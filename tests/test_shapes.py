"""The three shapes, one by one. Names carry shape_a, shape_b and shape_c for -k selection."""

import json

from toolcut.shapes import ShapeA, ShapeB, ShapeC
from toolcut.shapes.shape_c import search
from toolcut.taskdesk.ops import OPS


def test_shape_a_has_one_tool_per_operation(api):
    a = ShapeA(api.url)
    assert [t["name"] for t in a.list_tools()] == [op.name for op in OPS]
    r = a.call_tool("get_task", {"task_id": 3})
    assert not r.is_error and json.loads(r.text)["id"] == 3


def test_shape_a_errors_come_back_as_text(api):
    a = ShapeA(api.url)
    r = a.call_tool("get_task", {"task_id": 999})
    assert r.is_error and json.loads(r.text)["status"] == 404
    assert a.call_tool("no_such_tool", {}).is_error
    assert a.call_tool("get_task", {"task_id": 1, "extra": 1}).is_error


def test_shape_b_has_fewer_task_sized_tools(api):
    b = ShapeB(api.url)
    names = [t["name"] for t in b.list_tools()]
    assert 5 <= len(names) < len(OPS)
    r = json.loads(b.call_tool("find_tasks", {"assignee": "Priya Raman", "overdue": True}).text)
    assert r["count"] == len(r["tasks"]) >= 1
    assert all(t["assignee"] == "Priya Raman" and t["due"] < "2026-03-15" and t["status"] != "done" for t in r["tasks"])


def test_shape_b_find_tasks_reads_every_page(api):
    b = ShapeB(api.url)
    r = json.loads(b.call_tool("find_tasks", {}).text)
    assert r["count"] == 72 and len(r["tasks"]) == 72


def test_shape_b_resolves_names_and_reports_ambiguity(api):
    b = ShapeB(api.url)
    assert json.loads(b.call_tool("users", {"action": "get", "user": "grace liu"}).text)["id"] == 9
    r = b.call_tool("users", {"action": "get", "user": "a"})
    assert r.is_error and "matched" in r.text
    r = b.call_tool("comments", {"action": "add", "task_id": 1})
    assert r.is_error and "needs" in r.text


def test_shape_b_bulk_update_stops_and_reports(api):
    b = ShapeB(api.url)
    r = b.call_tool("update_tasks", {"task_ids": [1, 999], "status": "done"})
    assert r.is_error and "task 999" in r.text and "[1]" in r.text


def test_shape_c_has_two_tools(api):
    c = ShapeC(api.url)
    assert [t["name"] for t in c.list_tools()] == ["search_api", "run_code"]


def test_shape_c_search_api_ranks_by_name():
    hits = search("assign task")
    assert hits[0]["method"] == "assign_task" and "assignee_id" in hits[0]["signature"]
    assert len(search("*", 1)) == len(OPS)


def test_shape_c_run_code_uses_the_typed_client(api):
    c = ShapeC(api.url)
    r = c.call_tool("run_code", {"code": "r = taskdesk.list_tasks(status='done')\nprint(r['total'])"})
    assert not r.is_error and r.text.strip().isdigit()
    r = c.call_tool("run_code", {"code": "taskdesk.get_task(task_id=999)"})
    assert r.is_error and "404" in r.text
    assert c.call_tool("run_code", {"code": 1}).is_error
