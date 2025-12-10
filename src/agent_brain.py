import json
from openai import AsyncOpenAI
from config import Config
from src.logger import Logger
from src.browser_manager import BrowserManager


# Логика управления tool calls
class AgentBrain:
    def __init__(self, browser: BrowserManager):
        if not Config.API_KEY:
            raise ValueError("API Key not found")
        self.client = AsyncOpenAI(api_key=Config.API_KEY)
        self.browser = browser
        self.history = []
        self.tools_schema = self._get_tools_schema()

    def _get_tools_schema(self):
        return [
            {
                "type": "function",
                "function": {
                    "name": "open_url",
                    "description": "Перейти по ссылке",
                    "parameters": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "scan_page",
                    "description": "Просканировать страницу, чтобы найти ID элементов (кнопок, ссылок)",
                    "parameters": {"type": "object", "properties": {}}
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "click_element",
                    "description": "Кликнуть по элементу (нужен ID из scan_page)",
                    "parameters": {"type": "object", "properties": {"element_id": {"type": "integer"}},
                                   "required": ["element_id"]}
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "type_text",
                    "description": "Ввести текст в поле (нужен ID из scan_page)",
                    "parameters": {"type": "object",
                                   "properties": {"element_id": {"type": "integer"}, "text": {"type": "string"}},
                                   "required": ["element_id", "text"]}
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "scroll_up",
                    "description": "Прокрутить страницу вверх",
                    "parameters": {"type": "object", "properties": {}}
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "scroll_down",
                    "description": "Прокрутить страницу вниз",
                    "parameters": {"type": "object", "properties": {}}
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "finish_task",
                    "description": "Завершить работу успешно",
                    "parameters": {"type": "object",
                                   "properties": {"result": {"type": "string"}, "link": {"type": "string"}},
                                   "required": ["result", "link"]}
                }
            }
        ]

    async def run_loop(self, user_task: str):
        system_prompt = """
        Ты - автономный AI-агент, управляющий браузером. Твоя задача - выполнить цель пользователя.

        ТВОЙ ПРОЦЕСС МЫШЛЕНИЯ (ReAct):
        1. OBSERVATION (Наблюдение): Сначала посмотри на страницу через `scan_page`.
        2. THOUGHT (Мысль): Проанализируй, где ты находишься и какой элемент нужен. Напиши это текстом.
        3. ACTION (Действие): Вызови инструмент.

        ВАЖНО:
        - Если открылась страница, ВСЕГДА делай `scan_page`, чтобы получить актуальные ID элементов.
        - Если видишь попап (cookies, реклама) - закрой его.
        - Перед вызовом функции всегда пиши краткое обоснование.
        
        ТЫ ПОЛНОСТЬЮ АВТОНОМЕН.
            - ЗАПРЕЩЕНО спрашивать пользователя "что делать дальше".
            - ЗАПРЕЩЕНО писать "Что предлагаю дальше".
            - Если застрял - пробуй другой путь (например, scroll_up, open_url).
            - Если не можешь выполнить задачу - вызывай finish_task с описанием ошибки.
        """

        self.history = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"ЗАДАЧА: {user_task}"}
        ]

        step_limit = 25
        step = 0

        while step < step_limit:
            step += 1
            response = await self.client.chat.completions.create(
                model=Config.MODEL_NAME,
                messages=self.history,
                tools=self.tools_schema,
                tool_choice="auto"
            )

            msg = response.choices[0].message
            self.history.append(msg)

            if msg.content:
                Logger.agent(msg.content)

            if not msg.tool_calls:
                self.history.append({"role": "user",
                                     "content": "Не просто болтай, а действуй! Используй инструменты (scan_page, click, etc)."})
                continue

            should_stop = False
            for tool in msg.tool_calls:
                fname = tool.function.name
                try:
                    args = json.loads(tool.function.arguments)
                except:
                    args = {}

                Logger.tool(fname, args)

                res = "Error"
                if fname == "open_url":
                    res = await self.browser.open_url(args.get("url"))
                elif fname == "scan_page":
                    res = await self.browser.scan_page()
                elif fname == "click_element":
                    res = await self.browser.click_element(args.get("element_id"))
                elif fname == "type_text":
                    res = await self.browser.type_text(args.get("element_id"), args.get("text"))
                elif fname == "scroll_down":
                    res = await self.browser.scroll_down()
                elif fname == "finish_task":
                    Logger.success(f"FINAL RESULT: {args.get('result')}")
                    should_stop = True
                    res = "Task Completed"

                self.history.append({
                    "role": "tool",
                    "tool_call_id": tool.id,
                    "content": str(res)
                })

            if should_stop:
                break

        if step >= step_limit:
            Logger.error("Превышен лимит шагов агента.")