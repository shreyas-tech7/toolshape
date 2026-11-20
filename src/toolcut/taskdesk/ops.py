"""The TaskDesk operation list. It is the single source of truth for the API.

The HTTP server routes by it, the typed client is built from it, and every tool shape
must reach every operation in it (see tests/test_capability_matrix.py).
"""

from __future__ import annotations

from dataclasses import dataclass, field

PAGE_SIZE = 20
STATUSES = ["todo", "in_progress", "done"]
PRIORITIES = ["low", "medium", "high", "urgent"]
ROLES = ["member", "admin"]


@dataclass(frozen=True)
class Param:
    name: str
    type: str  # integer | string | boolean | date | integer_or_null
    where: str  # path | query | body
    required: bool = False
    description: str = ""
    enum: tuple[str, ...] = ()


@dataclass(frozen=True)
class Op:
    name: str
    method: str
    path: str
    summary: str
    params: tuple[Param, ...] = field(default_factory=tuple)
    writes: bool = False


def P(name, type_, where, required=False, description="", enum=()):
    return Param(name, type_, where, required, description, tuple(enum))


_TID = P("task_id", "integer", "path", True, "Task id.")
_PID = P("project_id", "integer", "path", True, "Project id.")
_UID = P("user_id", "integer", "path", True, "User id.")
_CID = P("comment_id", "integer", "path", True, "Comment id.")
_PAGE = P("page", "integer", "query", False, f"Page number, starting at 1. Each page holds at most {PAGE_SIZE} items.")

