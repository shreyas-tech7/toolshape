"""The record run is a resumable state machine over (task, shape, rep)."""

import json

import pytest

from toolcut.agent import ChatError, HttpChat
from toolcut.fake_provider import FakeProvider, oracle_traces
from toolcut.runner import DONE, FAILED, PENDING, RunConfig, RunState, fixture_path, run

TASK_IDS = ("t01", "t12")
SHAPES = ("A", "C")


@pytest.fixture(scope="module")
def traces():
    return oracle_traces()


def _cfg(tmp_path, **kw):
    return RunConfig(tmp_path / "run", model="fake", task_ids=TASK_IDS, shapes=SHAPES, reps=2, max_turns=50, **kw)


def test_new_state_has_every_item_pending(tmp_path):
    st = RunState.open(_cfg(tmp_path))
    assert len(st.items) == len(TASK_IDS) * len(SHAPES) * 2
    assert st.counts() == {PENDING: 8, DONE: 0, FAILED: 0}


def test_stop_then_resume_finishes_without_redoing_work(tmp_path, traces):
    cfg = _cfg(tmp_path)
    with FakeProvider(traces) as prov:
        first = run(cfg, lambda: HttpChat(prov.url, "fake"), limit=3, log=lambda *_: None)
        assert first.counts() == {PENDING: 5, DONE: 3, FAILED: 0}
        done_before = {k for k, v in first.items.items() if v["status"] == DONE}
        reqs = prov.requests
        second = run(cfg, lambda: HttpChat(prov.url, "fake"), log=lambda *_: None)
    assert second.counts() == {PENDING: 0, DONE: 8, FAILED: 0}
    assert all(second.items[k]["attempts"] == 1 for k in second.items)
    on_disk = json.loads((cfg.run_dir / "state.json").read_text())
    assert {k for k, v in on_disk["items"].items() if v["status"] == DONE} >= done_before
    assert prov.requests > reqs
    assert all(v["episode"]["passed"] for v in on_disk["items"].values())
    assert all(fixture_path(cfg.run_dir, k).exists() for k in on_disk["items"])


class Dies:
    """A chat client that fails after n requests, like a lost connection or a used-up quota."""

    calls = 0

    def __init__(self, inner, after):
        self.inner, self.after = inner, after

    def complete(self, payload):
        Dies.calls += 1
        if Dies.calls > self.after:
            raise ChatError("connection lost")
        return self.inner.complete(payload)


def test_failed_items_are_retried_on_the_next_run(tmp_path, traces):
    cfg = _cfg(tmp_path)
    Dies.calls = 0
    with FakeProvider(traces) as prov:
        st = run(cfg, lambda: Dies(HttpChat(prov.url, "fake"), after=4), log=lambda *_: None)
        c = st.counts()
        assert c[FAILED] > 0 and c[DONE] >= 1
        failed = [k for k, v in st.items.items() if v["status"] == FAILED]
        assert all("connection lost" in st.items[k]["error"] for k in failed)
        assert not any(fixture_path(cfg.run_dir, k).exists() for k in failed)
        st2 = run(cfg, lambda: HttpChat(prov.url, "fake"), log=lambda *_: None)
    assert st2.counts() == {PENDING: 0, DONE: 8, FAILED: 0}
    assert all(st2.items[k]["attempts"] == 2 for k in failed)


def test_gives_up_after_max_attempts(tmp_path, traces):
    cfg = _cfg(tmp_path, max_attempts=2)
    Dies.calls = 0
    with FakeProvider(traces) as prov:
        for _ in range(3):
            st = run(cfg, lambda: Dies(HttpChat(prov.url, "fake"), after=0), log=lambda *_: None)
    assert st.counts()[FAILED] == 8
    assert all(v["attempts"] == 2 for v in st.items.values())
    assert st.todo(cfg.max_attempts) == []


def test_replay_mode_reads_fixtures_offline(tmp_path, traces):
    cfg = _cfg(tmp_path)
    with FakeProvider(traces) as prov:
        rec = run(cfg, lambda: HttpChat(prov.url, "fake"), log=lambda *_: None)
    replay_cfg = RunConfig(cfg.run_dir, model="fake", mode="replay", task_ids=TASK_IDS, shapes=SHAPES, reps=2, max_turns=50)
    (cfg.run_dir / "state.json").rename(cfg.run_dir / "recorded.json")
    rep = run(replay_cfg, log=lambda *_: None)
    assert rep.counts()[DONE] == 8
    for k, v in rep.items.items():
        assert v["episode"]["passed"] == rec.items[k]["episode"]["passed"]
        assert v["episode"]["extra"]["prompt_tokens"] == rec.items[k]["episode"]["extra"]["prompt_tokens"]


def test_committed_scripted_run_is_complete():
    d = json.loads(open("runs/scripted/state.json").read())
    assert len(d["items"]) == 120
    assert all(v["status"] == DONE for v in d["items"].values())


def test_resume_refuses_a_different_model(tmp_path, traces):
    cfg = _cfg(tmp_path)
    with FakeProvider(traces) as prov:
        run(cfg, lambda: HttpChat(prov.url, "fake"), limit=1, log=lambda *_: None)
    other = RunConfig(cfg.run_dir, model="other", task_ids=TASK_IDS, shapes=SHAPES, reps=2, max_turns=50)
    with pytest.raises(ValueError, match="model"):
        RunState.open(other)


def test_resume_with_fewer_shapes_runs_only_those(tmp_path, traces):
    cfg = _cfg(tmp_path)
    with FakeProvider(traces) as prov:
        run(cfg, lambda: HttpChat(prov.url, "fake"), limit=1, log=lambda *_: None)
        only_c = RunConfig(cfg.run_dir, model="fake", task_ids=TASK_IDS, shapes=("C",), reps=2, max_turns=50)
        st = run(only_c, lambda: HttpChat(prov.url, "fake"), log=lambda *_: None)
    assert all(v["status"] == PENDING for k, v in st.items.items() if k.split("|")[1] == "A" and v["attempts"] == 0)
    assert all(v["status"] == DONE for k, v in st.items.items() if k.split("|")[1] == "C")


def test_replay_marks_a_missing_fixture_failed(tmp_path):
    cfg = RunConfig(tmp_path / "r", model="fake", mode="replay", task_ids=("t01",), shapes=("A",), max_turns=5)
    st = run(cfg, log=lambda *_: None)
    assert st.items["t01|A|0"]["status"] == FAILED and "no fixture" in st.items["t01|A|0"]["error"]


def test_replay_fails_when_recorded_exchanges_are_left_over(tmp_path, traces):
    """Broken case: a fixture with an extra exchange replays as done though the loop stopped early."""
    cfg = RunConfig(tmp_path / "r", model="fake", task_ids=("t01",), shapes=("A",), max_turns=50)
    with FakeProvider(traces) as prov:
        run(cfg, lambda: HttpChat(prov.url, "fake"), log=lambda *_: None)
    fpath = fixture_path(cfg.run_dir, "t01|A|0")
    d = json.loads(fpath.read_text())
    d["exchanges"].append(d["exchanges"][-1])
    fpath.write_text(json.dumps(d))
    (cfg.run_dir / "state.json").unlink()
    rcfg = RunConfig(cfg.run_dir, model="fake", mode="replay", task_ids=("t01",), shapes=("A",), max_turns=50)
    st = run(rcfg, log=lambda *_: None)
    assert st.items["t01|A|0"]["status"] == FAILED and "recorded exchanges" in st.items["t01|A|0"]["error"]
