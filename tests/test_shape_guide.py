"""The shape guide's example works: register a fourth shape and the harness runs it unchanged."""

import json
from pathlib import Path

import pytest

from toolcut import oracle, shapes
from toolcut.harness import run_episode
from toolcut.oracle import ToolProxy
from toolcut.sessions import InProcessSession
from toolcut.shapes.example_grouped import ShapeD, group_of
from toolcut.taskdesk.ops import OPS
from toolcut.tasks import TASKS

GUIDE = Path("docs/ADDING_A_SHAPE.md")


class GroupedProxy(ToolProxy):
    """Same client-like object as ToolProxy, but each method goes through shape D's resource tools."""

    def __getattr__(self, op_name):
        def call(**kwargs):
            return oracle._parse(self.session.call(group_of(op_name), {"operation": op_name, "args": kwargs}))

        return call


@pytest.fixture
def shape_d(monkeypatch):
    monkeypatch.setitem(shapes.SHAPES, "D", ShapeD)
    real = oracle.run_plan

    def run_plan(plan_id, shape_key, session):
        if shape_key == "D":
            ns = {"taskdesk": GroupedProxy(session)}
            exec(compile(oracle.HELPERS_SOURCE, "oracle_helpers.py", "exec"), ns)  # noqa: S102 - our own file
            return getattr(oracle.solutions, plan_id)(ns["H"])
        return real(plan_id, shape_key, session)

    monkeypatch.setattr("toolcut.harness.run_plan", run_plan)


def test_every_operation_has_a_group():
    tools = {t["name"]: t for t in ShapeD("http://127.0.0.1:1").tools()}
    covered = [o for t in tools.values() for o in t["inputSchema"]["properties"]["operation"]["enum"]]
    assert sorted(covered) == sorted(op.name for op in OPS)


def test_wrong_group_is_an_error(api):
    r = ShapeD(api.url).call_tool("users", {"operation": "delete_task", "args": {"task_id": 1}})
    assert r.is_error


def test_oracle_and_noop_through_the_example_shape(api, shape_d):
    with InProcessSession("D", api.url) as s:
        good = [run_episode(api, s, t, "D", "oracle") for t in TASKS]
        bad = [run_episode(api, s, t, "D", "noop") for t in TASKS]
    assert [r.task for r in good if not r.passed] == []
    assert not any(r.passed for r in bad)


def test_example_shape_size_is_measurable(api):
    n = len(json.dumps(ShapeD(api.url).tools(), separators=(",", ":"), sort_keys=True))
    assert 1000 < n < 20000


def test_guide_names_every_step():
    text = GUIDE.read_text()
    for needle in ("class ShapeD", "SHAPES", "run_plan", "test_capability_matrix", "toolcut sizes", "toolcut oracle", "toolcut readme"):
        assert needle in text, needle
