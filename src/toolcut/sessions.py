"""Tool sessions: how a harness or agent talks to a shape. In process, or over real MCP stdio.

Every session logs each call (name, argument bytes, result bytes, seconds, error flag) so the
metrics come from what actually crossed the boundary.
"""

from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass, field

from .shapes import ToolResult, make_shape


@dataclass
class CallLog:
    name: str
    arg_bytes: int
    result_bytes: int
    seconds: float
    is_error: bool


@dataclass
class Session:
    log: list[CallLog] = field(default_factory=list)

    def list_tools(self) -> list[dict]:
        raise NotImplementedError

    def _call(self, name: str, args: dict) -> ToolResult:
        raise NotImplementedError

    def call(self, name: str, args: dict) -> ToolResult:
        start = time.perf_counter()
        result = self._call(name, args)
        self.log.append(CallLog(name, len(json.dumps(args, separators=(",", ":"), ensure_ascii=False).encode()), len(result.text.encode()),
                                time.perf_counter() - start, result.is_error))
        return result

    def close(self) -> None:
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


class InProcessSession(Session):
    def __init__(self, shape_key: str, api_url: str):
        super().__init__()
        self.shape = make_shape(shape_key, api_url)

    def list_tools(self) -> list[dict]:
        return self.shape.list_tools()

    def _call(self, name, args):
        return self.shape.call_tool(name, args)


class McpSession(Session):
    """Starts `python -m toolcut.mcp_server` as a child and talks MCP over stdio."""

    def __init__(self, shape_key: str, api_url: str, timeout: float = 60.0):
        super().__init__()
        from anyio.from_thread import start_blocking_portal
        from mcp import Client, StdioServerParameters

        self._portal_cm = start_blocking_portal()
        self._portal = self._portal_cm.__enter__()
        params = StdioServerParameters(command=sys.executable, args=["-m", "toolcut.mcp_server", "--shape", shape_key, "--api-url", api_url])
        try:
            self._client_cm = self._portal.wrap_async_context_manager(Client(params, read_timeout_seconds=timeout))
            self._client = self._client_cm.__enter__()
        except BaseException:
            self._portal_cm.__exit__(None, None, None)
            raise

    def list_tools(self) -> list[dict]:
        result = self._portal.call(self._client.list_tools)
        return [t.model_dump(by_alias=True, exclude_none=True) for t in result.tools]

    def _call(self, name, args):
        result = self._portal.call(self._client.call_tool, name, args)
        text = "".join(c.text for c in result.content if getattr(c, "type", "") == "text")
        return ToolResult(text, bool(result.is_error))

    def close(self) -> None:
        try:
            self._client_cm.__exit__(None, None, None)
        finally:
            self._portal_cm.__exit__(None, None, None)


def open_session(shape_key: str, api_url: str, transport: str = "inprocess") -> Session:
    if transport == "mcp":
        return McpSession(shape_key, api_url)
    if transport == "inprocess":
        return InProcessSession(shape_key, api_url)
    raise ValueError(f"unknown transport {transport}")
