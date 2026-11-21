"""Capability matrix: every API operation is reachable through every shape, with the same
effect on the database. Reads must return the same rows."""

import json

import pytest

from toolcut.shapes import ShapeA, ShapeB, ShapeC
from toolcut.taskdesk.client import TaskDesk, admin_dump
from toolcut.taskdesk.ops import OPS

# operation -> (direct API arguments, shape B tool, shape B arguments)
MATRIX = {
    "list_users": ({}, "users", {"action": "list"}),
    "get_user": ({"user_id": 1}, "users", {"action": "get", "user": 1}),
    "create_user": ({"name": "Ivy Chen", "email": "ivy@taskdesk.test"}, "users", {"action": "create", "name": "Ivy Chen", "email": "ivy@taskdesk.test"}),
    "update_user": ({"user_id": 2, "role": "admin"}, "users", {"action": "update", "user": 2, "role": "admin"}),
    "deactivate_user": ({"user_id": 8}, "users", {"action": "deactivate", "user": 8}),
    "list_projects": ({}, "projects", {"action": "list"}),
    "get_project": ({"project_id": 1}, "projects", {"action": "get", "project": 1}),
    "create_project": ({"name": "New One", "owner_id": 1}, "projects", {"action": "create", "name": "New One", "owner": 1}),
    "update_project": ({"project_id": 1, "name": "Renamed"}, "projects", {"action": "update", "project": 1, "name": "Renamed"}),
    "archive_project": ({"project_id": 2}, "projects", {"action": "archive", "project": 2}),
    "list_project_members": ({"project_id": 1}, "projects", {"action": "members", "project": 1}),
    "add_project_member": ({"project_id": 1, "user_id": 9}, "projects", {"action": "add_member", "project": 1, "user": 9}),
    "list_tasks": ({"project_id": 1}, "find_tasks", {"project": 1}),
    "get_task": ({"task_id": 5}, "get_task_details", {"task_id": 5}),
    "create_task": ({"project_id": 1, "title": "T"}, "create_task", {"project": 1, "title": "T"}),
    "update_task": ({"task_id": 5, "status": "done"}, "update_tasks", {"task_ids": [5], "status": "done"}),
    "delete_task": ({"task_id": 5}, "delete_tasks", {"task_ids": [5]}),
    "assign_task": ({"task_id": 5, "assignee_id": 1}, "update_tasks", {"task_ids": [5], "assignee": 1}),
    "add_label": ({"task_id": 5, "label": "x"}, "update_tasks", {"task_ids": [5], "add_labels": ["x"]}),
    "remove_label": ({"task_id": 5, "label": "design"}, "update_tasks", {"task_ids": [5], "remove_labels": ["design"]}),
    "list_comments": ({"task_id": 37}, "comments", {"action": "list", "task_id": 37}),
    "add_comment": ({"task_id": 5, "body": "hi", "author_id": 1}, "comments", {"action": "add", "task_id": 5, "body": "hi", "author": 1}),
    "update_comment": ({"comment_id": 1, "body": "b"}, "comments", {"action": "edit", "comment_id": 1, "body": "b"}),
    "delete_comment": ({"comment_id": 1}, "comments", {"action": "delete", "comment_id": 1}),
    "search_tasks": ({"query": "crash"}, "find_tasks", {"text": "crash"}),
}


def ids(obj) -> set:
    found = set()
    if isinstance(obj, dict):
        if "id" in obj:
            found.add(obj["id"])
        for v in obj.values():
            found |= ids(v)
    elif isinstance(obj, list):
        for v in obj:
            found |= ids(v)
    return found


def test_matrix_covers_every_operation():
    assert set(MATRIX) == {op.name for op in OPS}


def _via(shape_key, url, op_name):
    direct_args, b_tool, b_args = MATRIX[op_name]
    if shape_key == "A":
        r = ShapeA(url).call_tool(op_name, direct_args)
    elif shape_key == "B":
        r = ShapeB(url).call_tool(b_tool, b_args)
    else:
        code = f"import json\nprint(json.dumps(taskdesk.{op_name}(**{direct_args!r})))"
        r = ShapeC(url).call_tool("run_code", {"code": code})
    assert not r.is_error, r.text
    return json.loads(r.text)


@pytest.mark.parametrize("shape_key", ["A", "B", "C"])
@pytest.mark.parametrize("op_name", sorted(MATRIX))
def test_same_effect_in_every_shape(api, shape_key, op_name):
    direct = TaskDesk(api.url).call(op_name, MATRIX[op_name][0])
    want = admin_dump(api.url, api.admin_token)["data"]
    api.reset()
    out = _via(shape_key, api.url, op_name)
    assert admin_dump(api.url, api.admin_token)["data"] == want
    if op_name.startswith(("list_", "get_", "search_")):
        assert ids(direct) and ids(direct) <= ids(out)
