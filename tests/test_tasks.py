"""The 40 tasks and the end-state scorer."""

from collections import Counter

from toolcut.scorer import collateral, score
from toolcut.taskdesk.db import seed_data
from toolcut.tasks import TASKS, _busiest_project, _earliest_open, _top_commenter, world


def seed_world():
    return world({t: list(rows.values()) for t, rows in seed_data().items()})


def test_forty_tasks_with_unique_ids_and_mixed_categories():
    assert len(TASKS) == 40
    assert len({t.id for t in TASKS}) == 40
    cats = Counter(t.category for t in TASKS)
    assert set(cats) == {"single", "names", "multi", "bulk", "lookup"}
    assert all(t.prompt.strip() for t in TASKS)


def test_lookup_answers_are_unique_in_the_seed():
    w = seed_world()
    assert _top_commenter(w) and _busiest_project(w) and _earliest_open(w)


def test_unchanged_state_fails_every_task():
    """Broken case: a scorer that passes when nothing happened. Every task needs a change."""
    w = seed_world()
    failed = [t.id for t in TASKS if not score(t, w, w).passed]
    assert failed == [t.id for t in TASKS]


def test_collateral_catches_a_side_effect():
    """Broken case: the right change plus an extra edit to another row must fail."""
    before = seed_world()
    after = seed_world()
    after["tasks"][13]["status"] = "done"
    t01 = next(t for t in TASKS if t.id == "t01")
    assert score(t01, before, after).passed
    after["tasks"][2]["priority"] = "low"
    s = score(t01, before, after)
    assert not s.passed and any("side effect: tasks 2 changed (priority)" in r for r in s.reasons)


def test_new_rows_only_in_named_tables():
    before = seed_world()
    after = seed_world()
    after["tasks"][13]["status"] = "done"
    after["users"][99] = {"id": 99, "name": "x", "email": "x@x", "role": "member", "active": True}
    t01 = next(t for t in TASKS if t.id == "t01")
    assert any("new users rows" in r for r in collateral(t01, before, after))


def test_a_check_that_cannot_read_the_state_fails_cleanly():
    before = seed_world()
    after = seed_world()
    del after["tasks"][13]
    t01 = next(t for t in TASKS if t.id == "t01")
    s = score(t01, before, after)
    assert not s.passed and s.reasons
