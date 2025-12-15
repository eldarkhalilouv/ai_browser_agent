import os
from dataclasses import dataclass, field
from typing import List
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    API_KEY: str = os.getenv("OPENROUTER_API_KEY") or os.getenv("API_KEY", "")
    MODEL_NAME: str = os.getenv("MODEL_NAME", "openai/gpt-4o-mini")
    BASE_URL: str = "https://openrouter.ai/api/v1"

    HEADLESS: bool = False
    VIEWPORT: dict = field(default_factory=lambda: {"width": 1280, "height": 800})
    TIMEOUT: int = 15000
    LOCALE: str = "ru-RU"
    STORAGE_STATE: str = "auth.json"

    USER_AGENT: str = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

    MAX_ITERATIONS: int = 50

    BROWSER_ARGS: List[str] = field(default_factory=lambda: [
        "--disable-blink-features=AutomationControlled",
        "--no-sandbox",
        "--disable-infobars",
        "--start-maximized"
    ])

    def get_api_key(self):
        if not self.API_KEY:
            raise ValueError("API Key is missing! Check .env file.")
        return self.API_KEY

cfg = Config()