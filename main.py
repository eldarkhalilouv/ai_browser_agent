import asyncio
from colorama import Fore
from src.browser_manager import BrowserManager
from src.agent_brain import AgentBrain
from src.logger import Logger


# Точка входа в приложение (python main.py)
async def main():
    browser_manager = BrowserManager()
    await browser_manager.start()

    try:
        agent = AgentBrain(browser_manager)
        Logger.info("System Initialized. Ready.")

        while True:
            task = input(Fore.YELLOW + "\n👨‍💻 ВВЕДИТЕ ЗАДАЧУ (или 'q' для выхода): ")
            if task.lower() in ['q', 'exit']:
                break

            Logger.info("🚀 Запускаю задачу...")
            await agent.run_loop(task)
            Logger.info("🏁 Задача завершена. Жду следующую.")

    except Exception as e:
        Logger.error(f"Global Error: {e}")
    finally:
        await browser_manager.stop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nGoodbye!")