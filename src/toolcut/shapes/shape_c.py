"""Shape C: two tools. search_api finds operations. run_code runs a short Python script
against the typed TaskDesk client in the sandbox (see toolcut.sandbox)."""

from __future__ import annotations

import re

from ..sandbox import ALLOWED_IMPORTS, DEFAULT_TIMEOUT, run_code
from ..taskdesk.ops import OPS, PAGE_SIZE, signature
from .base import Shape, ToolResult

TOOLS = [
    {"name": "search_api", "description": (
        "Search the TaskDesk API. Returns matching client methods with their Python signatures and notes. "
        'Use query "*" to list every method name.'),
     "inputSchema": {"type": "object", "properties": {
         "query": {"type": "string", "description": "Words to look for, for example \"assign task\"."},
         "limit": {"type": "integer", "description": "Most results to return. Default 5."},
     }, "required": ["query"], "additionalProperties": False}},
    {"name": "run_code", "description": (
        "Run a short Python script. The global `taskdesk` is a TaskDesk client: call methods with keyword "
        "arguments, for example taskdesk.list_tasks(status=\"todo\", page=1). Each method returns a dict "
        f"(list methods return items, total and next_page, {PAGE_SIZE} items per page). Errors raise TaskDeskError. "
        f"Allowed imports: {', '.join(ALLOWED_IMPORTS)}. Names that start with _ are blocked. "
        f"print() what you need back. Output is cut at 20,000 characters. Time limit {DEFAULT_TIMEOUT:g} seconds."),
     "inputSchema": {"type": "object", "properties": {
         "code": {"type": "string", "description": "Python source."},
     }, "required": ["code"], "additionalProperties": False}},
]

_WORD = re.compile(r"[a-z]+")


def _words(text: str) -> set[str]:
    out = set()
    for w in _WORD.findall(text.lower()):
        out.add(w)
        if w.endswith("s") and len(w) > 3:
            out.add(w[:-1])
    return out


def describe(op) -> dict:
    return {"method": op.name, "signature": signature(op), "summary": op.summary,
            "params": {p.name: p.description or p.type for p in op.params if p.description or p.enum}}


def search(query: str, limit: int = 5) -> list[dict]:
    if query.strip() == "*":
        return [{"method": op.name, "summary": op.summary} for op in OPS]
    q = _words(query)
    scored = []
    for i, op in enumerate(OPS):
        name_words = _words(op.name.replace("_", " "))
        text_words = _words(op.summary + " " + " ".join(p.name.replace("_", " ") + " " + p.description for p in op.params))
        score = 3 * len(q & name_words) + len(q & text_words)
        if score:
            scored.append((-score, i, op))
    return [describe(op) for _, _, op in sorted(scored)[: max(1, int(limit))]]


class ShapeC(Shape):
    key = "C"
    title = "search_api plus run_code"

    def __init__(self, api_url: str, timeout: float = DEFAULT_TIMEOUT):
        super().__init__(api_url)
        self.timeout = timeout

    def tools(self) -> list[dict]:
        return TOOLS

    def dispatch(self, name: str, args: dict) -> object:
        if name == "search_api":
            extra = set(args) - {"query", "limit"}
            if extra or "query" not in args:
                raise ValueError("search_api takes query and optional limit")
            hits = search(str(args["query"]), args.get("limit") or 5)
            return {"results": hits} if hits else {"results": [], "hint": 'No match. Try query "*" for the full list.'}
        extra = set(args) - {"code"}
        if extra or not isinstance(args.get("code"), str):
            raise ValueError("run_code takes one string argument: code")
        result = run_code(args["code"], self.api_url, timeout=self.timeout)
        return ToolResult(result.as_text(), is_error=result.error is not None)
