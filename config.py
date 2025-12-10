import os
from dotenv import load_dotenv

load_dotenv()


# Глобальный конфиг и .env лоудер
class Config:
    API_KEY = os.getenv("OPENAI_API_KEY")
    MODEL_NAME = "gpt-5-mini"

    HEADLESS = False
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
    VIEWPORT = {"width": 1280, "height": 800}

    PAGE_LOAD_TIMEOUT = 5000