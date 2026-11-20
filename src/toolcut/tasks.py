"""The 40 TaskDesk tasks. Each one has a prompt, a check on the final database and a
collateral rule: which existing rows it may change and which tables may gain rows.

Checks compute their expected values from the seed ("before") with plain code, so a
change to the seed data cannot silently break them.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field

from .taskdesk.db import TODAY

World = dict  # table name -> {id: row}

PREAMBLE = (
    f"Today is {TODAY}. A task is overdue when it has a due date before today and its status is not done. "
    "An open task is a task whose status is not done."
)


@dataclass(frozen=True)
class Task:
    id: str
    category: str
    prompt: str
    check: Callable[[World, World], list[str]]
    touch: Callable[[World], dict] = field(default=lambda before: {})
    create: tuple[str, ...] = ()


def world(dump_data: dict) -> World:
    """Turn the admin dump (table -> list of rows) into table -> {id: row}."""
    return {t: {row["id"]: row for row in rows} for t, rows in dump_data.items()}


# small helpers for checks
def overdue(t: dict) -> bool:
    return t["due"] is not None and t["due"] < TODAY and t["status"] != "done"


def uid(w: World, name: str) -> int:
    return next(u["id"] for u in w["users"].values() if u["name"] == name)


def pid(w: World, name: str) -> int:
    return next(p["id"] for p in w["projects"].values() if p["name"] == name)


def new_rows(after: World, before: World, table: str) -> list[dict]:
    return [r for i, r in after[table].items() if i not in before[table]]


def expect(cond: bool, msg: str) -> list[str]:
    return [] if cond else [msg]


def field_is(table: str, row_id: int, key: str, value) -> Callable[[World, World], list[str]]:
    def check(after, before):
        row = after[table].get(row_id)
        if row is None:
            return [f"{table} {row_id} is missing"]
        return expect(row[key] == value, f"{table} {row_id} {key} is {row[key]!r}, expected {value!r}")
    return check


def all_of(*checks) -> Callable[[World, World], list[str]]:
    def check(after, before):
        out = []
        for c in checks:
            out += c(after, before)
        return out
    return check


def one_new_comment(task_id: int, author: str, body_ok: Callable[[str, World], bool], what: str):
    def check(after, before):
        rows = [c for c in new_rows(after, before, "comments") if c["task_id"] == task_id]
        if len(rows) != 1:
            return [f"expected exactly one new comment on task {task_id}, found {len(rows)}"]
        c = rows[0]
        out = expect(c["author_id"] == uid(before, author), f"comment author is {c['author_id']}, expected {author}")
        return out + expect(body_ok(c["body"], before), f"comment body {c['body']!r} is not {what}")
    return check


def one_new_task(project: str, title: str, **fields):
    def check(after, before):
        rows = [t for t in new_rows(after, before, "tasks") if t["project_id"] == pid(before, project)]
        if len(rows) != 1:
            return [f"expected exactly one new task in {project}, found {len(rows)}"]
        t = rows[0]
        out = expect(t["title"].strip() == title, f"new task title is {t['title']!r}, expected {title!r}")
        for k, v in fields.items():
            if k == "assignee":
                k, v = "assignee_id", uid(before, v)
            got = t[k]
            if k == "labels":
                got, v = sorted(got), sorted(v)
            out += expect(got == v, f"new task {k} is {got!r}, expected {v!r}")
        return out
    return check


def tasks_where(before: World, pred) -> set[int]:
    return {t["id"] for t in before["tasks"].values() if pred(t)}


def every(ids_fn, key: str, value) -> Callable[[World, World], list[str]]:
    def check(after, before):
        out = []
        for i in sorted(ids_fn(before)):
            t = after["tasks"].get(i)
            if t is None:
                out.append(f"task {i} is missing")
            elif key == "+label" and value not in t["labels"]:
                out.append(f"task {i} lacks label {value!r}")
            elif key == "-label" and value in t["labels"]:
                out.append(f"task {i} still has label {value!r}")
            elif key not in ("+label", "-label") and t[key] != value:
                out.append(f"task {i} {key} is {t[key]!r}, expected {value!r}")
        return out
    return check


def ints_in(text: str) -> list[int]:
    return [int(x) for x in re.findall(r"\d+", text)]


def _comment_has(before: World, body: str) -> set[int]:
    return {c["task_id"] for c in before["comments"].values() if c["body"] == body}


def _top_commenter(before: World) -> int:
    (top, n), (_, m) = Counter(c["author_id"] for c in before["comments"].values()).most_common(2)
    if n <= m:
        raise RuntimeError("seed must have a unique top commenter")
    return top


def _busiest_project(before: World) -> str:
    (top, n), (_, m) = Counter(t["project_id"] for t in before["tasks"].values() if t["status"] != "done").most_common(2)
    if n <= m:
        raise RuntimeError("seed must have a unique busiest project")
    return before["projects"][top]["name"]


def _earliest_open(before: World) -> int:
    rows = sorted((t["due"], t["id"]) for t in before["tasks"].values() if t["due"] and t["status"] != "done")
    if rows[0][0] == rows[1][0]:
        raise RuntimeError("seed must have a unique earliest due date")
    return rows[0][1]


T = Task
TASKS: list[Task] = [
    # single step, ids given
    T("t01", "single", "Mark task 13 as done.", field_is("tasks", 13, "status", "done"), lambda b: {"tasks": {13}}),
    T("t02", "single", "Change the priority of task 44 to high.", field_is("tasks", 44, "priority", "high"), lambda b: {"tasks": {44}}),
    T("t03", "single", "Set the due date of task 49 to 2026-03-31.", field_is("tasks", 49, "due", "2026-03-31"), lambda b: {"tasks": {49}}),
    T("t04", "single", 'Add the label "security" to task 24.', every(lambda b: {24}, "+label", "security"), lambda b: {"tasks": {24}}),
    T("t05", "single", 'Remove the label "design" from task 37.', every(lambda b: {37}, "-label", "design"), lambda b: {"tasks": {37}}),
    T("t06", "single", 'Add the comment "Starting today." to task 31, written by Sam Okafor.',
      one_new_comment(31, "Sam Okafor", lambda s, b: s.strip() == "Starting today.", '"Starting today."'), create=("comments",)),
    T("t07", "single", "Delete task 59.", lambda a, b: expect(59 not in a["tasks"], "task 59 still exists"),
      lambda b: {"tasks": {59}, "comments": {c["id"] for c in b["comments"].values() if c["task_id"] == 59}}),
    T("t08", "single", "Unassign task 21 so that nobody is assigned to it.", field_is("tasks", 21, "assignee_id", None), lambda b: {"tasks": {21}}),
    # names instead of ids
    T("t09", "names", "Assign task 19 to Aiko Tanaka.", lambda a, b: field_is("tasks", 19, "assignee_id", uid(b, "Aiko Tanaka"))(a, b), lambda b: {"tasks": {19}}),
    T("t10", "names", 'Create a task titled "Write API changelog" in the Data Platform project with high priority.',
      one_new_task("Data Platform", "Write API changelog", priority="high"), create=("tasks",)),
    T("t11", "names", 'Create a user named "Ivy Chen" with the email ivy.chen@taskdesk.test and the member role.',
      lambda a, b: (lambda rows: expect(len(rows) == 1 and rows[0]["name"] == "Ivy Chen" and rows[0]["email"] == "ivy.chen@taskdesk.test"
                                        and rows[0]["role"] == "member" and rows[0]["active"], f"new users: {rows}"))(new_rows(a, b, "users")),
      create=("users",)),
    T("t12", "names", 'Rename the project "Ops" to "Operations".', lambda a, b: field_is("projects", pid(b, "Ops"), "name", "Operations")(a, b),
      lambda b: {"projects": {pid(b, "Ops")}}),
    T("t13", "names", "Deactivate the user Tom Becker.", lambda a, b: field_is("users", uid(b, "Tom Becker"), "active", False)(a, b),
      lambda b: {"users": {uid(b, "Tom Becker")}}),
    T("t14", "names", "Give Lena Fischer the admin role.", lambda a, b: field_is("users", uid(b, "Lena Fischer"), "role", "admin")(a, b),
      lambda b: {"users": {uid(b, "Lena Fischer")}}),
    T("t15", "names", "Add Grace Liu as a member of the Mobile App project.",
      lambda a, b: expect(uid(b, "Grace Liu") in a["projects"][pid(b, "Mobile App")]["members"], "Grace Liu is not a member of Mobile App"),
      lambda b: {"projects": {pid(b, "Mobile App")}}),
    T("t16", "names", "Make Diego Alvarez the owner of the Billing Revamp project.",
      lambda a, b: field_is("projects", pid(b, "Billing Revamp"), "owner_id", uid(b, "Diego Alvarez"))(a, b),
      lambda b: {"projects": {pid(b, "Billing Revamp")}}),
    # several steps
    T("t17", "multi", "Assign task 71 to Grace Liu.",
      lambda a, b: field_is("tasks", 71, "assignee_id", uid(b, "Grace Liu"))(a, b),
      lambda b: {"tasks": {71}, "projects": {b["tasks"][71]["project_id"]}}),
    T("t18", "multi", 'Create a project named "Security Review" owned by Sam Okafor. Then create a task titled "Threat model" in it, assigned to Sam Okafor.',
      lambda a, b: (lambda ps: ["expected one new project named Security Review"] if len(ps) != 1 or ps[0]["name"] != "Security Review"
                    else expect(ps[0]["owner_id"] == uid(b, "Sam Okafor"), "wrong owner")
                    + (lambda ts: expect(len(ts) == 1 and ts[0]["title"].strip() == "Threat model" and ts[0]["assignee_id"] == uid(b, "Sam Okafor"),
                                         f"tasks in the new project: {ts}"))([t for t in a["tasks"].values() if t["project_id"] == ps[0]["id"]]))(new_rows(a, b, "projects"))
      + expect(len(new_rows(a, b, "tasks")) == 1, "expected exactly one new task"),
      create=("projects", "tasks")),
    T("t19", "multi", 'Find the task whose title contains "Plan Q2 roadmap" and set its status to in_progress.',
      lambda a, b: every(lambda w: tasks_where(w, lambda t: "Plan Q2 roadmap" in t["title"]), "status", "in_progress")(a, b),
      lambda b: {"tasks": tasks_where(b, lambda t: "Plan Q2 roadmap" in t["title"])}),
    T("t20", "multi", 'Priya Raman wrote a comment on task 57. Change its text to "Approved for release."',
      lambda a, b: [f"comment {i} body is {a['comments'][i]['body']!r}" for i in
                    [c["id"] for c in b["comments"].values() if c["task_id"] == 57 and c["author_id"] == uid(b, "Priya Raman")]
                    if a["comments"].get(i, {}).get("body") != "Approved for release."],
      lambda b: {"comments": {c["id"] for c in b["comments"].values() if c["task_id"] == 57 and c["author_id"] == uid(b, "Priya Raman")}}),
    T("t21", "multi", "Delete every comment on task 37 that Sam Okafor wrote. Keep the other comments.",
      lambda a, b: [f"comment {i} still exists" for i, c in b["comments"].items() if c["task_id"] == 37 and c["author_id"] == uid(b, "Sam Okafor") and i in a["comments"]]
      + expect(any(c["task_id"] == 37 for c in a["comments"].values()), "the other comments on task 37 are gone"),
      lambda b: {"comments": {i for i, c in b["comments"].items() if c["task_id"] == 37 and c["author_id"] == uid(b, "Sam Okafor")}}),
    T("t22", "multi", "Archive the Billing Revamp project.", lambda a, b: field_is("projects", pid(b, "Billing Revamp"), "status", "archived")(a, b),
      lambda b: {"projects": {pid(b, "Billing Revamp")}}),
    T("t23", "multi", 'Create a task titled "Fix flaky login test" in the Website Relaunch project. Assign it to Noor Haddad, set the due date to 2026-03-20 and add the labels "bug" and "frontend".',
      one_new_task("Website Relaunch", "Fix flaky login test", assignee="Noor Haddad", due="2026-03-20", labels=["bug", "frontend"]), create=("tasks",)),
    T("t24", "multi", 'Reassign task 9 to Marco Bellini, then add the comment "Reassigned to Marco." to task 9, written by Diego Alvarez.',
      all_of(lambda a, b: field_is("tasks", 9, "assignee_id", uid(b, "Marco Bellini"))(a, b),
             one_new_comment(9, "Diego Alvarez", lambda s, b: s.strip() == "Reassigned to Marco.", '"Reassigned to Marco."')),
      lambda b: {"tasks": {9}}, ("comments",)),
    # bulk
    T("t25", "bulk", 'Add the label "overdue" to every overdue task in the Ops project.',
      every(lambda b: tasks_where(b, lambda t: overdue(t) and t["project_id"] == pid(b, "Ops")), "+label", "overdue"),
      lambda b: {"tasks": tasks_where(b, lambda t: overdue(t) and t["project_id"] == pid(b, "Ops"))}),
    T("t26", "bulk", 'Add the label "overdue" to every overdue task assigned to Priya Raman, in any project.',
      every(lambda b: tasks_where(b, lambda t: overdue(t) and t["assignee_id"] == uid(b, "Priya Raman")), "+label", "overdue"),
      lambda b: {"tasks": tasks_where(b, lambda t: overdue(t) and t["assignee_id"] == uid(b, "Priya Raman"))}),
    T("t27", "bulk", "Deactivate Tom Becker and unassign every open task that is assigned to Tom Becker.",
      all_of(lambda a, b: field_is("users", uid(b, "Tom Becker"), "active", False)(a, b),
             every(lambda b: tasks_where(b, lambda t: t["status"] != "done" and t["assignee_id"] == uid(b, "Tom Becker")), "assignee_id", None)),
      lambda b: {"users": {uid(b, "Tom Becker")}, "tasks": tasks_where(b, lambda t: t["status"] != "done" and t["assignee_id"] == uid(b, "Tom Becker"))}),
    T("t28", "bulk", 'Set the priority to urgent on every open task in the Data Platform project that has the label "urgent-fix".',
      every(lambda b: tasks_where(b, lambda t: t["status"] != "done" and t["project_id"] == pid(b, "Data Platform") and "urgent-fix" in t["labels"]), "priority", "urgent"),
      lambda b: {"tasks": tasks_where(b, lambda t: t["status"] != "done" and t["project_id"] == pid(b, "Data Platform") and "urgent-fix" in t["labels"])}),
    T("t29", "bulk", "Mark every in_progress task in the Mobile App project as done.",
      every(lambda b: tasks_where(b, lambda t: t["status"] == "in_progress" and t["project_id"] == pid(b, "Mobile App")), "status", "done"),
      lambda b: {"tasks": tasks_where(b, lambda t: t["status"] == "in_progress" and t["project_id"] == pid(b, "Mobile App"))}),
    T("t30", "bulk", 'Remove the label "docs" from every task in the Website Relaunch project.',
      every(lambda b: tasks_where(b, lambda t: "docs" in t["labels"] and t["project_id"] == pid(b, "Website Relaunch")), "-label", "docs"),
      lambda b: {"tasks": tasks_where(b, lambda t: "docs" in t["labels"] and t["project_id"] == pid(b, "Website Relaunch"))}),
    T("t31", "bulk", "Reassign every open task of Marco Bellini in the Website Relaunch project to Aiko Tanaka.",
      lambda a, b: every(lambda w: tasks_where(w, lambda t: t["status"] != "done" and t["assignee_id"] == uid(w, "Marco Bellini") and t["project_id"] == pid(w, "Website Relaunch")),
                         "assignee_id", uid(b, "Aiko Tanaka"))(a, b),
      lambda b: {"tasks": tasks_where(b, lambda t: t["status"] != "done" and t["assignee_id"] == uid(b, "Marco Bellini") and t["project_id"] == pid(b, "Website Relaunch"))}),
    # look something up, then write the answer
    T("t32", "lookup", "Count the overdue tasks across all projects. Add a comment to task 1, written by Priya Raman, whose text is only that number.",
      one_new_comment(1, "Priya Raman", lambda s, b: s.strip() == str(len(tasks_where(b, overdue))), "the overdue count"), create=("comments",)),
    T("t33", "lookup", "Find the user who wrote the most comments and give that user the admin role.",
      lambda a, b: field_is("users", _top_commenter(b), "role", "admin")(a, b), lambda b: {"users": {_top_commenter(b)}}),
    T("t34", "lookup", 'Count the open tasks that have no assignee, across all projects. Create a task in the Ops project titled "Unassigned open tasks: N", where N is that count.',
      lambda a, b: one_new_task("Ops", f"Unassigned open tasks: {len(tasks_where(b, lambda t: t['status'] != 'done' and t['assignee_id'] is None))}")(a, b), create=("tasks",)),
    T("t35", "lookup", "Find the project with the most open tasks. Add a comment to task 71, written by Priya Raman, whose text is only that project's name.",
      one_new_comment(71, "Priya Raman", lambda s, b: s.strip().lower() == _busiest_project(b).lower(), "the busiest project's name"), create=("comments",)),
    T("t36", "lookup", "Find the open task with the earliest due date and set its priority to urgent.",
      lambda a, b: field_is("tasks", _earliest_open(b), "priority", "urgent")(a, b), lambda b: {"tasks": {_earliest_open(b)}}),
    T("t37", "lookup", "Give every task in the Billing Revamp project that has no due date the due date 2026-04-30.",
      every(lambda b: tasks_where(b, lambda t: t["due"] is None and t["project_id"] == pid(b, "Billing Revamp")), "due", "2026-04-30"),
      lambda b: {"tasks": tasks_where(b, lambda t: t["due"] is None and t["project_id"] == pid(b, "Billing Revamp"))}),
    T("t38", "lookup", 'Add the label "customer" to every task that has a comment whose text is exactly "Customer reported this again."',
      every(lambda b: _comment_has(b, "Customer reported this again."), "+label", "customer"),
      lambda b: {"tasks": _comment_has(b, "Customer reported this again.")}),
    T("t39", "lookup", "List the ids of every open task with urgent priority in the Website Relaunch project. Add them as one comment on task 2, written by Priya Raman: the ids only, in increasing order, separated by commas.",
      one_new_comment(2, "Priya Raman", lambda s, b: ints_in(s) == sorted(tasks_where(b, lambda t: t["status"] != "done" and t["priority"] == "urgent"
                                                                                       and t["project_id"] == pid(b, "Website Relaunch"))), "the urgent open ids"),
      create=("comments",)),
    T("t40", "lookup", 'Create a user named "Ravi Patel" with the email ravi.patel@taskdesk.test. Add the new user to the Data Platform project, then assign task 21 to the new user.',
      lambda a, b: (lambda rows: ["expected one new user Ravi Patel"] if len(rows) != 1 or rows[0]["name"] != "Ravi Patel" else
                    field_is("tasks", 21, "assignee_id", rows[0]["id"])(a, b)
                    + expect(rows[0]["id"] in a["projects"][pid(b, "Data Platform")]["members"], "Ravi Patel is not in Data Platform"))(new_rows(a, b, "users")),
      lambda b: {"projects": {pid(b, "Data Platform")}, "tasks": {21}}, ("users",)),
]

TASKS_BY_ID = {t.id: t for t in TASKS}
