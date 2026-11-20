# ruff: noqa: F821
"""The oracle's helper layer over the typed client. It uses the global `taskdesk`.

This file is plain, sandbox-safe Python (no names that start with _, no imports), because
shape C sends its source text inside a run_code script. Shape A runs the same source with
`taskdesk` bound to a proxy that sends each call through shape A's one-op tools.
"""

TODAY = "2026-03-15"


class H:
    @staticmethod
    def pages(method, **kw):
        rows = []
        page = 1
        while page:
            r = method(page=page, **kw)
            rows = rows + r["items"]
            page = r["next_page"]
        return rows

    @staticmethod
    def user(name):
        return [u for u in taskdesk.list_users()["items"] if u["name"] == name][0]

    @staticmethod
    def users():
        return taskdesk.list_users()["items"]

    @staticmethod
    def project(name):
        return [p for p in taskdesk.list_projects()["items"] if p["name"] == name][0]

    @staticmethod
    def projects():
        return taskdesk.list_projects()["items"]

    @staticmethod
    def tasks(**filters):
        return H.pages(taskdesk.list_tasks, **filters)

    @staticmethod
    def overdue(**filters):
        return [t for t in H.tasks(due_before=TODAY, **filters) if t["status"] != "done"]

    @staticmethod
    def search(text):
        return H.pages(taskdesk.search_tasks, query=text)

    @staticmethod
    def task(task_id):
        return taskdesk.get_task(task_id=task_id)

    @staticmethod
    def comments(task_id):
        return taskdesk.list_comments(task_id=task_id)["items"]

    @staticmethod
    def all_comments():
        out = []
        for t in H.tasks():
            out = out + H.comments(t["id"])
        return out

    @staticmethod
    def members(project_id):
        return [u["id"] for u in taskdesk.list_project_members(project_id=project_id)["items"]]

    @staticmethod
    def update(task_id, **fields):
        return taskdesk.update_task(task_id=task_id, **fields)

    @staticmethod
    def assign(task_id, user_id):
        return taskdesk.assign_task(task_id=task_id, assignee_id=user_id)

    @staticmethod
    def label(task_id, label):
        return taskdesk.add_label(task_id=task_id, label=label)

    @staticmethod
    def unlabel(task_id, label):
        return taskdesk.remove_label(task_id=task_id, label=label)

    @staticmethod
    def update_many(task_ids, assignee=-1, add_label=None, remove_label=None, **fields):
        for tid in task_ids:
            if fields:
                taskdesk.update_task(task_id=tid, **fields)
            if assignee != -1:
                taskdesk.assign_task(task_id=tid, assignee_id=assignee)
            if add_label:
                taskdesk.add_label(task_id=tid, label=add_label)
            if remove_label:
                taskdesk.remove_label(task_id=tid, label=remove_label)

    @staticmethod
    def comment(task_id, body, author_id):
        return taskdesk.add_comment(task_id=task_id, body=body, author_id=author_id)

    @staticmethod
    def edit_comment(comment_id, body):
        return taskdesk.update_comment(comment_id=comment_id, body=body)

    @staticmethod
    def delete_comment(comment_id):
        return taskdesk.delete_comment(comment_id=comment_id)

    @staticmethod
    def delete_task(task_id):
        return taskdesk.delete_task(task_id=task_id)

    @staticmethod
    def create_task(project_id, title, labels=(), **fields):
        t = taskdesk.create_task(project_id=project_id, title=title, **fields)
        for label in labels:
            t = taskdesk.add_label(task_id=t["id"], label=label)
        return t

    @staticmethod
    def add_member(project_id, user_id):
        return taskdesk.add_project_member(project_id=project_id, user_id=user_id)

    @staticmethod
    def create_project(name, owner_id, **fields):
        return taskdesk.create_project(name=name, owner_id=owner_id, **fields)

    @staticmethod
    def update_project(project_id, **fields):
        return taskdesk.update_project(project_id=project_id, **fields)

    @staticmethod
    def archive(project_id):
        return taskdesk.archive_project(project_id=project_id)

    @staticmethod
    def create_user(name, email, **fields):
        return taskdesk.create_user(name=name, email=email, **fields)

    @staticmethod
    def update_user(user_id, **fields):
        return taskdesk.update_user(user_id=user_id, **fields)

    @staticmethod
    def deactivate(user_id):
        return taskdesk.deactivate_user(user_id=user_id)
