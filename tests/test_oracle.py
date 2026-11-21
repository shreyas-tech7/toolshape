"""The oracle solves all 40 tasks in all three shapes. The wrong agents fail all of them."""

import pytest

from toolcut.harness import run_episode
from toolcut.oracle import shape_c_script
from toolcut.sandbox import check_script
from toolcut.sessions import McpSession, open_session
from toolcut.tasks import TASKS


@pytest.mark.parametrize("shape_key", ["A", "B", "C"])
def test_oracle_passes_and_wrong_agents_fail(api, shape_key):
    with open_session(shape_key, api.url) as session:
        for agent, want in (("oracle", True), ("noop", False), ("swap", False)):
            results = [run_episode(api, session, t, shape_key, agent) for t in TASKS]
            wrong = [(r.task, r.reasons[:1], r.error) for r in results if r.passed != want]
            assert not wrong, f"{agent} in shape {shape_key}: {wrong}"


def test_shape_c_scripts_pass_the_sandbox_rules():
    for t in TASKS:
        check_script(shape_c_script(t.id))


@pytest.mark.parametrize("shape_key", ["A", "B", "C"])
def test_oracle_over_real_mcp(api, shape_key):
    with McpSession(shape_key, api.url) as session:
        for t in TASKS[::8]:
            r = run_episode(api, session, t, shape_key, "oracle")
            assert r.passed, (t.id, r.reasons, r.error)
