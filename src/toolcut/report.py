"""Turn results files into markdown tables. The README and docs/REPORT.md use the same functions,
so every number in them comes from a results file written by a real run.
"""

from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path

from . import __version__
from .metrics import BOOT_N, BOOT_SEED, bootstrap_mean, paired_diff, wilson
from .tasks import TASKS

SHAPES = ("A", "B", "C")
SHAPE_NAMES = {"A": "A: one tool per endpoint", "B": "B: task-sized tools", "C": "C: search_api + run_code"}


def tok(nbytes: float) -> float:
    return nbytes / 4


def load(path) -> dict:
    return json.loads(Path(path).read_text())


def _fmt(x: float, nd: int = 1) -> str:
    return f"{x:,.{nd}f}"


def _ci(m, lo, hi, nd=1) -> str:
    return f"{_fmt(m, nd)} [{_fmt(lo, nd)}, {_fmt(hi, nd)}]"


def _pct(k, n) -> str:
    lo, hi = wilson(k, n)
    return f"{k}/{n} [{lo * 100:.0f}%, {hi * 100:.0f}%]"


def by_shape(episodes: list[dict], agent: str) -> dict[str, dict[str, dict]]:
    out: dict[str, dict[str, dict]] = defaultdict(dict)
    for e in episodes:
        if e["agent"] == agent:
            out[e["shape"]][e["task"]] = e
    return out


def sizes_table(sizes: dict) -> str:
    rows = ["| Shape | Tools | Definition bytes | Est. tokens |", "|---|---:|---:|---:|"]
    for k in SHAPES:
        s = sizes["shapes"][k]
        rows.append(f"| {SHAPE_NAMES[k]} | {s['tools']} | {s['bytes']:,} | {s['est_tokens']:,} |")
    m = sizes["meta"]
    rows.append("")
    rows.append(f"Source: `results/tool_sizes.json`, {m['date']}, read over {m['transport']}. Tokens are bytes / 4, rounded up. No model.")
    return "\n".join(rows)


def oracle_table(oracle: dict) -> str:
    eps = oracle["episodes"]
    orc = by_shape(eps, "oracle")
    rows = ["| Shape | Oracle passes [95% CI] | Wrong agents pass | Calls per task [95% CI] | Round-trip tokens per task [95% CI] | Seconds per task |",
            "|---|---|---|---|---|---:|"]
    for k in SHAPES:
        ts = [orc[k][t.id] for t in TASKS]
        wrong = [e for e in eps if e["shape"] == k and e["agent"] in ("noop", "swap")]
        calls = bootstrap_mean([e["tool_calls"] for e in ts])
        rt = bootstrap_mean([tok(e["arg_bytes"] + e["result_bytes"]) for e in ts])
        secs = sum(e["seconds"] for e in ts) / len(ts)
        rows.append(f"| {SHAPE_NAMES[k]} | {_pct(sum(e['passed'] for e in ts), len(ts))} | {sum(e['passed'] for e in wrong)}/{len(wrong)} "
                    f"| {_ci(*calls)} | {_ci(*rt, nd=0)} | {secs:.3f} |")
    m = oracle["meta"]
    rows.append("")
    rows.append(f"Source: `results/oracle.json`, {m['date']}, seed {m['seed']}, transport {m['transport']}, no model (scripted oracle). "
                f"Pass intervals are Wilson. The oracle is deterministic, so its intervals describe the spread over these {len(TASKS)} tasks, not run to run noise. Mean intervals are a bootstrap over the {len(TASKS)} tasks ({BOOT_N:,} resamples, seed {BOOT_SEED}). "
                "Seconds depend on the machine in `docs/ENVIRONMENT.md`.")
    return "\n".join(rows)


def _agent_eps(run: dict) -> dict[str, dict[str, dict]]:
    out: dict[str, dict[str, dict]] = defaultdict(dict)
    for it in run["items"].values():
        if it["status"] == "done":
            e = it["episode"]
            out[e["shape"]][e["task"]] = e
    return out


SCRIPTED_NOTE = ("This is not a language model. A local fake endpoint replays the oracle's calls one per turn through the real agent loop, "
                 "so it shows the least an agent pays to make those calls.")


