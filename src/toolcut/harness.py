"""Run one episode: reset the fake API, run an agent on a task in a shape, score the end state."""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field

from .oracle import plan_for, run_plan
from .scorer import score
from .sessions import Session
from .taskdesk.client import admin_dump
from .taskdesk.server import TaskDeskServer
from .tasks import Task, world


@dataclass
class Episode:
    task: str
    shape: str
    agent: str
    passed: bool
    reasons: list[str]
    tool_calls: int
    tool_errors: int
    arg_bytes: int
    result_bytes: int
    api_calls: int
    seconds: float
    error: str | None = None
    extra: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return asdict(self)


def run_episode(server: TaskDeskServer, session: Session, task: Task, shape_key: str, agent) -> Episode:
    """agent is "oracle", "noop", "swap", or a callable(task, session) that drives the session."""
    server.reset()
    before = world(admin_dump(server.url, server.admin_token)["data"])
    start_log = len(session.log)
    error = None
    extra = {}
    name = getattr(agent, "name", "model") if callable(agent) else agent
    t0 = time.perf_counter()
    try:
        if callable(agent):
            extra = agent(task, session) or {}
        else:
            plan = plan_for(agent, task)
            if plan is not None:
                run_plan(plan, shape_key, session)
    except Exception as e:  # noqa: BLE001 - a failed episode is a result, not a crash
        error = f"{type(e).__name__}: {e}"[:500]
    seconds = time.perf_counter() - t0
    dump = admin_dump(server.url, server.admin_token)
    s = score(task, before, world(dump["data"]))
    calls = session.log[start_log:]
    return Episode(task.id, shape_key, name, s.passed, s.reasons[:10], len(calls), sum(c.is_error for c in calls),
                   sum(c.arg_bytes for c in calls), sum(c.result_bytes for c in calls), len(dump["calls"]),
                   round(seconds, 4), error, extra)
