"""Scripted agents that need no model.

- oracle: runs the task's plan from toolcut.solutions through the shape's own tools.
- noop: does nothing.
- swap: runs the plan of the next task (t40 runs t01's plan).

The oracle must pass every task in every shape and both wrong agents must fail every task.
That is how we know the scorer can tell right from wrong.
"""

from __future__ import annotations

import inspect
import json
from pathlib import Path

from . import solutions
from .sessions import Session
from .taskdesk.client import TaskDeskError
from .tasks import TASKS, Task

HELPERS_SOURCE = (Path(__file__).parent / "oracle_helpers.py").read_text()


def _parse(result) -> object:
    if result.is_error:
        try:
            err = json.loads(result.text)
            raise TaskDeskError(int(err.get("status", 400)), err.get("error", result.text))
        except (json.JSONDecodeError, AttributeError):
            raise TaskDeskError(400, result.text) from None
    return json.loads(result.text)


class ToolProxy:
    """Looks like the typed client, but each method call goes through shape A's tools."""

    def __init__(self, session: Session):
        self.session = session

    def __getattr__(self, op_name):
        def call(**kwargs):
            return _parse(self.session.call(op_name, kwargs))

        return call


def helpers_for_shape_a(session: Session):
    namespace = {"taskdesk": ToolProxy(session)}
    exec(compile(HELPERS_SOURCE, "oracle_helpers.py", "exec"), namespace)  # noqa: S102 - our own file
    return namespace["H"]


class HB:
    """The same helper interface, built on shape B's task-sized tools."""

    def __init__(self, session: Session):
        self.s = session

    def _t(self, tool, **args):
        return _parse(self.s.call(tool, {k: v for k, v in args.items() if v is not None}))

    def user(self, name):
        return self._t("users", action="get", user=name)

    def users(self):
        return self._t("users", action="list")["items"]

    def project(self, name):
        return self._t("projects", action="get", project=name)

    def projects(self):
        return self._t("projects", action="list")["items"]

    def tasks(self, project_id=None, assignee_id=None, **filters):
        return self._t("find_tasks", project=project_id, assignee=assignee_id, **filters)["tasks"]

    def overdue(self, **filters):
        return self.tasks(overdue=True, **filters)

    def search(self, text):
        return self.tasks(text=text)

    def task(self, task_id):
        return self._t("get_task_details", task_id=task_id)

    def comments(self, task_id):
        return self._t("comments", action="list", task_id=task_id)["items"]

    def all_comments(self):
        out = []
        for t in self.tasks():
            out += self.comments(t["id"])
        return out

    def members(self, project_id):
        return [u["id"] for u in self._t("projects", action="members", project=project_id)["items"]]

    def update(self, task_id, **fields):
        return self._t("update_tasks", task_ids=[task_id], **fields)

    def assign(self, task_id, user_id):
        return self._t("update_tasks", task_ids=[task_id], assignee="none" if user_id is None else user_id)

    def label(self, task_id, label):
        return self._t("update_tasks", task_ids=[task_id], add_labels=[label])

    def unlabel(self, task_id, label):
        return self._t("update_tasks", task_ids=[task_id], remove_labels=[label])

    def update_many(self, task_ids, assignee=-1, add_label=None, remove_label=None, **fields):
        if not task_ids:
            return None
        if assignee != -1:
            fields["assignee"] = "none" if assignee is None else assignee
        return self._t("update_tasks", task_ids=list(task_ids), add_labels=[add_label] if add_label else None,
                       remove_labels=[remove_label] if remove_label else None, **fields)

    def comment(self, task_id, body, author_id):
        return self._t("comments", action="add", task_id=task_id, body=body, author=author_id)

    def edit_comment(self, comment_id, body):
        return self._t("comments", action="edit", comment_id=comment_id, body=body)

    def delete_comment(self, comment_id):
        return self._t("comments", action="delete", comment_id=comment_id)

    def delete_task(self, task_id):
        return self._t("delete_tasks", task_ids=[task_id])

    def create_task(self, project_id, title, labels=(), assignee_id=None, **fields):
        return self._t("create_task", project=project_id, title=title, assignee=assignee_id, labels=list(labels) or None, **fields)

    def add_member(self, project_id, user_id):
        return self._t("projects", action="add_member", project=project_id, user=user_id)

    def create_project(self, name, owner_id, **fields):
        return self._t("projects", action="create", name=name, owner=owner_id, **fields)

    def update_project(self, project_id, owner_id=None, **fields):
        return self._t("projects", action="update", project=project_id, owner=owner_id, **fields)

    def archive(self, project_id):
        return self._t("projects", action="archive", project=project_id)

    def create_user(self, name, email, **fields):
        return self._t("users", action="create", name=name, email=email, **fields)

    def update_user(self, user_id, **fields):
        return self._t("users", action="update", user=user_id, **fields)

    def deactivate(self, user_id):
        return self._t("users", action="deactivate", user=user_id)


def shape_c_script(task_id: str) -> str:
    """The run_code script for shape C: the helper source, the plan, and one call."""
    plan = inspect.getsource(getattr(solutions, task_id))
    body = HELPERS_SOURCE.split('"""', 2)[2]  # drop the module docstring and the ruff line
    return f"{body.strip()}\n\n\n{plan.strip()}\n\n\n{task_id}(H)\nprint(\"done\")\n"


def run_plan(plan_id: str, shape_key: str, session: Session) -> None:
    """Run one task's plan through a shape. Raises if a tool call fails."""
    if shape_key == "A":
        getattr(solutions, plan_id)(helpers_for_shape_a(session))
    elif shape_key == "B":
        getattr(solutions, plan_id)(HB(session))
    elif shape_key == "C":
        session.call("search_api", {"query": "*"})
        result = session.call("run_code", {"code": shape_c_script(plan_id)})
        if result.is_error or not result.text.strip().endswith("done"):
            raise RuntimeError(f"run_code failed: {result.text[-500:]}")
    else:
        raise ValueError(f"unknown shape {shape_key}")


def plan_for(agent: str, task: Task) -> str | None:
    if agent == "oracle":
        return task.id
    if agent == "noop":
        return None
    if agent == "swap":
        ids = [t.id for t in TASKS]
        return ids[(ids.index(task.id) + 1) % len(ids)]
    raise ValueError(f"unknown agent {agent}")
