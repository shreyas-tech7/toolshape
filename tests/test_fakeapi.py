"""TaskDesk fake API: routes, seeded data, validation and the admin dump."""

import pytest

from toolcut.taskdesk.client import TaskDesk, TaskDeskError, admin_dump
from toolcut.taskdesk.db import DB, TODAY, seed_data
from toolcut.taskdesk.ops import OPS, PAGE_SIZE


def test_about_25_operations_over_four_resources():
    assert len(OPS) == 25
    names = {op.name for op in OPS}
    for word in ("user", "project", "task", "comment"):
        assert any(word in n for n in names)
    assert len(names) == 25


def test_every_op_has_a_db_method():
    db = DB()
    for op in OPS:
        assert callable(getattr(db, "op_" + op.name))


def test_seed_is_deterministic():
    assert seed_data() == seed_data()
    assert seed_data(1) != seed_data()


def test_list_tasks_paginates(api):
    c = TaskDesk(api.url)
    first = c.list_tasks()
    assert len(first["items"]) == PAGE_SIZE and first["next_page"] == 2
    seen = [t["id"] for t in first["items"]]
    page = first["next_page"]
    while page:
        r = c.list_tasks(page=page)
        seen += [t["id"] for t in r["items"]]
        page = r["next_page"]
    assert seen == sorted(seen) and len(seen) == first["total"] == 72


def test_filters_combine(api):
    c = TaskDesk(api.url)
    r = c.list_tasks(project_id=1, status="todo")
    assert r["items"] and all(t["project_id"] == 1 and t["status"] == "todo" for t in r["items"])
    r = c.list_tasks(due_before=TODAY)
    assert all(t["due"] and t["due"] < TODAY for t in r["items"])


def test_assign_rules(api):
    c = TaskDesk(api.url)
    task = c.create_task(project_id=1, title="New thing")
    assert task["created_at"] == TODAY and task["status"] == "todo"
    with pytest.raises(TaskDeskError) as e:
        c.assign_task(task_id=task["id"], assignee_id=10)
    assert e.value.status == 400 and "deactivated" in e.value.message
    outsider = next(u for u in range(1, 10) if u not in c.get_project(project_id=1)["members"])
    with pytest.raises(TaskDeskError, match="not a member"):
        c.assign_task(task_id=task["id"], assignee_id=outsider)
    c.add_project_member(project_id=1, user_id=outsider)
    assert c.assign_task(task_id=task["id"], assignee_id=outsider)["assignee_id"] == outsider
    assert c.assign_task(task_id=task["id"], assignee_id=None)["assignee_id"] is None


def test_errors_are_json_with_status(api):
    c = TaskDesk(api.url)
    with pytest.raises(TaskDeskError) as e:
        c.get_task(task_id=9999)
    assert e.value.status == 404
    with pytest.raises(TaskDeskError, match="must be one of"):
        c.update_task(task_id=1, status="later")
    with pytest.raises(TaskDeskError, match="archived"):
        c.create_task(project_id=6, title="x")
    with pytest.raises(TypeError):
        c.get_task(task_id=1, color="red")


def test_delete_task_removes_its_comments(api):
    c = TaskDesk(api.url)
    tid = next(t for t in range(1, 73) if c.list_comments(task_id=t)["items"])
    c.delete_task(task_id=tid)
    dump = admin_dump(api.url, api.admin_token)["data"]
    assert not any(x["task_id"] == tid for x in dump["comments"])


def test_admin_needs_the_token(api):
    with pytest.raises(TaskDeskError) as e:
        admin_dump(api.url, "wrong")
    assert e.value.status == 403
    d = admin_dump(api.url, api.admin_token)
    assert len(d["data"]["tasks"]) == 72


def test_search_and_labels(api):
    c = TaskDesk(api.url)
    r = c.search_tasks(query="CRASH")
    assert r["items"] and all("crash" in t["title"].lower() for t in r["items"])
    t = c.add_label(task_id=1, label="Needs-QA")
    assert "needs-qa" in t["labels"]
    assert "needs-qa" not in c.remove_label(task_id=1, label="needs-qa")["labels"]
