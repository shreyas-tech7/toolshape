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


def _t(task_id):
    return next(t for t in TASKS if t.id == task_id)


def test_every_task_that_touches_rows_lists_its_fields():
    from toolcut.tasks import FIELDS

    w = seed_world()
    for t in TASKS:
        for table, ids in t.touch(w).items():
            if ids:
                assert table in FIELDS.get(t.id, {}), (t.id, table)


def test_extra_field_on_an_allowed_row_fails():
    """Outside check finding: the right change plus a new title on the same task passed."""
    before, after = seed_world(), seed_world()
    after["tasks"][13]["status"] = "done"
    after["tasks"][13]["title"] = "renamed"
    s = score(_t("t01"), before, after)
    assert not s.passed and any("field title changed" in r for r in s.reasons)


def test_extra_member_or_rename_on_the_project_fails():
    from toolcut.tasks import pid, uid

    before = seed_world()
    p, grace = pid(before, "Mobile App"), uid(before, "Grace Liu")
    after = seed_world()
    after["projects"][p]["members"] = sorted(set(after["projects"][p]["members"]) | {grace})
    assert score(_t("t15"), before, after).passed
    renamed = seed_world()
    renamed["projects"][p]["members"] = sorted(set(renamed["projects"][p]["members"]) | {grace})
    renamed["projects"][p]["name"] = "Other"
    assert not score(_t("t15"), before, renamed).passed
    removed = seed_world()
    removed["projects"][p]["members"] = [grace]
    assert not score(_t("t15"), before, removed).passed


def test_extra_label_fails():
    before, after = seed_world(), seed_world()
    after["tasks"][24]["labels"] = sorted(set(after["tasks"][24]["labels"]) | {"security", "other"})
    assert not score(_t("t04"), before, after).passed


def test_id_list_answer_must_be_ids_only():
    from toolcut.tasks import id_list

    assert id_list("2, 24,65") == [2, 24, 65]
    assert id_list("Urgent ids: 2 and 24") is None
    assert id_list("") is None
