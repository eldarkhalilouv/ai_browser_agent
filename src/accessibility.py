from typing import Dict, Any, List
from dataclasses import dataclass


@dataclass
class ElementInfo:
    id: int
    role: str
    name: str
    attributes: str = ""


class AccessibilityParser:
    INTERACTIVE_ROLES = {
        'button', 'link', 'textbox', 'searchbox', 'combobox',
        'checkbox', 'radio', 'slider', 'tab', 'menuitem', 'switch', 'treeitem'
    }

    CONTEXT_ROLES = {'heading', 'img', 'statictext', 'text', 'paragraph', 'listitem'}

    def __init__(self):
        self.elements_map: Dict[int, ElementInfo] = {}

    async def scan(self, page) -> str:
        self.elements_map.clear()
        try:
            snapshot = await page.accessibility.snapshot(interesting_only=False)
        except Exception as e:
            return f"Error scanning page: {e}"

        if not snapshot:
            return "Accessibility tree is empty."

        report_lines = []
        self._traverse(snapshot, report_lines)

        if not report_lines:
            return "No interactive elements found. Try scrolling."

        return f"Interactive Elements ({len(self.elements_map)} items):\n" + "\n".join(report_lines)

    def _traverse(self, node: Dict[str, Any], report: List[str]):
        if len(self.elements_map) >= 800:
            return

        role = node.get("role", "generic")
        name = node.get("name", "").strip()
        children = node.get("children", [])

        value = node.get("value")
        checked = node.get("checked")
        level = node.get("level")
        disabled = node.get("disabled")

        if not name and children and role in self.INTERACTIVE_ROLES:
            name = self._collect_text(children)

        is_interactive = role in self.INTERACTIVE_ROLES
        is_heading = role == 'heading'
        is_content = role in self.CONTEXT_ROLES and name and len(name) > 2

        if not (is_interactive or is_heading or is_content):
            for child in children:
                self._traverse(child, report)
            return

        attrs = []
        if role in ['textbox', 'searchbox'] and not name and value:
            name = f"[Value: {value}]"
        if value and str(value) != str(name): attrs.append(f"val={value}")
        if checked: attrs.append("checked")
        if disabled: attrs.append("disabled")
        if level: attrs.append(f"h{level}")

        attr_str = f" ({', '.join(attrs)})" if attrs else ""

        display_name = name.replace("\n", " ")
        if len(display_name) > 80:
            display_name = display_name[:77] + "..."

        el_id = None
        prefix = "  -"

        if is_interactive:
            el_id = len(self.elements_map) + 1
            self.elements_map[el_id] = ElementInfo(id=el_id, role=role, name=name)
            prefix = f"{el_id}."

        if is_heading:
            report.append(f"\n=== {role.upper()} {display_name} ===")
        elif el_id:
            report.append(f"{prefix} [{role}] {display_name}{attr_str}")
        else:
            if any(x in display_name for x in ['₽', '$', '€']) or len(display_name) > 20:
                report.append(f"    (txt) {display_name}")

        for child in children:
            self._traverse(child, report)

    def _collect_text(self, children: List[Dict]) -> str:
        text = []
        for child in children:
            name = child.get("name", "").strip()
            if name:
                text.append(name)
            else:
                text.append(self._collect_text(child.get("children", [])))
        return " ".join([t for t in text if t]).strip()