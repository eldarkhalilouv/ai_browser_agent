import os
import asyncio
from typing import Optional
from playwright.async_api import async_playwright, Playwright, Browser, BrowserContext, Page, Locator
from config import cfg
from .accessibility import AccessibilityParser


class BrowserService:
    def __init__(self):
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.parser = AccessibilityParser()

    async def start(self):
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=cfg.HEADLESS,
            channel="chrome",
            args=cfg.BROWSER_ARGS
        )

        state = cfg.STORAGE_STATE if os.path.exists(cfg.STORAGE_STATE) else None

        self.context = await self.browser.new_context(
            storage_state=state,
            viewport=cfg.VIEWPORT,
            locale=cfg.LOCALE,
            user_agent=cfg.USER_AGENT
        )

        await self.context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        self.context.on("page", self._handle_new_tab)
        self.page = await self.context.new_page()

    async def stop(self):
        if self.context:
            await self.context.storage_state(path=cfg.STORAGE_STATE)
            await self.context.close()
        if self.browser: await self.browser.close()
        if self.playwright: await self.playwright.stop()

    async def open_url(self, url: str) -> str:
        if not self.page: return "Browser not started."
        if not url.startswith("http"): url = "https://" + url
        try:
            await self.page.goto(url, wait_until="domcontentloaded", timeout=cfg.TIMEOUT)
            await asyncio.sleep(2)
            await self._dismiss_overlays()
            return f"Opened {url} - Title: {await self.page.title()}"
        except Exception as e:
            return f"Error opening url: {e}"

    async def scan_page(self) -> str:
        if not self.page: return "No page."
        await self._dismiss_overlays()
        return await self.parser.scan(self.page)

    async def click_element(self, element_id: int) -> str:
        """
        Adaptive Click:
        1. Try normal click.
        2. If obscured/outside viewport -> Scroll & Force Click.
        3. If selector fails -> Try searching by Text content.
        4. If still fails -> Try JavaScript dispatchEvent.
        """
        el_info = self.parser.elements_map.get(element_id)
        if not el_info: return f"❌ Error: ID {element_id} not found. Suggestion: Call 'scan_page' to refresh IDs."

        if el_info.name:
            loc = self.page.get_by_role(el_info.role, name=el_info.name).first
        else:
            loc = self.page.get_by_role(el_info.role).first

        if not await loc.count() and el_info.name:
            loc = self.page.get_by_text(el_info.name).first

        if not await loc.count():
            return f"❌ Error: Element '{el_info.name}' disappeared from DOM. Suggestion: Page might have updated. Call 'scan_page'."

        try:
            await loc.scroll_into_view_if_needed(timeout=1000)

            await loc.click(timeout=2000)
            return f"✅ Clicked {el_info.role} '{el_info.name}' (Standard)"

        except Exception as e_standard:
            try:
                await loc.click(timeout=2000, force=True)
                return f"⚠️ Clicked {el_info.role} '{el_info.name}' (Forced - element was obscured)"

            except Exception as e_force:
                try:
                    await loc.evaluate("element => element.click()")
                    return f"⚠️ Clicked {el_info.role} '{el_info.name}' (via JS Injection)"
                except Exception as e_js:
                    return f"❌ CRITICAL FAIL: Could not click '{el_info.name}'.\nReasons:\n1. Standard: {e_standard}\n2. Force: {e_force}\n3. JS: {e_js}\n👉 ADVICE: Don't try clicking this again. Use 'scroll' or check if it's the right element."

    async def type_text(self, element_id: int, text: str, submit: bool = True) -> str:
        el_info = self.parser.elements_map.get(element_id)
        if not el_info: return f"ID {element_id} not found."

        try:
            locator = self.page.get_by_role(el_info.role, name=el_info.name).first
            await locator.click(force=True)
            await locator.fill("")
            await locator.fill(text)
            if submit:
                await self.page.keyboard.press("Enter")
                return f"Typed '{text}' into {el_info.name} and pressed ENTER"
            return f"Typed '{text}' into {el_info.name}"
        except Exception as e:
            return f"Typing failed: {e}"

    async def scroll(self, direction: str) -> str:
        if not self.page: return "No page."
        delta = 800 if direction == "down" else -800
        await self.page.mouse.wheel(0, delta)
        await asyncio.sleep(0.5)
        return f"Scrolled {direction}."

    async def get_tabs(self) -> str:
        if not self.context: return "No context."
        return "\n".join([f"{i}: {p.url} ({await p.title()})" + (" [ACTIVE]" if p == self.page else "")
                          for i, p in enumerate(self.context.pages)])

    async def switch_tab(self, idx: int) -> str:
        if not self.context or not (0 <= idx < len(self.context.pages)): return "Invalid tab index."
        self.page = self.context.pages[idx]
        await self.page.bring_to_front()
        return f"Active tab: {await self.page.title()}"

    async def close_tab(self) -> str:
        if not self.context or len(self.context.pages) <= 1: return "Cannot close last tab."
        await self.page.close()
        self.page = self.context.pages[-1]
        return "Tab closed."

    async def _handle_new_tab(self, page: Page):
        await page.wait_for_load_state("domcontentloaded")
        self.page = page

    async def _dismiss_overlays(self):
        if not self.page: return
        try:
            selectors = [
                "button[aria-label='Закрыть']",
                "div[data-apiary-widget-name='RegionPopup'] button",
                ".Cookie-Button",
                "button:has-text('Принять')",
                "button:has-text('Понятно')"
            ]
            for sel in selectors:
                try:
                    loc = self.page.locator(sel).first
                    if await loc.is_visible(timeout=500):
                        await loc.click(force=True)
                except Exception as e:
                    return f"Failed: {e}"
        except Exception as e:
            return f"Failed: {e}"