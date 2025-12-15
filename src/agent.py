import json
import asyncio
import tiktoken
from typing import List, Dict, Any
from openai import AsyncOpenAI
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown

from config import cfg
from .browser import BrowserService

console = Console()

class Agent:
    def __init__(self, browser: BrowserService):
        self.client = AsyncOpenAI(api_key=cfg.API_KEY, base_url=cfg.BASE_URL)
        self.browser = browser
        self.history: List[Dict[str, Any]] = []
        self.plan: List[str] = []
        self.notes: List[str] = []
        self.main_goal: str = ""
        self.has_planned: bool = False

        self.last_action = None
        self.repeated_action_count = 0

        self.tools_map = {
            "mark_step_done": self._tool_mark_done,
            "finish_task": self._tool_finish,
            "ask_user": self._tool_ask_user,
            "open_url": self.browser.open_url,
            "scan_page": self.browser.scan_page,
            "click_element": self.browser.click_element,
            "type_text": self.browser.type_text,
            "scroll": self.browser.scroll,
            "get_tabs": self.browser.get_tabs,
            "switch_tab": self.browser.switch_tab,
            "close_tab": self.browser.close_tab
        }

    async def run(self, task: str):
        self.main_goal = task
        self.plan = []
        self.history = []
        self.notes = []
        self.has_planned = False

        self.last_action = None
        self.repeated_action_count = 0

        console.print(Panel(f"[bold cyan]Task:[/bold cyan] {task}", title="🤖 New Mission"))

        for i in range(cfg.MAX_ITERATIONS):
            self._prune_history()

            if not self.plan and not self.has_planned:
                role = "PLANNER"
            else:
                role = "WORKER"

            console.rule(f"Step {i + 1} | Role: {role}")

            try:
                response = await self.client.chat.completions.create(
                    model=cfg.MODEL_NAME,
                    messages=[{"role": "system", "content": self._get_system_prompt(role)}] + self.history,
                    tools=self._get_tool_definitions(role),
                    tool_choice="auto"
                )
            except Exception as e:
                console.print(f"[bold red]API Error: {e}[/bold red]")
                await asyncio.sleep(5)
                continue

            msg = response.choices[0].message
            self.history.append(msg.model_dump())

            if msg.content:
                console.print(Panel(Markdown(msg.content), title="🧠 Thought", style="yellow"))

            if not msg.tool_calls:
                console.print("[dim magenta]No tools called.[/dim magenta]")
                if role == "PLANNER":
                     self.history.append({"role": "user", "content": "You must call 'set_plan' or 'ask_user'."})
                else:
                     self.history.append({"role": "user", "content": "Action required. Please call a tool to proceed."})
                continue

            reset_context = False

            for tool_call in msg.tool_calls:
                fname = tool_call.function.name
                args_str = tool_call.function.arguments
                console.print(f"🔧 Call: [bold green]{fname}[/bold green] {args_str[:100]}")

                try:
                    args = json.loads(args_str)

                    if fname == "set_plan":
                        self.plan = args.get("steps", [])
                        console.print(Panel(f"Plan set: {self.plan}", title="📝 Plan Updated", style="green"))
                        self.history = []
                        self.has_planned = True
                        reset_context = True
                        break

                    if fname == "finish_task":
                        console.print(Panel(args.get("final_result", "Done"), title="🏁 Done", style="green"))
                        return

                    current_action = (fname, str(args))

                    if current_action == self.last_action:
                        self.repeated_action_count += 1
                    else:
                        self.repeated_action_count = 0

                    if self.repeated_action_count >= 3:
                        result = "⛔ SYSTEM OVERRIDE: You are looping the exact same action 3 times. STOP. You MUST choose a DIFFERENT tool or strategy."
                        console.print(f"[bold red]{result}[/bold red]")
                    else:
                        func = self.tools_map.get(fname)
                        if func:
                            if asyncio.iscoroutinefunction(func):
                                result = await func(**args)
                            else:
                                result = func(**args)
                        else:
                            result = f"Error: Tool {fname} not found"

                    if "Error" in str(result) or "fail" in str(result).lower():
                        result += self._get_error_hint(fname, str(result))

                    self.last_action = current_action

                except Exception as e:
                    result = f"Error executing {fname}: {e}"
                    console.print(f"[red]{result}[/red]")

                if not reset_context:
                    self._add_tool_result(tool_call.id, str(result))

    def _prune_history(self):
        try:
            enc = tiktoken.encoding_for_model(cfg.MODEL_NAME)
        except:
            enc = tiktoken.get_encoding("cl100k_base")

        total_tokens = 0
        kept_messages = []
        TOKEN_LIMIT = 100000

        for msg in reversed(self.history):
            msg_content = str(msg.get("content") or "")
            if msg.get("tool_calls"):
                msg_content += str(msg["tool_calls"])

            msg_tokens = len(enc.encode(msg_content))

            if total_tokens + msg_tokens > TOKEN_LIMIT:
                break

            total_tokens += msg_tokens
            kept_messages.append(msg)

        self.history = list(reversed(kept_messages))

    def _add_tool_result(self, tool_id: str, result: str):
        display_res = result if len(result) < 200 else f"...large output ({len(result)} chars)..."
        console.print(f"   ℹ️ Result: [dim]{display_res}[/dim]")

        if len(result) > 20000:
            result = result[:2000] + "\n...[TRUNCATED DUE TO LENGTH]... Call scan_page again if needed."

        self.history.append({
            "role": "tool",
            "tool_call_id": tool_id,
            "content": result
        })

    def _tool_mark_done(self, result_summary: str):
        if self.plan:
            done_step = self.plan.pop(0)
            console.print(f"✅ [bold strike]{done_step}[/bold strike]")

        self.notes.append(f"Step done: {result_summary}")
        return "Step marked done."

    def _tool_finish(self, final_result: str):
        return "Finished."

    def _tool_ask_user(self, question: str):
        console.print(Panel(question, title="❓ Question", style="magenta"))
        ans = console.input("[bold magenta]Answer > [/bold magenta]")
        self.notes.append(f"User Clarification (Q: {question} | A: {ans})")
        return f"User Answer: {ans}"

    def _get_system_prompt(self, role: str) -> str:
        context_str = "\n".join(self.notes) or "None"

        if role == "PLANNER":
            return f"""You are a Strategic Planner for a web automation agent.
                    MAIN GOAL: "{self.main_goal}"
                    CONTEXT: {context_str}

                    *** CRITICAL RULES FOR PLANNING ***
                    1. **USE SEARCH BAR**: This is the #1 Rule. If the user wants a specific product or topic, NEVER try to navigate via categories/filters. ALWAYS plan to "Type [query] into search" first.
                    2. **KEEP IT SIMPLE**: Create short, direct plans. 
                       - Bad: "Go to Electronics -> Phones -> Filters -> Brand X"
                       - Good: "Search for 'Brand X Phone', Click first result".
                    3. **DIRECT NAVIGATION**: If the URL is known or obvious, go there directly.

                    INSTRUCTIONS:
                    1. Analyze the MAIN GOAL.
                    2. If unclear, call 'ask_user'.
                    3. Otherwise, call 'set_plan' with a simple, direct list of steps.
                    """
        else:
            if not self.plan:
                return f"Plan empty. Goal: {self.main_goal}. Call 'finish_task' or 'ask_user'."

            step = self.plan[0]

            return f"""You are a Browser Worker.
                    GOAL: "{self.main_goal}"
                    CURRENT STEP: "{step}"
                    PREVIOUS ACTIONS REPEAT COUNT: {self.repeated_action_count}

                    *** STRATEGY FOR CLICKING PRODUCTS ***
                    1. **DO NOT GUESS**. If you see a list of results, you MUST find the element that contains the text "{self.main_goal}" (or keywords like 'Poco', 'iPhone', etc).
                    2. **IGNORE** navigation links like "Back", "Filters", "Sort", "Results".
                    3. **VERIFY** before clicking. Does the element text match the product name?
                    4. If the list is huge and you don't see the text, `scroll` down and `scan_page` again.

                    *** PROTOCOL ***
                    1. **THINK**: Assess the page. Identify the element ID that matches the goal text.
                    2. **ACT**: YOU MUST GENERATE A TOOL CALL. Writing "ACT" in text is not enough.

                    FORMAT:
                    THOUGHT: [I see the list. Element 42 has text 'Poco X7 Pro 256GB'. Matches goal. I will click it.]
                    ACT: [Tool Call]
                    """

    def _get_tool_definitions(self, role: str) -> List[dict]:
        if role == "PLANNER":
            return [{
                "type": "function",
                "function": {
                    "name": "set_plan",
                    "description": "Set execution steps.",
                    "parameters": {"type": "object",
                                   "properties": {"steps": {"type": "array", "items": {"type": "string"}}},
                                   "required": ["steps"]}
                }
            }, {
                "type": "function",
                "function": {
                    "name": "ask_user",
                    "description": "Ask clarification.",
                    "parameters": {"type": "object", "properties": {"question": {"type": "string"}},
                                   "required": ["question"]}
                }
            }]

        return [
            {"type": "function", "function": {"name": "open_url", "parameters": {"type": "object", "properties": {
                "url": {"type": "string"}}, "required": ["url"]}}},
            {"type": "function", "function": {"name": "scan_page",
                                              "description": "Get interactive elements map.",
                                              "parameters": {"type": "object", "properties": {}}}},
            {"type": "function", "function": {"name": "click_element", "parameters": {"type": "object", "properties": {
                "element_id": {"type": "integer"}}, "required": ["element_id"]}}},
            {"type": "function", "function": {"name": "type_text", "parameters": {"type": "object", "properties": {
                "element_id": {"type": "integer"}, "text": {"type": "string"},
                "submit": {"type": "boolean", "description": "Press Enter after typing? Default True"}},
                                                                                  "required": ["element_id", "text"]}}},
            {"type": "function", "function": {"name": "scroll", "parameters": {"type": "object", "properties": {
                "direction": {"type": "string", "enum": ["up", "down"]}}, "required": ["direction"]}}},
            {"type": "function",
             "function": {"name": "mark_step_done", "description": "Call when step is done.",
                          "parameters": {"type": "object", "properties": {"result_summary": {"type": "string"}},
                                         "required": ["result_summary"]}}},
            {"type": "function",
             "function": {"name": "finish_task", "description": "Call when ALL steps are done.",
                          "parameters": {"type": "object", "properties": {"final_result": {"type": "string"}},
                                         "required": ["final_result"]}}},
            {"type": "function", "function": {"name": "get_tabs", "parameters": {"type": "object", "properties": {}}}},
            {"type": "function", "function": {"name": "switch_tab", "parameters": {"type": "object", "properties": {
                "idx": {"type": "integer"}}, "required": ["idx"]}}},
            {"type": "function", "function": {"name": "close_tab", "parameters": {"type": "object", "properties": {}}}}
        ]

    def _get_error_hint(self, fname: str, error_msg: str) -> str:
        hint = "\n\n💡 ADAPTIVE STRATEGY: "

        if fname == "click_element":
            if "outside of the viewport" in error_msg:
                return hint + "The element is hidden. Call 'scroll(direction='down')' to reveal it."
            if "obscured" in error_msg:
                return hint + "Something covers the element. Try closing popups first."
            return hint + "Click failed. Try: 1. Scroll closer. 2. Search by typing text instead. 3. Use 'open_url' to navigate directly."

        elif fname == "scan_page":
            return hint + "If the page is empty, try waiting a bit or reloading. If it's too big, ignore navigation elements and focus on content."

        elif fname == "type_text":
            return hint + "Typing failed. Try clicking the input field first, then type again."

        return ""