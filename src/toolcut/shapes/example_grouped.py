"""Example shape for docs/ADDING_A_SHAPE.md: one tool per resource, with the operation as an argument.

It is not part of the benchmark. tests/test_shape_guide.py registers it, checks that it reaches
every operation, and runs the oracle through it.
"""

from __future__ import annotations

from ..taskdesk.client import TaskDesk
from ..taskdesk.ops import OPS
from .base import Shape

GROUPS = {
    "users": "Read and change TaskDesk users.",
    "projects": "Read and change projects and their members.",
    "tasks": "Read, search and change tasks and their labels.",
    "comments": "Read and change comments on tasks.",
}


def group_of(op_name: str) -> str:
    if op_name.endswith(("_user", "_users")):
        return "users"
    if "project" in op_name and "task" not in op_name:
        return "projects"
    if "comment" in op_name:
        return "comments"
    return "tasks"


class ShapeD(Shape):
    key = "D"
    title = "D: one tool per resource"

    def __init__(self, api_url: str):
        super().__init__(api_url)
        self.client = TaskDesk(api_url)

    def tools(self) -> list[dict]:
        out = []
        for group, desc in GROUPS.items():
            ops = [op for op in OPS if group_of(op.name) == group]
            lines = "; ".join(f"{op.name}({', '.join(p.name for p in op.params)}): {op.summary}" for op in ops)
            out.append({"name": group, "description": f"{desc} Operations: {lines}",
                        "inputSchema": {"type": "object", "properties": {
                            "operation": {"type": "string", "enum": [op.name for op in ops]},
                            "args": {"type": "object", "description": "Arguments for the operation, by name."},
                        }, "required": ["operation"], "additionalProperties": False}})
        return out

    def dispatch(self, name: str, args: dict) -> object:
        op = args.get("operation")
        if group_of(str(op)) != name:
            raise ValueError(f"{op} is not an operation of {name}")
        return self.client.call(op, args.get("args") or {})
