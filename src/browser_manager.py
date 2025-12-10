import asyncio
import os
from playwright.async_api import async_playwright, Page, BrowserContext
from config import Config
from src.logger import Logger


# Управление браузером через tool calls
class BrowserManager:
    def __init__(self):
        self.playwright = None
        self.browser = None
        self.context: BrowserContext = None
        self.page: Page = None


    async def start(self):
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            channel="chrome",
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-infobars",
                "--start-maximized"
            ]
        )

        storage_state = "auth.json" if os.path.exists("auth.json") else None
        if storage_state:
            Logger.info(f"Загружаю сессию из {storage_state}...")

        self.context = await self.browser.new_context(
            storage_state=storage_state,
            user_agent=Config.USER_AGENT,
            viewport=Config.VIEWPORT,
            locale="ru-RU"
        )

        await self.context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        self.page = await self.context.new_page()
        Logger.info("Browser Started (Stealth Mode)")


    async def stop(self):
        if self.context:
            await self.context.storage_state(path="auth.json")

        if self.context: await self.context.close()
        if self.browser: await self.browser.close()
        if self.playwright: await self.playwright.stop()


    async def open_url(self, url: str) -> str:
        if not self.page: return "Error: Browser not initialized"
        try:
            if not url.startswith("http"): url = "https://" + url
            await self.page.goto(url, wait_until="domcontentloaded", timeout=15000)
            await asyncio.sleep(2)
            return f"Opened {url}"
        except Exception as e:
            return f"Error opening URL: {e}"


    async def scroll_up(self, pixels: int = 700) -> str:
        if not self.page: return "Error: No page"
        try:
            await self.page.evaluate(f"window.scrollBy(0, -{pixels})")
            await asyncio.sleep(1)
            return "Scrolled up. Call scan_page to see content."
        except Exception as e:
            return f"Scroll error: {e}"


    async def scroll_down(self, pixels: int = 700) -> str:
        if not self.page: return "Error: No page"
        try:
            await self.page.evaluate(f"window.scrollBy(0, {pixels})")
            await asyncio.sleep(1)
            return "Scrolled down. Call scan_page to see new content."
        except Exception as e:
            return f"Scroll error: {e}"


    async def click_element(self, element_id: int) -> str:
        try:
            js_code = f"""
                (() => {{
                    let el = document.querySelector('[data-ai-id="{element_id}"]');
                    if(!el) return null;
                    el.scrollIntoView({{behavior: "smooth", block: "center"}});
                    let rect = el.getBoundingClientRect();
                    return {{ x: rect.x + rect.width / 2, y: rect.y + rect.height / 2 }};
                }})()
            """
            coords = await self.page.evaluate(js_code)

            if not coords:
                return f"Element {element_id} not found in DOM"

            await self.page.mouse.move(coords['x'], coords['y'], steps=10)

            await asyncio.sleep(0.3)

            await self.page.mouse.down()
            await asyncio.sleep(0.1)
            await self.page.mouse.up()

            await asyncio.sleep(2)

            return f"Clicked ID {element_id} (Human Mode)"
        except Exception as e:
            return f"Error clicking: {e}"


    async def type_text(self, element_id: int, text: str) -> str:
        try:
            await self.page.fill(f'[data-ai-id="{element_id}"]', text)
            await self.page.keyboard.press("Enter")
            return f"Typed '{text}' into ID {element_id}"
        except Exception as e:
            return f"Error typing: {e}"


    async def scan_page(self) -> str:
        if not self.page: return "Error: No page"

        js_script = """
        () => {
            let items = document.querySelectorAll('button, a, input, [role="button"], [role="link"], textarea');
            let map = {};
            let counter = 0;

            items.forEach((el, index) => {
                let rect = el.getBoundingClientRect();
                if (rect.width < 5 || rect.height < 5 || window.getComputedStyle(el).visibility === 'hidden') return;
                if (counter > 150) return;

                let id = index + 1;
                el.setAttribute('data-ai-id', id);
                el.style.border = "2px solid red"; 
                el.style.backgroundColor = "rgba(255, 0, 0, 0.1)";

                let label = el.innerText || el.placeholder || el.ariaLabel || el.name || "";
                label = label.replace(/\\s+/g, ' ').trim().substring(0, 50);

                if (!label && el.tagName !== 'INPUT') return; 
                if (el.tagName === 'INPUT') label = `INPUT: ${el.type} (placeholder: ${el.placeholder})`;

                map[id] = `[${el.tagName}] ${label}`;
                counter++;
            });
            return { url: window.location.href, elements: map };
        }
        """
        try:
            data = await self.page.evaluate(js_script)
            report = [f"CURRENT PAGE URL: {data['url']}", "VISIBLE ELEMENTS:"]
            for id, desc in data['elements'].items():
                report.append(f"ID {id}: {desc}")

            result = "\n".join(report)
            Logger.info(f"Page scanned. Found {len(data['elements'])} elements.")
            return result
        except Exception as e:
            return f"Scan error: {e}"