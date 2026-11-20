"""A resumable record or replay run over (task, shape, rep).

State lives in runs/<run_id>/state.json. Each item is pending, done or failed. The file is
rewritten atomically after every item, so a killed run loses at most the item in flight.
Running the same command again skips done items and retries failed ones up to max_attempts.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

from .agent import Fixture, RecordingChat, ReplayChat, run_agent
from .harness import run_episode
from .sessions import open_session
from .taskdesk.server import TaskDeskServer
from .tasks import TASKS, TASKS_BY_ID

PENDING, DONE, FAILED = "pending", "done", "failed"


def item_key(task_id: str, shape: str, rep: int) -> str:
    return f"{task_id}|{shape}|{rep}"


@dataclass
class RunConfig:
    run_dir: Path
    model: str
    mode: str = "record"  # record or replay
    shapes: tuple[str, ...] = ("A", "B", "C")
    task_ids: tuple[str, ...] = tuple(t.id for t in TASKS)
    reps: int = 1
    transport: str = "inprocess"
    max_turns: int = 20
    max_attempts: int = 3
    provider_label: str = ""


class RunState:
    def __init__(self, path: Path, meta: dict, items: dict):
        self.path = path
        self.meta = meta
        self.items = items

    @classmethod
    def open(cls, cfg: RunConfig) -> RunState:
        path = cfg.run_dir / "state.json"
        keys = [item_key(t, s, r) for t in cfg.task_ids for s in cfg.shapes for r in range(cfg.reps)]
        if path.exists():
            d = json.loads(path.read_text())
            items = d["items"]
            for k in keys:
                items.setdefault(k, {"status": PENDING, "attempts": 0})
            return cls(path, d["meta"], items)
        meta = {"model": cfg.model, "mode": cfg.mode, "provider": cfg.provider_label, "transport": cfg.transport,
                "max_turns": cfg.max_turns, "created": time.strftime("%Y-%m-%d", time.gmtime())}
        return cls(path, meta, {k: {"status": PENDING, "attempts": 0} for k in keys})

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"meta": self.meta, "items": self.items}, indent=1, sort_keys=True))
        tmp.replace(self.path)

    def counts(self) -> dict:
        out = {PENDING: 0, DONE: 0, FAILED: 0}
        for it in self.items.values():
            out[it["status"]] += 1
        return out

    def todo(self, max_attempts: int) -> list[str]:
        return [k for k, it in self.items.items() if it["status"] == PENDING or (it["status"] == FAILED and it["attempts"] < max_attempts)]


def fixture_path(run_dir: Path, key: str) -> Path:
    return run_dir / "fixtures" / (key.replace("|", "-") + ".json")


def run(cfg: RunConfig, chat_factory=None, limit: int | None = None, log=print) -> RunState:
    """chat_factory() returns the live chat client for record mode. Replay mode reads fixtures."""
    state = RunState.open(cfg)
    state.save()
    todo = state.todo(cfg.max_attempts)
    if limit is not None:
        todo = todo[:limit]
    with TaskDeskServer() as server:
        sessions = {}
        try:
            for key in todo:
                task_id, shape, _rep = key.split("|")
                item = state.items[key]
                item["attempts"] += 1
                fpath = fixture_path(cfg.run_dir, key)
                if cfg.mode == "replay":
                    chat = ReplayChat(Fixture.load(fpath))
                    fixture = None
                else:
                    fixture = Fixture({"key": key, "model": cfg.model, "provider": cfg.provider_label})
                    chat = RecordingChat(chat_factory(), fixture)
                if shape not in sessions:
                    sessions[shape] = open_session(shape, server.url, cfg.transport)

                def agent(task, session, chat=chat):
                    return run_agent(task, session, chat, cfg.model, max_turns=cfg.max_turns)

                agent.name = "model"
                ep = run_episode(server, sessions[shape], TASKS_BY_ID[task_id], shape, agent)
                if ep.error:
                    item.update(status=FAILED, error=ep.error)
                    log(f"{key}: failed: {ep.error}")
                else:
                    item.update(status=DONE, episode=ep.as_dict(), error=None)
                    if fixture is not None:
                        fixture.save(fpath)
                    log(f"{key}: {'pass' if ep.passed else 'fail'} in {ep.tool_calls} calls")
                state.save()
        finally:
            for s in sessions.values():
                s.close()
    return state


def episodes(state_path: Path) -> list[dict]:
    d = json.loads(Path(state_path).read_text())
    return [it["episode"] for it in d["items"].values() if it["status"] == DONE]