def cost_table(run: dict, source: str = "runs/scripted/state.json", note: str = SCRIPTED_NOTE) -> str:
    agent = _agent_eps(run)
    rows = ["| Shape | Passes [95% CI] | Model turns per task | Input tokens per task [95% CI] | Output tokens per task | Of which tool definitions |",
            "|---|---|---:|---|---:|---:|"]
    for k in SHAPES:
        ts = [agent[k][t.id] for t in TASKS if t.id in agent[k]]
        if not ts:
            continue
        inp = bootstrap_mean([e["extra"]["prompt_tokens"] for e in ts])
        out = sum(e["extra"]["completion_tokens"] for e in ts) / len(ts)
        turns = sum(e["extra"]["turns"] for e in ts) / len(ts)
        defs = sum(e["extra"]["tool_def_tokens"] for e in ts) / len(ts)
        rows.append(f"| {SHAPE_NAMES[k]} | {_pct(sum(e['passed'] for e in ts), len(ts))} | {turns:.1f} | {_ci(*inp, nd=0)} | {_fmt(out, 0)} | {_fmt(defs, 0)} |")
    m = run["meta"]
    src = {e["extra"].get("token_source") for s in agent.values() for e in s.values()}
    rows.append("")
    how = {"provider": "the usage field of each response", "estimate": "bytes / 4"}
    if m["provider"] == "local fake endpoint":
        how["provider"] = "the usage field of the local fake endpoint, which itself estimates bytes / 4"
    rows.append(f"Source: `{source}`, {m['created']}, model `{m['model']}` ({m['provider']}), transport {m['transport']}. "
                f"{note} Token counts come from {' and '.join(how[s] for s in sorted(src))}.")
    return "\n".join(rows)


def paired_table(oracle: dict, run: dict) -> str:
    orc = by_shape(oracle["episodes"], "oracle")
    agent = _agent_eps(run)
    ids = [t.id for t in TASKS]
    rows = ["| Comparison | Calls per task, difference [95% CI] | Input tokens per task, difference [95% CI] |", "|---|---|---|"]
    for k in ("B", "C"):
        dc = paired_diff([orc["A"][i]["tool_calls"] for i in ids], [orc[k][i]["tool_calls"] for i in ids])
        both = [i for i in ids if i in agent["A"] and i in agent[k]]
        dt = paired_diff([agent["A"][i]["extra"]["prompt_tokens"] for i in both], [agent[k][i]["extra"]["prompt_tokens"] for i in both])
        rows.append(f"| {k} minus A | {_ci(*dc, nd=2)} | {_ci(*dt, nd=0)} |")
    rows.append("")
    rows.append(f"Paired by task. The interval resamples the {len(ids)} task pairs. Calls come from the oracle run and tokens from the scripted agent run.")
    return "\n".join(rows)


def per_task_table(oracle: dict, run: dict) -> str:
    orc = by_shape(oracle["episodes"], "oracle")
    agent = _agent_eps(run)
    rows = ["| Task | Category | Calls A | Calls B | Calls C | Input tokens A | Input tokens B | Input tokens C |", "|---|---|---:|---:|---:|---:|---:|---:|"]
    for t in TASKS:
        tk = [agent[k].get(t.id, {}).get("extra", {}).get("prompt_tokens") for k in SHAPES]
        rows.append(f"| {t.id} | {t.category} | " + " | ".join(str(orc[k][t.id]["tool_calls"]) for k in SHAPES) + " | "
                    + " | ".join(f"{x:,}" if x is not None else "n/a" for x in tk) + " |")
    return "\n".join(rows)


def category_wins(oracle: dict, run: dict) -> list[dict]:
    orc = by_shape(oracle["episodes"], "oracle")
    agent = _agent_eps(run)
    cats: dict[str, list[str]] = defaultdict(list)
    for t in TASKS:
        cats[t.category].append(t.id)
    out = []
    for cat, ids in cats.items():
        calls = {k: sum(orc[k][i]["tool_calls"] for i in ids) / len(ids) for k in SHAPES}
        toks = {}
        for k in SHAPES:
            have = [agent[k][i]["extra"]["prompt_tokens"] for i in ids if i in agent[k]]
            toks[k] = sum(have) / len(have) if len(have) == len(ids) else float("inf")
        out.append({"category": cat, "tasks": len(ids), "calls": calls, "tokens": toks,
                    "fewest_calls": min(SHAPES, key=lambda k: (calls[k], k)), "fewest_tokens": min(SHAPES, key=lambda k: (toks[k], k))})
    return out


CATEGORY_TEXT = {
    "single": "one change to one known record",
    "names": "the task names people or projects, not ids",
    "multi": "a few dependent steps",
    "bulk": "the same change to many records",
    "lookup": "a question answered by reading and counting",
}


def _n(x: float) -> str:
    return "n/a" if x == float("inf") else f"{x:,.0f}"


def wins_table(oracle: dict, run: dict) -> str:
    rows = ["| Category | What it means | Tasks | Mean calls A / B / C | Mean input tokens A / B / C | Fewest tokens |", "|---|---|---:|---|---|---|"]
    for w in category_wins(oracle, run):
        c, t = w["calls"], w["tokens"]
        rows.append(f"| {w['category']} | {CATEGORY_TEXT.get(w['category'], '')} | {w['tasks']} | "
                    f"{c['A']:.1f} / {c['B']:.1f} / {c['C']:.1f} | {' / '.join(_n(t[k]) for k in SHAPES)} | {w['fewest_tokens']} |")
    rows.append("")
    rows.append("Computed from the oracle run and the scripted agent run. A real model adds wrong turns and retries that these numbers leave out.")
    return "\n".join(rows)


