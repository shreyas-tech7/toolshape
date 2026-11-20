"""The oracle's plan for each task, written once against the helper layer `h`.

Each function is sandbox-safe (shape C sends its source inside a run_code script), so it
uses no imports and no names that start with _. See toolcut.oracle for how each shape runs it.
"""


def t01(h):
    h.update(13, status="done")


def t02(h):
    h.update(44, priority="high")


def t03(h):
    h.update(49, due="2026-03-31")


def t04(h):
    h.label(24, "security")


def t05(h):
    h.unlabel(37, "design")


def t06(h):
    h.comment(31, "Starting today.", h.user("Sam Okafor")["id"])


def t07(h):
    h.delete_task(59)


def t08(h):
    h.assign(21, None)


def t09(h):
    h.assign(19, h.user("Aiko Tanaka")["id"])


def t10(h):
    h.create_task(h.project("Data Platform")["id"], "Write API changelog", priority="high")


def t11(h):
    h.create_user("Ivy Chen", "ivy.chen@taskdesk.test", role="member")


def t12(h):
    h.update_project(h.project("Ops")["id"], name="Operations")


def t13(h):
    h.deactivate(h.user("Tom Becker")["id"])


def t14(h):
    h.update_user(h.user("Lena Fischer")["id"], role="admin")


def t15(h):
    h.add_member(h.project("Mobile App")["id"], h.user("Grace Liu")["id"])


def t16(h):
    h.update_project(h.project("Billing Revamp")["id"], owner_id=h.user("Diego Alvarez")["id"])


def t17(h):
    grace = h.user("Grace Liu")["id"]
    task = h.task(71)
    if grace not in h.members(task["project_id"]):
        h.add_member(task["project_id"], grace)
    h.assign(71, grace)


def t18(h):
    sam = h.user("Sam Okafor")["id"]
    project = h.create_project("Security Review", sam)
    h.create_task(project["id"], "Threat model", assignee_id=sam)


def t19(h):
    for t in h.search("Plan Q2 roadmap"):
        h.update(t["id"], status="in_progress")


def t20(h):
    priya = h.user("Priya Raman")["id"]
    for c in h.comments(57):
        if c["author_id"] == priya:
            h.edit_comment(c["id"], "Approved for release.")


def t21(h):
    sam = h.user("Sam Okafor")["id"]
    for c in h.comments(37):
        if c["author_id"] == sam:
            h.delete_comment(c["id"])


def t22(h):
    h.archive(h.project("Billing Revamp")["id"])


def t23(h):
    h.create_task(h.project("Website Relaunch")["id"], "Fix flaky login test", labels=["bug", "frontend"],
                  assignee_id=h.user("Noor Haddad")["id"], due="2026-03-20")


def t24(h):
    h.assign(9, h.user("Marco Bellini")["id"])
    h.comment(9, "Reassigned to Marco.", h.user("Diego Alvarez")["id"])


def t25(h):
    ids = [t["id"] for t in h.overdue(project_id=h.project("Ops")["id"])]
    h.update_many(ids, add_label="overdue")


def t26(h):
    ids = [t["id"] for t in h.overdue(assignee_id=h.user("Priya Raman")["id"])]
    h.update_many(ids, add_label="overdue")


def t27(h):
    tom = h.user("Tom Becker")["id"]
    ids = [t["id"] for t in h.tasks(assignee_id=tom) if t["status"] != "done"]
    h.update_many(ids, assignee=None)
    h.deactivate(tom)


def t28(h):
    tasks = h.tasks(project_id=h.project("Data Platform")["id"], label="urgent-fix")
    h.update_many([t["id"] for t in tasks if t["status"] != "done"], priority="urgent")


def t29(h):
    tasks = h.tasks(project_id=h.project("Mobile App")["id"], status="in_progress")
    h.update_many([t["id"] for t in tasks], status="done")


def t30(h):
    tasks = h.tasks(project_id=h.project("Website Relaunch")["id"], label="docs")
    h.update_many([t["id"] for t in tasks], remove_label="docs")


def t31(h):
    tasks = h.tasks(project_id=h.project("Website Relaunch")["id"], assignee_id=h.user("Marco Bellini")["id"])
    h.update_many([t["id"] for t in tasks if t["status"] != "done"], assignee=h.user("Aiko Tanaka")["id"])


def t32(h):
    h.comment(1, str(len(h.overdue())), h.user("Priya Raman")["id"])


def t33(h):
    counts = {}
    for c in h.all_comments():
        counts[c["author_id"]] = counts.get(c["author_id"], 0) + 1
    top = max(counts, key=lambda k: counts[k])
    h.update_user(top, role="admin")


def t34(h):
    n = len([t for t in h.tasks() if t["status"] != "done" and t["assignee_id"] is None])
    h.create_task(h.project("Ops")["id"], "Unassigned open tasks: " + str(n))


def t35(h):
    counts = {}
    for t in h.tasks():
        if t["status"] != "done":
            counts[t["project_id"]] = counts.get(t["project_id"], 0) + 1
    top = max(counts, key=lambda k: counts[k])
    name = [p["name"] for p in h.projects() if p["id"] == top][0]
    h.comment(71, name, h.user("Priya Raman")["id"])


def t36(h):
    rows = sorted([t for t in h.tasks() if t["status"] != "done" and t["due"]], key=lambda t: t["due"])
    h.update(rows[0]["id"], priority="urgent")


def t37(h):
    tasks = h.tasks(project_id=h.project("Billing Revamp")["id"])
    h.update_many([t["id"] for t in tasks if t["due"] is None], due="2026-04-30")


def t38(h):
    ids = sorted({c["task_id"] for c in h.all_comments() if c["body"] == "Customer reported this again."})
    h.update_many(ids, add_label="customer")


def t39(h):
    tasks = h.tasks(project_id=h.project("Website Relaunch")["id"])
    ids = sorted(t["id"] for t in tasks if t["status"] != "done" and t["priority"] == "urgent")
    h.comment(2, ", ".join(str(i) for i in ids), h.user("Priya Raman")["id"])


def t40(h):
    user = h.create_user("Ravi Patel", "ravi.patel@taskdesk.test")
    h.add_member(h.project("Data Platform")["id"], user["id"])
    h.assign(21, user["id"])
