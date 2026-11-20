"""Shape A: one tool per API endpoint. The tool list is a mirror of the operation list."""

from __future__ import annotations

from ..taskdesk.client import TaskDesk
from ..taskdesk.ops import OPS, input_schema
from .base import Shape


class ShapeA(Shape):
    key = "A"
    title = "One tool per endpoint"

    def __init__(self, api_url: str):
        super().__init__(api_url)
        self.client = TaskDesk(api_url)
        self._tools = [{"name": op.name, "description": op.summary, "inputSchema": input_schema(op)} for op in OPS]

    def tools(self) -> list[dict]:
        return self._tools

    def dispatch(self, name: str, args: dict) -> object:
        return self.client.call(name, args)
