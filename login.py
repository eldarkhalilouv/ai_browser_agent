import asyncio
from playwright.async_api import async_playwright
from config import Config

AUTH_FILE = "auth.json"


async def save_session():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)

        context = await browser.new_context(
            user_agent=Config.USER_AGENT,
            viewport=Config.VIEWPORT,
            locale="ru-RU"
        )

        page = await context.new_page()

        print("🌍 Браузер открыт!")
        print("👉 Заходи на нужные сайты (WB, Ozon, Яндекс).")
        print("👉 Логинься, вводи СМС коды.")
        print("⚡ Когда закончишь и увидишь свой профиль - вернись сюда и нажми ENTER.")

        await page.goto("https://www.wildberries.ru")

        input("\nНажми Enter, чтобы сохранить сессию...")

        await context.storage_state(path=AUTH_FILE)
        print(f"✅ Сессия сохранена в {AUTH_FILE}")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(save_session())