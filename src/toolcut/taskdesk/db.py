"""TaskDesk data and operation logic. A plain in-memory store with seeded data.

The clock is fixed: today is TODAY, and every new row gets that timestamp.
"""

from __future__ import annotations

import copy
import random
import re
import threading

from .ops import OPS_BY_NAME, PAGE_SIZE, PRIORITIES, ROLES, STATUSES

TODAY = "2026-03-15"
SEED = 42
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class ApiError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


USERS = [
    ("Priya Raman", "admin"), ("Marco Bellini", "member"), ("Aiko Tanaka", "member"), ("Sam Okafor", "member"),
    ("Lena Fischer", "member"), ("Diego Alvarez", "admin"), ("Noor Haddad", "member"), ("Tom Becker", "member"),
    ("Grace Liu", "member"), ("Omar Said", "member"),
]
PROJECTS = [
    ("Website Relaunch", "New marketing site and blog.", 1),
    ("Mobile App", "iOS and Android client.", 6),
    ("Billing Revamp", "Move invoices to the new billing provider.", 1),
    ("Ops", "Internal operations and tooling.", 6),
    ("Data Platform", "Warehouse, pipelines and dashboards.", 3),
    ("Legacy Portal", "Old customer portal, being retired.", 2),
]
TITLES = [
    "Write landing page copy", "Fix login redirect", "Set up CI pipeline", "Design pricing table", "Migrate user table",
    "Add dark mode", "Update privacy policy", "Load test checkout", "Clean up feature flags", "Draft launch email",
    "Rotate API keys", "Add invoice PDF export", "Review analytics events", "Fix crash on startup", "Archive old dashboards",
    "Write onboarding guide", "Tune database indexes", "Translate settings page", "Plan Q2 roadmap", "Audit access logs",
    "Refactor payment client", "Add push notifications", "Fix timezone bug", "Benchmark search", "Prepare board slides",
]
LABELS = ["bug", "frontend", "backend", "docs", "security", "infra", "design", "urgent-fix"]
COMMENTS = [
    "Looks good to me.", "Blocked on design review.", "I can take this next week.", "Moved to staging.",
    "Needs a second reviewer.", "Customer reported this again.", "Done locally, opening a PR.", "Can we split this?",
]


def seed_data(seed: int = SEED) -> dict:
    rng = random.Random(seed)  # noqa: S311 - seeded, for statistics or synthetic data
    users = {}
    for i, (name, role) in enumerate(USERS, start=1):
        first, last = name.lower().split()
        users[i] = {"id": i, "name": name, "email": f"{first}.{last}@taskdesk.test", "role": role, "active": True}
    users[10]["active"] = False  # Omar Said left
    projects = {}
    for i, (name, desc, owner) in enumerate(PROJECTS, start=1):
        others = rng.sample([u for u in range(1, 10) if u != owner], 4)
        projects[i] = {"id": i, "name": name, "description": desc, "status": "active", "owner_id": owner,
                       "members": sorted({owner, *others})}
    projects[6]["status"] = "archived"
    tasks = {}
    for i in range(1, 73):
        pid = rng.choice([1, 1, 2, 2, 3, 4, 4, 5, 5, 6])
        members = projects[pid]["members"]
        assignee = rng.choice(members + [None])
        due = None if rng.random() < 0.2 else f"2026-{rng.choice(['02', '03', '03', '04', '05'])}-{rng.randint(1, 28):02d}"
        tasks[i] = {
            "id": i, "project_id": pid, "title": f"{rng.choice(TITLES)} #{i}", "description": rng.choice(["", "See the spec.", "Ask Priya for details.", "Follow the checklist."]),
            "status": rng.choice(["todo", "todo", "in_progress", "done"]), "priority": rng.choice(PRIORITIES),
            "assignee_id": assignee, "due": due, "labels": sorted(rng.sample(LABELS, rng.choice([0, 1, 1, 2]))),
            "created_at": "2026-01-10", "updated_at": "2026-01-10",
        }
    comments = {}
    for i in range(1, 51):
        tid = rng.randint(1, 72)
        author = rng.choice(projects[tasks[tid]["project_id"]]["members"])
        comments[i] = {"id": i, "task_id": tid, "author_id": author, "body": rng.choice(COMMENTS), "created_at": "2026-02-01"}
    return {"users": users, "projects": projects, "tasks": tasks, "comments": comments}


