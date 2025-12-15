import asyncio
from rich.console import Console
from aioconsole import ainput

from src.agent import Agent
from src.browser import BrowserService

console = Console()


async def main():
    browser = BrowserService()

    try:
        await browser.start()
        agent = Agent(browser)

        console.print("[bold green]System Ready. Browser launched.[/bold green]")

        while True:
            task = await ainput("\nEnter task (q to exit): ")
            if task.lower() in ['q', 'exit']:
                break

            await agent.run(task)

    except KeyboardInterrupt:
        print("\nGoodbye!")
    except Exception as e:
        console.print(f"[bold red]Critical Error: {e}[/bold red]")
    finally:
        console.print("Stopping browser...")
        await browser.stop()


if __name__ == "__main__":
    asyncio.run(main())