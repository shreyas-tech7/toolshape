"""Score a run from the fake API's database: the task's own check, then the collateral check."""

from __future__ import annotations

from dataclasses import dataclass

from .tasks import Task, World


@dataclass
class Score:
    passed: bool
    reasons: list[str]


def collateral(task: Task, before: World, after: World) -> list[str]:
    """Rows the task may not touch must equal the seed. New rows only in the task's tables."""
    allowed = task.touch(before)
    out = []
    for table, rows in before.items():
        ok_ids = allowed.get(table, set())
        for row_id, row in rows.items():
            if row_id in ok_ids:
                continue
            now = after.get(table, {}).get(row_id)
            if now is None:
                out.append(f"side effect: {table} {row_id} was deleted")
            elif now != row:
                changed = sorted(k for k in row if row.get(k) != now.get(k))
                out.append(f"side effect: {table} {row_id} changed ({', '.join(changed)})")
        new = [i for i in after.get(table, {}) if i not in rows]
        if new and table not in task.create:
            out.append(f"side effect: new {table} rows {new}")
    return out


def score(task: Task, before: World, after: World) -> Score:
    try:
        reasons = list(task.check(after, before))
    except (KeyError, IndexError, TypeError, ValueError, StopIteration) as e:
        reasons = [f"check could not read the end state: {type(e).__name__}: {e}"]
    reasons += collateral(task, before, after)
    return Score(not reasons, reasons)