def model_status(record_state: Path | None) -> str:
    if record_state and Path(record_state).exists():
        run = load(record_state)
        return cost_table(run, source=str(record_state), note="A real model, recorded with `toolcut record`.")
    return ("No run with a real model yet. The build machine had no provider key and could not reach api.groq.com or openrouter.ai "
            "(see `BLOCKERS.md`). `docs/HUMAN_STEPS.md` gives the two commands that record one.")


def status_line(sizes: dict, oracle: dict, has_model: bool = False) -> str:
    orc = [e for e in oracle["episodes"] if e["agent"] == "oracle"]
    wrong = [e for e in oracle["episodes"] if e["agent"] != "oracle"]
    n = oracle["meta"]["tasks"]
    per = {k: sum(e["passed"] for e in orc if e["shape"] == k) for k in SHAPES}
    solved = f"{per['A']} of {n} tasks in every shape" if len(set(per.values())) == 1 else ", ".join(f"{v} of {n} in {k}" for k, v in per.items())
    a, c = sizes["shapes"]["A"]["bytes"], sizes["shapes"]["C"]["bytes"]
    version = __version__.replace("rc", "-rc")
    return (f"**Status:** v{version}, a release candidate. The oracle solves {solved} and the wrong agents solve "
            f"{sum(e['passed'] for e in wrong)} of {len(wrong)}. Shape C's tool list is {c:,} bytes against {a:,} for shape A. "
            + ("A run with a real model is in the Results part." if has_model else
               "No real model has run yet, so the model results are blocked (see Limits)."))


def facts_line(sizes: dict) -> str:
    from .taskdesk.ops import OPS

    cats = sorted({t.category for t in TASKS})
    t = {k: sizes["shapes"][k]["tools"] for k in SHAPES}
    return (f"TaskDesk has {len(OPS)} endpoints. The benchmark has {len(TASKS)} tasks in {len(cats)} categories "
            f"({', '.join(cats)}). Shape A has {t['A']} tools, shape B has {t['B']} and shape C has {t['C']}.")


def sections(root: Path) -> dict[str, str]:
    res = root / "results"
    sizes = load(res / "tool_sizes.json")
    oracle = load(res / "oracle.json")
    run = load(root / "runs" / "scripted" / "state.json")
    return {
        "status": status_line(sizes, oracle, (root / "runs" / "model" / "state.json").exists()),
        "facts": facts_line(sizes),
        "sizes": sizes_table(sizes),
        "results": oracle_table(oracle),
        "cost": cost_table(run),
        "paired": paired_table(oracle, run),
        "wins": wins_table(oracle, run),
        "per_task": per_task_table(oracle, run),
        "model": model_status(root / "runs" / "model" / "state.json"),
    }


def full_report(root: Path) -> str:
    s = sections(root)
    parts = [
        "# toolcut report", "",
        "Generated by `toolcut report`. Do not edit by hand.", "",
        "## Tool definition sizes", "", s["sizes"], "",
        "## Oracle and wrong agents over MCP", "", s["results"], "",
        "## Cost per task through the agent loop", "", s["cost"], "",
        "## Paired differences against shape A", "", s["paired"], "",
        "## When each shape wins", "", s["wins"], "",
        "## Real model run", "", s["model"], "",
        "## Per task", "", s["per_task"], "",
    ]
    return "\n".join(parts)


START = "<!-- toolcut:{}:start -->"
END = "<!-- toolcut:{}:end -->"


def fill(text: str, secs: dict[str, str]) -> str:
    for name, body in secs.items():
        a, b = START.format(name), END.format(name)
        if a not in text:
            continue
        head, rest = text.split(a, 1)
        _old, tail = rest.split(b, 1)
        text = f"{head}{a}\n{body}\n{b}{tail}"
    return text


def stale(text: str, secs: dict[str, str]) -> list[str]:
    """Names of sections whose README text differs from what the results files give."""
    out = []
    for name, body in secs.items():
        a, b = START.format(name), END.format(name)
        if a in text:
            cur = text.split(a, 1)[1].split(b, 1)[0].strip("\n")
            if cur != body:
                out.append(name)
    return out


def est(nbytes: int) -> int:
    """Tokens for a byte count, the same estimate the agent uses."""
    return math.ceil(nbytes / 4)


__all__ = ["est", "fill", "full_report", "sections", "stale"]
