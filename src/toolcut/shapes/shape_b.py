"""Shape B: a few task-sized tools.

The tools take names as well as ids, fetch every page for you, and fold several API calls
into one. They reach exactly the same operations as shape A and nothing more
(tests/test_capability_matrix.py checks this).
"""

from __future__ import annotations

from ..taskdesk.client import TaskDesk, TaskDeskError
from ..taskdesk.db import TODAY
from ..taskdesk.ops import PRIORITIES, ROLES, STATUSES
from .base import Shape

REF = {"type": ["string", "integer"]}
STR = {"type": "string"}
INT = {"type": "integer"}
DATE = {"type": "string", "pattern": r"^\d{4}-\d{2}-\d{2}$"}
MAX_ROWS = 100


def _obj(props: dict, required: list[str] | None = None) -> dict:
    return {"type": "object", "properties": props, "required": required or [], "additionalProperties": False}


def _d(schema: dict, description: str) -> dict:
    return {**schema, "description": description}


TOOLS = [
    {"name": "find_tasks", "description": (
        f"Find tasks. Every filter is optional and they combine with AND. Returns all matches (up to {MAX_ROWS}) "
        "with project and assignee names, so no paging is needed. Use get_task_details for descriptions and comments."),
     "inputSchema": _obj({
         "project": _d(REF, "Project name or id."),
         "assignee": _d(REF, 'User name, email or id. Use "none" for unassigned tasks.'),
         "status": _d({"type": "string", "enum": STATUSES}, "Status."),
         "priority": _d({"type": "string", "enum": PRIORITIES}, "Priority."),
         "label": _d(STR, "Label."),
         "overdue": _d({"type": "boolean"}, f"true: only tasks due before today ({TODAY}) that are not done."),
         "due_before": _d(DATE, "Only tasks due strictly before this date."),
         "text": _d(STR, "Text that the title or description contains, case-insensitive."),
     })},
    {"name": "get_task_details", "description": "Get one task with its description, project, assignee and all comments.",
     "inputSchema": _obj({"task_id": INT}, ["task_id"])},
    {"name": "create_task", "description": "Create a task, and optionally assign it and label it, in one call. The assignee must be an active project member.",
     "inputSchema": _obj({
         "project": _d(REF, "Project name or id."), "title": STR, "description": STR,
         "assignee": _d(REF, "User name, email or id."), "due": _d(DATE, "Due date."),
         "priority": {"type": "string", "enum": PRIORITIES}, "labels": {"type": "array", "items": STR},
     }, ["project", "title"])},
    {"name": "update_tasks", "description": (
        "Change one or more tasks in one call. Every field is optional. assignee takes a user name, email or id, "
        'or "none" to unassign. The assignee must be an active member of each task\'s project.'),
     "inputSchema": _obj({
         "task_ids": {"type": "array", "items": INT, "minItems": 1},
         "status": {"type": "string", "enum": STATUSES}, "priority": {"type": "string", "enum": PRIORITIES},
         "due": DATE, "title": STR, "description": STR, "assignee": REF,
         "add_labels": {"type": "array", "items": STR}, "remove_labels": {"type": "array", "items": STR},
     }, ["task_ids"])},
    {"name": "delete_tasks", "description": "Delete one or more tasks and their comments.",
     "inputSchema": _obj({"task_ids": {"type": "array", "items": INT, "minItems": 1}}, ["task_ids"])},
    {"name": "comments", "description": "List, add, edit or delete comments. list and add need task_id. edit and delete need comment_id. add needs author (user name, email or id) and body.",
     "inputSchema": _obj({
         "action": {"type": "string", "enum": ["list", "add", "edit", "delete"]},
         "task_id": INT, "comment_id": INT, "body": STR, "author": REF,
     }, ["action"])},
    {"name": "projects", "description": (
        "Work with projects. list (optional status), get, members, create (name, owner, optional description), "
        "update (name, description, owner), archive, add_member (user). project takes a name or id."),
     "inputSchema": _obj({
         "action": {"type": "string", "enum": ["list", "get", "members", "create", "update", "archive", "add_member"]},
         "project": REF, "name": STR, "description": STR, "owner": REF, "user": REF,
         "status": {"type": "string", "enum": ["active", "archived"]},
     }, ["action"])},
    {"name": "users", "description": "Work with users. list (optional active), get, create (name, email, optional role), update (name, email, role), deactivate. user takes a name, email or id.",
     "inputSchema": _obj({
         "action": {"type": "string", "enum": ["list", "get", "create", "update", "deactivate"]},
         "user": REF, "name": STR, "email": STR, "role": {"type": "string", "enum": ROLES}, "active": {"type": "boolean"},
     }, ["action"])},
]


