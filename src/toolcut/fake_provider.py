"""A local OpenAI-compatible endpoint for offline tests and demos. It is not a model.

It replays a fixed trace of tool calls for each (task, shape): one call per turn, then a final
message. It finds the task from the user message and the shape from the tool names. It also
returns a usage field computed with the same estimate the agent uses, so both token paths run.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .agent import est_tokens
from .tasks import TASKS


def shape_of(tool_names: set[str]) -> str:
    if tool_names == {"search_api", "run_code"}:
        return "C"
    return "B" if "find_tasks" in tool_names else "A"


class FakeProvider:
    """traces: {(task_id, shape): [(tool name, args), ...]}. mode "trace" or "stop" (never calls a tool)."""

    def __init__(self, traces: dict, mode: str = "trace", with_usage: bool = True):
        self.traces = traces
        self.mode = mode
        self.with_usage = with_usage
        self.requests = 0
        by_prompt = {t.prompt: t.id for t in TASKS}
        prov = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)))
                prov.requests += 1
                messages = body["messages"]
                task_id = by_prompt.get(next(m["content"] for m in messages if m["role"] == "user"))
                shape = shape_of({t["function"]["name"] for t in body.get("tools", [])})
                done = sum(1 for m in messages if m["role"] == "tool")
                trace = prov.traces.get((task_id, shape), []) if prov.mode == "trace" else []
                if done < len(trace):
                    name, args = trace[done]
                    msg = {"role": "assistant", "content": "", "tool_calls": [
                        {"id": f"call_{done}", "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}]}
                else:
                    msg = {"role": "assistant", "content": "Done."}
                resp = {"id": f"fake-{prov.requests}", "object": "chat.completion", "model": body.get("model"),
                        "choices": [{"index": 0, "message": msg, "finish_reason": "tool_calls" if msg.get("tool_calls") else "stop"}]}
                if prov.with_usage:
                    resp["usage"] = {"prompt_tokens": est_tokens(json.dumps(messages)) + est_tokens(json.dumps(body.get("tools", []), separators=(",", ":"))),
                                     "completion_tokens": est_tokens(json.dumps(msg))}
                data = json.dumps(resp).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.httpd.daemon_threads = True
        self.url = f"http://127.0.0.1:{self.httpd.server_address[1]}/v1"
        self._thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *exc):
        self.httpd.shutdown()
        self.httpd.server_close()


def oracle_traces(shape_keys=("A", "B", "C")) -> dict:
    """Record the oracle's tool calls for every task and shape, against a fresh fake API."""
    from .harness import run_episode
    from .sessions import InProcessSession
    from .taskdesk.server import TaskDeskServer

    class Tracing(InProcessSession):
        def __init__(self, key, url):
            super().__init__(key, url)
            self.trace = []

        def _call(self, name, args):
            self.trace.append((name, args))
            return super()._call(name, args)

    traces = {}
    with TaskDeskServer() as server:
        for key in shape_keys:
            session = Tracing(key, server.url)
            for t in TASKS:
                session.trace = []
                run_episode(server, session, t, key, "oracle")
                traces[(t.id, key)] = list(session.trace)
    return traces
