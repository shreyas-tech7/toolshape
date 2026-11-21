"""What every shape provides. A shape is a list of tools plus a way to call them."""

from __future__ import annotations

import json
from dataclasses import dataclass

from ..taskdesk.client import TaskDeskError


@dataclass
class ToolResult:
    text: str
    is_error: bool = False


class Shape:
    """Base class. Subclasses set key, title and implement tools() and dispatch()."""

    key = "?"
    title = "?"

    def __init__(self, api_url: str):
        self.api_url = api_url

    def tools(self) -> list[dict]:
        """MCP tool definitions: dicts with name, description and inputSchema."""
        raise NotImplementedError

    def dispatch(self, name: str, args: dict) -> object:
        raise NotImplementedError

    def list_tools(self) -> list[dict]:
        return self.tools()

    def call_tool(self, name: str, args: dict | None) -> ToolResult:
        """Run one tool call. Errors come back as text with is_error set, never as exceptions."""
        args = args or {}
        if name not in {t["name"] for t in self.tools()}:
            return ToolResult(json.dumps({"error": f"unknown tool {name}"}), True)
        if not isinstance(args, dict):
            return ToolResult(json.dumps({"error": "arguments must be a JSON object"}), True)
        try:
            out = self.dispatch(name, args)
        except TaskDeskError as e:
            return ToolResult(json.dumps({"error": e.message, "status": e.status}), True)
        except (TypeError, ValueError, KeyError) as e:
            return ToolResult(json.dumps({"error": str(e)}), True)
        if isinstance(out, ToolResult):
            return out
        return ToolResult(json.dumps(out, separators=(",", ":")))