class ShapeB(Shape):
    key = "B"
    title = "Task-sized tools"

    def __init__(self, api_url: str):
        super().__init__(api_url)
        self.td = TaskDesk(api_url)

    def tools(self) -> list[dict]:
        return TOOLS

    def dispatch(self, name: str, args: dict) -> object:
        return getattr(self, "t_" + name)(**args)

    # name resolution
    def user_id(self, ref) -> int:
        if isinstance(ref, int) or (isinstance(ref, str) and ref.strip().isdigit()):
            return self.td.get_user(user_id=int(ref))["id"]
        users = self.td.list_users()["items"]
        key = str(ref).strip().lower()
        hits = [u for u in users if u["email"].lower() == key or u["name"].lower() == key]
        if not hits:
            hits = [u for u in users if key in u["name"].lower()]
        if len(hits) != 1:
            names = ", ".join(u["name"] for u in hits) or "none"
            raise TaskDeskError(404 if not hits else 400, f"user {ref!r} matched {len(hits)} users ({names})")
        return hits[0]["id"]

    def project_id(self, ref) -> int:
        if isinstance(ref, int) or (isinstance(ref, str) and ref.strip().isdigit()):
            return self.td.get_project(project_id=int(ref))["id"]
        hits = [p for p in self.td.list_projects()["items"] if p["name"].lower() == str(ref).strip().lower()]
        if len(hits) != 1:
            raise TaskDeskError(404, f"project {ref!r} not found")
        return hits[0]["id"]

    def _names(self):
        users = {u["id"]: u["name"] for u in self.td.list_users()["items"]}
        projects = {p["id"]: p["name"] for p in self.td.list_projects()["items"]}
        return users, projects

    def _row(self, t, users, projects) -> dict:
        return {"id": t["id"], "title": t["title"], "project": projects.get(t["project_id"]), "project_id": t["project_id"],
                "assignee": users.get(t["assignee_id"]), "assignee_id": t["assignee_id"], "status": t["status"], "priority": t["priority"],
                "due": t["due"], "labels": t["labels"]}

    def _all(self, op, **kw) -> list[dict]:
        rows, page = [], 1
        while page:
            r = self.td.call(op, {**kw, "page": page})
            rows += r["items"]
            page = r["next_page"]
        return rows

    # tools
    def t_find_tasks(self, project=None, assignee=None, status=None, priority=None, label=None, overdue=None, due_before=None, text=None):
        unassigned = isinstance(assignee, str) and assignee.strip().lower() == "none"
        kw = {"status": status, "label": label, "due_before": due_before}
        if project is not None:
            kw["project_id"] = self.project_id(project)
        if assignee is not None and not unassigned:
            kw["assignee_id"] = self.user_id(assignee)
        kw = {k: v for k, v in kw.items() if v is not None}
        if text is not None:
            found = {t["id"] for t in self._all("search_tasks", query=text)}
            rows = [t for t in self._all("list_tasks", **kw) if t["id"] in found]
        else:
            rows = self._all("list_tasks", **kw)
        if unassigned:
            rows = [t for t in rows if t["assignee_id"] is None]
        if priority is not None:
            rows = [t for t in rows if t["priority"] == priority]
        if overdue is not None:
            rows = [t for t in rows if (t["due"] is not None and t["due"] < TODAY and t["status"] != "done") == bool(overdue)]
        users, projects = self._names()
        out = [self._row(t, users, projects) for t in rows[:MAX_ROWS]]
        return {"count": len(rows), "tasks": out, **({"truncated": True} if len(rows) > MAX_ROWS else {})}

    def t_get_task_details(self, task_id):
        t = self.td.get_task(task_id=task_id)
        users, projects = self._names()
        comments = [{"id": c["id"], "author": users.get(c["author_id"]), "body": c["body"], "created_at": c["created_at"]}
                    for c in self.td.list_comments(task_id=task_id)["items"]]
        return {**self._row(t, users, projects), "description": t["description"], "created_at": t["created_at"], "updated_at": t["updated_at"], "comments": comments}

    def t_create_task(self, project, title, description=None, assignee=None, due=None, priority=None, labels=None):
        args = {"project_id": self.project_id(project), "title": title, "description": description, "due": due, "priority": priority}
        if assignee is not None:
            args["assignee_id"] = self.user_id(assignee)
        t = self.td.create_task(**{k: v for k, v in args.items() if v is not None})
        for label in labels or []:
            t = self.td.add_label(task_id=t["id"], label=label)
        users, projects = self._names()
        return self._row(t, users, projects)

    def t_update_tasks(self, task_ids, status=None, priority=None, due=None, title=None, description=None, assignee=None,
                       add_labels=None, remove_labels=None):
        fields = {k: v for k, v in {"status": status, "priority": priority, "due": due, "title": title, "description": description}.items() if v is not None}
        target = ...
        if assignee is not None:
            target = None if str(assignee).strip().lower() == "none" else self.user_id(assignee)
        done = []
        for tid in task_ids:
            try:
                t = self.td.get_task(task_id=tid)
                if fields:
                    t = self.td.update_task(task_id=tid, **fields)
                if target is not ...:
                    t = self.td.assign_task(task_id=tid, assignee_id=target)
                for label in add_labels or []:
                    t = self.td.add_label(task_id=tid, label=label)
                for label in remove_labels or []:
                    if label in t["labels"]:
                        t = self.td.remove_label(task_id=tid, label=label)
            except TaskDeskError as e:
                raise TaskDeskError(e.status, f"task {tid}: {e.message}. Updated before the error: {done or 'none'}") from None
            done.append(tid)
        users, projects = self._names()
        return {"updated": [self._row(self.td.get_task(task_id=tid), users, projects) for tid in done]}

    def t_delete_tasks(self, task_ids):
        for tid in task_ids:
            self.td.delete_task(task_id=tid)
        return {"deleted": list(task_ids)}

    def t_comments(self, action, task_id=None, comment_id=None, body=None, author=None):
        need = {"list": ["task_id"], "add": ["task_id", "body", "author"], "edit": ["comment_id", "body"], "delete": ["comment_id"]}[action]
        given = {"task_id": task_id, "comment_id": comment_id, "body": body, "author": author}
        missing = [k for k in need if given[k] is None]
        if missing:
            raise ValueError(f"comments {action} needs {', '.join(missing)}")
        if action == "list":
            return self.td.list_comments(task_id=task_id)
        if action == "add":
            return self.td.add_comment(task_id=task_id, body=body, author_id=self.user_id(author))
        if action == "edit":
            return self.td.update_comment(comment_id=comment_id, body=body)
        return self.td.delete_comment(comment_id=comment_id)

    def t_projects(self, action, project=None, name=None, description=None, owner=None, user=None, status=None):
        if action == "list":
            return self.td.list_projects(**({"status": status} if status else {}))
        if action == "create":
            if name is None or owner is None:
                raise ValueError("projects create needs name and owner")
            return self.td.create_project(name=name, owner_id=self.user_id(owner), **({"description": description} if description is not None else {}))
        if project is None:
            raise ValueError(f"projects {action} needs project")
        pid = self.project_id(project)
        if action == "get":
            return self.td.get_project(project_id=pid)
        if action == "members":
            return self.td.list_project_members(project_id=pid)
        if action == "archive":
            return self.td.archive_project(project_id=pid)
        if action == "add_member":
            if user is None:
                raise ValueError("projects add_member needs user")
            return self.td.add_project_member(project_id=pid, user_id=self.user_id(user))
        args = {"name": name, "description": description, "owner_id": self.user_id(owner) if owner is not None else None}
        return self.td.update_project(project_id=pid, **{k: v for k, v in args.items() if v is not None})

    def t_users(self, action, user=None, name=None, email=None, role=None, active=None):
        if action == "list":
            return self.td.list_users(**({"active": active} if active is not None else {}))
        if action == "create":
            if name is None or email is None:
                raise ValueError("users create needs name and email")
            return self.td.create_user(name=name, email=email, **({"role": role} if role else {}))
        if user is None:
            raise ValueError(f"users {action} needs user")
        uid = self.user_id(user)
        if action == "get":
            return self.td.get_user(user_id=uid)
        if action == "deactivate":
            return self.td.deactivate_user(user_id=uid)
        return self.td.update_user(user_id=uid, **{k: v for k, v in {"name": name, "email": email, "role": role}.items() if v is not None})