class DB:
    """The store. All operation methods are named op_<operation name>."""

    def __init__(self, seed: int = SEED):
        self.lock = threading.Lock()
        self.reset(seed)

    def reset(self, seed: int = SEED) -> None:
        self.data = seed_data(seed)
        self.calls: list[str] = []

    def dump(self) -> dict:
        return copy.deepcopy(self.data)

    def call(self, name: str, args: dict) -> object:
        if name not in OPS_BY_NAME:
            raise ApiError(404, f"unknown operation {name}")
        with self.lock:
            self.calls.append(name)
            return copy.deepcopy(getattr(self, "op_" + name)(**args))

    # helpers
    def _get(self, table: str, key, what: str) -> dict:
        try:
            row = self.data[table].get(int(key))
        except (TypeError, ValueError):
            row = None
        if row is None:
            raise ApiError(404, f"{what} {key} not found")
        return row

    def _next_id(self, table: str) -> int:
        return max(self.data[table], default=0) + 1

    @staticmethod
    def _page(items: list, page) -> dict:
        page = int(page or 1)
        if page < 1:
            raise ApiError(400, "page must be 1 or more")
        start = (page - 1) * PAGE_SIZE
        chunk = items[start:start + PAGE_SIZE]
        more = start + PAGE_SIZE < len(items)
        return {"items": chunk, "page": page, "total": len(items), "next_page": page + 1 if more else None}

    @staticmethod
    def _check(value, allowed, field):
        if value is not None and value not in allowed:
            raise ApiError(400, f"{field} must be one of {', '.join(allowed)}")

    @staticmethod
    def _check_date(value, field="due"):
        if value is not None and not (isinstance(value, str) and _DATE.match(value)):
            raise ApiError(400, f"{field} must be YYYY-MM-DD")

    def _assignable(self, project: dict, user_id) -> None:
        if user_id is None:
            return
        user = self._get("users", user_id, "user")
        if not user["active"]:
            raise ApiError(400, f"user {user_id} is deactivated")
        if user["id"] not in project["members"]:
            raise ApiError(400, f"user {user_id} is not a member of project {project['id']}")

    # users
    def op_list_users(self, active=None):
        rows = list(self.data["users"].values())
        if active is not None:
            rows = [u for u in rows if u["active"] == bool(active)]
        return {"items": rows}

    def op_get_user(self, user_id):
        return self._get("users", user_id, "user")

    def op_create_user(self, name, email, role=None):
        self._check(role, ROLES, "role")
        if any(u["email"].lower() == str(email).lower() for u in self.data["users"].values()):
            raise ApiError(409, f"email {email} is already used")
        uid = self._next_id("users")
        self.data["users"][uid] = {"id": uid, "name": name, "email": email, "role": role or "member", "active": True}
        return self.data["users"][uid]

    def op_update_user(self, user_id, name=None, email=None, role=None):
        user = self._get("users", user_id, "user")
        self._check(role, ROLES, "role")
        if email is not None and any(u["email"].lower() == email.lower() and u["id"] != user["id"] for u in self.data["users"].values()):
            raise ApiError(409, f"email {email} is already used")
        for k, v in (("name", name), ("email", email), ("role", role)):
            if v is not None:
                user[k] = v
        return user

    def op_deactivate_user(self, user_id):
        user = self._get("users", user_id, "user")
        user["active"] = False
        return user

    # projects
    def op_list_projects(self, status=None):
        self._check(status, ["active", "archived"], "status")
        rows = [p for p in self.data["projects"].values() if status is None or p["status"] == status]
        return {"items": rows}

    def op_get_project(self, project_id):
        return self._get("projects", project_id, "project")

    def op_create_project(self, name, owner_id, description=None):
        owner = self._get("users", owner_id, "user")
        if any(p["name"].lower() == str(name).lower() for p in self.data["projects"].values()):
            raise ApiError(409, f"project name {name} is already used")
        pid = self._next_id("projects")
        self.data["projects"][pid] = {"id": pid, "name": name, "description": description or "", "status": "active",
                                      "owner_id": owner["id"], "members": [owner["id"]]}
        return self.data["projects"][pid]

    def op_update_project(self, project_id, name=None, description=None, owner_id=None):
        project = self._get("projects", project_id, "project")
        if owner_id is not None:
            self._get("users", owner_id, "user")
            project["owner_id"] = int(owner_id)
            if int(owner_id) not in project["members"]:
                project["members"] = sorted(project["members"] + [int(owner_id)])
        if name is not None:
            project["name"] = name
        if description is not None:
            project["description"] = description
        return project

    def op_archive_project(self, project_id):
        project = self._get("projects", project_id, "project")
        project["status"] = "archived"
        return project

    def op_list_project_members(self, project_id):
        project = self._get("projects", project_id, "project")
        return {"items": [self.data["users"][u] for u in project["members"]]}

    def op_add_project_member(self, project_id, user_id):
        project = self._get("projects", project_id, "project")
        user = self._get("users", user_id, "user")
        if user["id"] not in project["members"]:
            project["members"] = sorted(project["members"] + [user["id"]])
        return project

    # tasks
    def op_list_tasks(self, project_id=None, assignee_id=None, status=None, label=None, due_before=None, page=None):
        self._check(status, STATUSES, "status")
        self._check_date(due_before, "due_before")
        rows = []
        for t in self.data["tasks"].values():
            if project_id is not None and t["project_id"] != int(project_id):
                continue
            if assignee_id is not None and t["assignee_id"] != int(assignee_id):
                continue
            if status is not None and t["status"] != status:
                continue
            if label is not None and label not in t["labels"]:
                continue
            if due_before is not None and not (t["due"] and t["due"] < due_before):
                continue
            rows.append(t)
        return self._page(rows, page)

    def op_get_task(self, task_id):
        return self._get("tasks", task_id, "task")

    def op_create_task(self, project_id, title, description=None, assignee_id=None, due=None, priority=None):
        project = self._get("projects", project_id, "project")
        if project["status"] == "archived":
            raise ApiError(400, f"project {project_id} is archived")
        self._check(priority, PRIORITIES, "priority")
        self._check_date(due)
        self._assignable(project, assignee_id)
        tid = self._next_id("tasks")
        self.data["tasks"][tid] = {
            "id": tid, "project_id": project["id"], "title": title, "description": description or "", "status": "todo",
            "priority": priority or "medium", "assignee_id": int(assignee_id) if assignee_id is not None else None,
            "due": due, "labels": [], "created_at": TODAY, "updated_at": TODAY,
        }
        return self.data["tasks"][tid]

    def op_update_task(self, task_id, title=None, description=None, status=None, priority=None, due=None):
        task = self._get("tasks", task_id, "task")
        self._check(status, STATUSES, "status")
        self._check(priority, PRIORITIES, "priority")
        self._check_date(due)
        for k, v in (("title", title), ("description", description), ("status", status), ("priority", priority), ("due", due)):
            if v is not None:
                task[k] = v
        task["updated_at"] = TODAY
        return task

    def op_delete_task(self, task_id):
        task = self._get("tasks", task_id, "task")
        del self.data["tasks"][task["id"]]
        for cid in [c for c, row in self.data["comments"].items() if row["task_id"] == task["id"]]:
            del self.data["comments"][cid]
        return {"deleted": task["id"]}

    def op_assign_task(self, task_id, assignee_id):
        task = self._get("tasks", task_id, "task")
        self._assignable(self.data["projects"][task["project_id"]], assignee_id)
        task["assignee_id"] = int(assignee_id) if assignee_id is not None else None
        task["updated_at"] = TODAY
        return task

    def op_add_label(self, task_id, label):
        task = self._get("tasks", task_id, "task")
        label = str(label).strip().lower()
        if not label:
            raise ApiError(400, "label must not be empty")
        if label not in task["labels"]:
            task["labels"] = sorted(task["labels"] + [label])
            task["updated_at"] = TODAY
        return task

    def op_remove_label(self, task_id, label):
        task = self._get("tasks", task_id, "task")
        if label not in task["labels"]:
            raise ApiError(404, f"task {task_id} has no label {label}")
        task["labels"] = [x for x in task["labels"] if x != label]
        task["updated_at"] = TODAY
        return task

    # comments
    def op_list_comments(self, task_id):
        task = self._get("tasks", task_id, "task")
        return {"items": [c for c in self.data["comments"].values() if c["task_id"] == task["id"]]}

    def op_add_comment(self, task_id, body, author_id):
        task = self._get("tasks", task_id, "task")
        author = self._get("users", author_id, "user")
        if not str(body).strip():
            raise ApiError(400, "body must not be empty")
        cid = self._next_id("comments")
        self.data["comments"][cid] = {"id": cid, "task_id": task["id"], "author_id": author["id"], "body": body, "created_at": TODAY}
        return self.data["comments"][cid]

    def op_update_comment(self, comment_id, body):
        comment = self._get("comments", comment_id, "comment")
        comment["body"] = body
        return comment

    def op_delete_comment(self, comment_id):
        comment = self._get("comments", comment_id, "comment")
        del self.data["comments"][comment["id"]]
        return {"deleted": comment["id"]}

    def op_search_tasks(self, query, page=None):
        q = str(query).lower()
        rows = [t for t in self.data["tasks"].values() if q in t["title"].lower() or q in t["description"].lower()]
        return self._page(rows, page)
