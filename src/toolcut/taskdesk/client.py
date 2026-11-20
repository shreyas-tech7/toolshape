"""Typed TaskDesk client. One method per operation in ops.OPS. Standard library only.

This is the client that shape C's run_code scripts use, and that the harness uses to
call the API directly. It never reaches the admin routes.
"""

from __future__ import annotations

import http.client
import json
from urllib.parse import quote, urlencode, urlsplit

from .ops import OPS, Op


class TaskDeskError(Exception):
    """The API answered with an error. status is the HTTP status."""

    def __init__(self, status: int, message: str):
        super().__init__(f"{status}: {message}")
        self.status = status
        self.message = message


def _call(base_url: str, op: Op, kwargs: dict, timeout: float = 10.0):
    known = {p.name: p for p in op.params}
    unknown = set(kwargs) - set(known)
    if unknown:
        raise TypeError(f"{op.name}() got unexpected argument(s): {', '.join(sorted(unknown))}")
    path = op.path
    query, body = {}, {}
    for p in op.params:
        if p.name not in kwargs:
            if p.required:
                raise TypeError(f"{op.name}() missing required argument: {p.name}")
            continue
        v = kwargs[p.name]
        if v is None and p.type != "integer_or_null":
            continue
        if p.where == "path":
            path = path.replace("{" + p.name + "}", quote(str(v), safe=""))
        elif p.where == "query":
            query[p.name] = str(v).lower() if isinstance(v, bool) else v
        else:
            body[p.name] = v
    if query:
        path += "?" + urlencode(query)
    url = urlsplit(base_url)
    conn = http.client.HTTPConnection(url.hostname, url.port, timeout=timeout)
    try:
        data = json.dumps(body).encode() if op.method in ("POST", "PATCH") else None
        headers = {"Content-Type": "application/json"} if data is not None else {}
        conn.request(op.method, path, body=data, headers=headers)
        resp = conn.getresponse()
        payload = json.loads(resp.read() or b"null")
    finally:
        conn.close()
    if resp.status >= 400:
        raise TaskDeskError(resp.status, payload.get("error", "error") if isinstance(payload, dict) else str(payload))
    return payload


def _method(op: Op):
    def method(self, **kwargs):
        return _call(self.base_url, op, kwargs)

    method.__name__ = op.name
    method.__doc__ = op.summary
    return method


class TaskDesk:
    """TaskDesk client. Example: TaskDesk(url).list_tasks(status="todo", page=2)."""

    def __init__(self, base_url: str):
        self.base_url = base_url

    def call(self, name: str, args: dict):
        """Call an operation by name with a dict of arguments."""
        op = next((o for o in OPS if o.name == name), None)
        if op is None:
            raise TaskDeskError(404, f"unknown operation {name}")
        return _call(self.base_url, op, args)


for _op in OPS:
    setattr(TaskDesk, _op.name, _method(_op))


def admin_dump(base_url: str, token: str) -> dict:
    """Read the whole database. Harness only. Needs the per-run admin token."""
    url = urlsplit(base_url)
    conn = http.client.HTTPConnection(url.hostname, url.port, timeout=10)
    try:
        conn.request("GET", "/_admin/dump", headers={"X-Admin-Token": token})
        resp = conn.getresponse()
        payload = json.loads(resp.read())
    finally:
        conn.close()
    if resp.status != 200:
        raise TaskDeskError(resp.status, payload.get("error", "error"))
    return payload
