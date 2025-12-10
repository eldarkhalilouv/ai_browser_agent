import json
from colorama import Fore, Style, init

init(autoreset=True)


# Методы для логгирования
class Logger:
    @staticmethod
    def agent(text: str):
        print(Fore.GREEN + Style.BRIGHT + f"\n🧠 THOUGHT: {text}")

    @staticmethod
    def tool(name: str, args: dict):
        try:
            args_str = str(args)
            if len(args_str) > 100: args_str = args_str[:100] + "..."
        except:
            args_str = "..."
        print(Fore.BLUE + f"🔧 CALL: {name} {Fore.CYAN}{args_str}")

    @staticmethod
    def info(text: str):
        print(Fore.WHITE + f"   ℹ️ {text}")

    @staticmethod
    def success(text: str):
        print(Fore.MAGENTA + f"   ✅ {text}")

    @staticmethod
    def error(text: str):
        print(Fore.RED + f"   ❌ {text}")