OPS: tuple[Op, ...] = (
    Op("list_users", "GET", "/users", "List users.", (P("active", "boolean", "query", False, "Only active (true) or only deactivated (false) users."),)),
    Op("get_user", "GET", "/users/{user_id}", "Get one user.", (_UID,)),
    Op("create_user", "POST", "/users", "Create a user.", (
        P("name", "string", "body", True, "Full name."),
        P("email", "string", "body", True, "Email address. Must be unique."),
        P("role", "string", "body", False, "Role. Default member.", ROLES)), True),
    Op("update_user", "PATCH", "/users/{user_id}", "Change a user's name, email or role.", (
        _UID, P("name", "string", "body"), P("email", "string", "body"), P("role", "string", "body", False, "", ROLES)), True),
    Op("deactivate_user", "POST", "/users/{user_id}/deactivate", "Deactivate a user. Deactivated users cannot be assigned tasks.", (_UID,), True),
    Op("list_projects", "GET", "/projects", "List projects.", (P("status", "string", "query", False, "Filter by status.", ["active", "archived"]),)),
    Op("get_project", "GET", "/projects/{project_id}", "Get one project.", (_PID,)),
    Op("create_project", "POST", "/projects", "Create a project. The owner becomes its first member.", (
        P("name", "string", "body", True, "Project name. Must be unique."),
        P("owner_id", "integer", "body", True, "User id of the owner."),
        P("description", "string", "body", False, "Short description.")), True),
    Op("update_project", "PATCH", "/projects/{project_id}", "Change a project's name, description or owner.", (
        _PID, P("name", "string", "body"), P("description", "string", "body"), P("owner_id", "integer", "body")), True),
    Op("archive_project", "POST", "/projects/{project_id}/archive", "Archive a project. Archived projects take no new tasks.", (_PID,), True),
    Op("list_project_members", "GET", "/projects/{project_id}/members", "List the users who are members of a project.", (_PID,)),
    Op("add_project_member", "POST", "/projects/{project_id}/members", "Add a user to a project.", (
        _PID, P("user_id", "integer", "body", True, "User id to add.")), True),
    Op("list_tasks", "GET", "/tasks", f"List tasks, newest id last, {PAGE_SIZE} per page. Filters combine with AND.", (
        P("project_id", "integer", "query", False, "Only tasks in this project."),
        P("assignee_id", "integer", "query", False, "Only tasks assigned to this user."),
        P("status", "string", "query", False, "Only tasks with this status.", STATUSES),
        P("label", "string", "query", False, "Only tasks that carry this label."),
        P("due_before", "date", "query", False, "Only tasks due strictly before this date (YYYY-MM-DD)."),
        _PAGE)),
    Op("get_task", "GET", "/tasks/{task_id}", "Get one task.", (_TID,)),
    Op("create_task", "POST", "/tasks", "Create a task in a project.", (
        P("project_id", "integer", "body", True, "Project id."),
        P("title", "string", "body", True, "Title."),
        P("description", "string", "body", False, "Description."),
        P("assignee_id", "integer", "body", False, "User id. Must be an active member of the project."),
        P("due", "date", "body", False, "Due date, YYYY-MM-DD."),
        P("priority", "string", "body", False, "Default medium.", PRIORITIES)), True),
    Op("update_task", "PATCH", "/tasks/{task_id}", "Change a task's title, description, status, priority or due date.", (
        _TID, P("title", "string", "body"), P("description", "string", "body"),
        P("status", "string", "body", False, "", STATUSES), P("priority", "string", "body", False, "", PRIORITIES),
        P("due", "date", "body", False, "Due date, YYYY-MM-DD.")), True),
    Op("delete_task", "DELETE", "/tasks/{task_id}", "Delete a task and its comments.", (_TID,), True),
    Op("assign_task", "POST", "/tasks/{task_id}/assign", "Assign a task, or unassign it with null.", (
        _TID, P("assignee_id", "integer_or_null", "body", True, "User id, or null to unassign. Must be an active member of the task's project.")), True),
    Op("add_label", "POST", "/tasks/{task_id}/labels", "Add a label to a task.", (_TID, P("label", "string", "body", True, "Label text, lowercase.")), True),
    Op("remove_label", "DELETE", "/tasks/{task_id}/labels/{label}", "Remove a label from a task.", (_TID, P("label", "string", "path", True, "Label text.")), True),
    Op("list_comments", "GET", "/tasks/{task_id}/comments", "List a task's comments, oldest first.", (_TID,)),
    Op("add_comment", "POST", "/tasks/{task_id}/comments", "Add a comment to a task.", (
        _TID, P("body", "string", "body", True, "Comment text."), P("author_id", "integer", "body", True, "User id of the author.")), True),
    Op("update_comment", "PATCH", "/comments/{comment_id}", "Change a comment's text.", (_CID, P("body", "string", "body", True, "New text.")), True),
    Op("delete_comment", "DELETE", "/comments/{comment_id}", "Delete a comment.", (_CID,), True),
    Op("search_tasks", "GET", "/search", f"Find tasks whose title or description contains the text, case-insensitive, {PAGE_SIZE} per page.", (
        P("query", "string", "query", True, "Text to look for."), _PAGE)),
)

OPS_BY_NAME = {op.name: op for op in OPS}

_JSON_TYPES = {
    "integer": {"type": "integer"},
    "string": {"type": "string"},
    "boolean": {"type": "boolean"},
    "date": {"type": "string", "pattern": r"^\d{4}-\d{2}-\d{2}$"},
    "integer_or_null": {"type": ["integer", "null"]},
}


def param_schema(p: Param) -> dict:
    s = dict(_JSON_TYPES[p.type])
    if p.description:
        s["description"] = p.description
    if p.enum:
        s["enum"] = list(p.enum)
    return s


def input_schema(op: Op) -> dict:
    return {
        "type": "object",
        "properties": {p.name: param_schema(p) for p in op.params},
        "required": [p.name for p in op.params if p.required],
        "additionalProperties": False,
    }


_PY_TYPES = {"integer": "int", "string": "str", "boolean": "bool", "date": "str", "integer_or_null": "int | None"}


def signature(op: Op) -> str:
    """Python signature text for the typed client method, shown by search_api."""
    req = [f"{p.name}: {_PY_TYPES[p.type]}" for p in op.params if p.required]
    opt = [f"{p.name}: {_PY_TYPES[p.type]} | None = None" for p in op.params if not p.required]
    return f"taskdesk.{op.name}({', '.join(req + opt)}) -> dict"
