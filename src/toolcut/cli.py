"""toolcut command line. Every results file and README table comes from one of these commands."""

from __future__ import annotations

import argparse
import json
import platform
import sys
import time
from pathlib import Path

from . import __version__

ROOT = Path.cwd()


def _today() -> str:
    return time.strftime("%Y-%m-%d", time.gmtime())


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1, sort_keys=True) + "\n")


def cmd_oracle(a) -> int:
    from .harness import run_episode
    from .sessions import open_session
    from .taskdesk.db import SEED
    from .taskdesk.server import TaskDeskServer
    from .tasks import TASKS

    episodes = []
    with TaskDeskServer() as server:
        for shape in a.shapes:
            with open_session(shape, server.url, a.transport) as session:
                for agent in ("oracle", "noop", "swap"):
                    for t in TASKS:
                        ep = run_episode(server, session, t, shape, agent)
                        episodes.append(ep.as_dict())
            ok = sum(e["passed"] for e in episodes if e["shape"] == shape and e["agent"] == "oracle")
            bad = sum(e["passed"] for e in episodes if e["shape"] == shape and e["agent"] != "oracle")
            print(f"shape {shape}: oracle {ok}/{len(TASKS)}, wrong agents passed {bad}")
    meta = {"date": _today(), "seed": SEED, "transport": a.transport, "python": platform.python_version(), "tasks": len(TASKS)}
    _write_json(Path(a.out), {"meta": meta, "episodes": episodes})
    orc = [e for e in episodes if e["agent"] == "oracle"]
    wrong = [e for e in episodes if e["agent"] != "oracle"]
    good = all(e["passed"] for e in orc) and not any(e["passed"] for e in wrong)
    print(f"wrote {a.out}: {'all checks hold' if good else 'CHECK FAILED'}")
    return 0 if good else 1


def _tool_defs(shape: str, transport: str, url: str) -> list[dict]:
    from .sessions import open_session

    with open_session(shape, url, transport) as s:
        tools = s.list_tools()
    return [{"name": t["name"], "description": t.get("description", ""), "inputSchema": t["inputSchema"]} for t in tools]


def cmd_sizes(a) -> int:
    from .report import est
    from .taskdesk.server import TaskDeskServer

    out = {"meta": {"date": _today(), "transport": a.transport, "measure": "compact JSON of name, description and inputSchema"}, "shapes": {}}
    with TaskDeskServer() as server:
        for shape in ("A", "B", "C"):
            defs = _tool_defs(shape, a.transport, server.url)
            n = len(json.dumps(defs, separators=(",", ":"), sort_keys=True).encode())
            out["shapes"][shape] = {"tools": len(defs), "bytes": n, "est_tokens": est(n)}
            print(f"shape {shape}: {len(defs)} tools, {n} bytes, about {est(n)} tokens")
    _write_json(Path(a.out), out)
    return 0


def cmd_export_tools(a) -> int:
    from .taskdesk.server import TaskDeskServer

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    with TaskDeskServer() as server:
        for shape in ("A", "B", "C"):
            defs = _tool_defs(shape, "inprocess", server.url)
            _write_json(out / f"shape_{shape}.json", {"tools": defs})
            print(f"wrote {out / f'shape_{shape}.json'}")
    return 0


def cmd_scripted(a) -> int:
    from .agent import HttpChat
    from .fake_provider import FakeProvider, oracle_traces
    from .runner import RunConfig, run

    if a.fresh and Path(a.run_dir).exists():
        import shutil

        shutil.rmtree(a.run_dir)
    traces = oracle_traces()
    with FakeProvider(traces) as prov:
        cfg = RunConfig(Path(a.run_dir), model="fake-oracle-replay", provider_label="local fake endpoint", transport=a.transport,
                        max_turns=a.max_turns)
        state = run(cfg, lambda: HttpChat(prov.url, cfg.model), log=(lambda *_: None))
    print(f"{a.run_dir}: {state.counts()}")
    return 0 if state.counts()["done"] == len(state.items) else 1


def cmd_record(a) -> int:
    from .agent import HttpChat
    from .runner import RunConfig, run

    cfg = RunConfig(Path(a.run_dir), model=a.model, provider_label=a.base_url, shapes=tuple(a.shapes),
                    task_ids=tuple(a.tasks) if a.tasks else RunConfig.__dataclass_fields__["task_ids"].default,
                    reps=a.reps, transport=a.transport, max_turns=a.max_turns)
    state = run(cfg, lambda: HttpChat(a.base_url, a.model, key_env=a.key_env, wait=a.wait), limit=a.limit)
    print(f"{a.run_dir}: {state.counts()}")
    return 0


def cmd_replay(a) -> int:
    """Replay a recorded run from its fixtures into a fresh state file and compare outcomes."""
    import shutil

    from .runner import RunConfig, run

    src = Path(a.run_dir)
    meta = json.loads((src / "state.json").read_text())
    dst = Path(a.out)
    if (dst / "fixtures").exists():
        shutil.rmtree(dst / "fixtures")
    (dst / "state.json").unlink(missing_ok=True)
    shutil.copytree(src / "fixtures", dst / "fixtures")
    keys = list(meta["items"])
    cfg = RunConfig(dst, model=meta["meta"]["model"], mode="replay", task_ids=tuple(sorted({k.split("|")[0] for k in keys})),
                    shapes=tuple(sorted({k.split("|")[1] for k in keys})), transport=meta["meta"]["transport"],
                    max_turns=meta["meta"]["max_turns"], provider_label="replay of " + str(src))
    state = run(cfg, log=(lambda *_: None))
    diff = [k for k, it in meta["items"].items() if it["status"] == "done"
            and state.items.get(k, {}).get("episode", {}).get("passed") != it["episode"]["passed"]]
    print(f"replayed {state.counts()['done']} items, {len(diff)} outcome differences")
    return 0 if not diff else 1


def cmd_report(a) -> int:
    from .report import full_report

    Path(a.out).write_text(full_report(ROOT))
    print(f"wrote {a.out}")
    return 0


def cmd_readme(a) -> int:
    from .report import fill, sections, stale

    path = ROOT / "README.md"
    text = path.read_text()
    secs = sections(ROOT)
    if a.check:
        bad = stale(text, secs)
        if bad:
            print("README is out of date in: " + ", ".join(bad) + ". Run `toolcut readme`.")
            return 1
        print("README matches the results files")
        return 0
    path.write_text(fill(text, secs))
    print("README tables rewritten from results files")
    return 0


def cmd_demo(a) -> int:
    from .harness import run_episode
    from .sessions import open_session
    from .taskdesk.server import TaskDeskServer
    from .tasks import TASKS_BY_ID

    task = TASKS_BY_ID[a.task]
    print(f"task {task.id} ({task.category}): {task.prompt}\n")
    with TaskDeskServer() as server:
        for shape in ("A", "B", "C"):
            with open_session(shape, server.url, a.transport) as s:
                ep = run_episode(server, s, task, shape, "oracle")
                print(f"shape {shape}: {'PASS' if ep.passed else 'FAIL'}, {ep.tool_calls} tool calls, {ep.api_calls} API requests, "
                      f"{ep.arg_bytes + ep.result_bytes} bytes through the tools")
                groups: list[list] = []
                for c in s.log:
                    if groups and groups[-1][0] == c.name:
                        groups[-1][1] += 1
                        groups[-1][2] += c.arg_bytes
                        groups[-1][3] += c.result_bytes
                    else:
                        groups.append([c.name, 1, c.arg_bytes, c.result_bytes])
                for name, n, ab, rb in groups:
                    times = f" x{n}" if n > 1 else ""
                    print(f"  {name}{times}: {ab} B in, {rb} B out")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="toolcut", description="Compare three MCP tool shapes over one fixed fake API.")
    p.add_argument("--version", action="version", version=f"toolcut {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    o = sub.add_parser("oracle", help="run the oracle and the wrong agents on every task and shape")
    o.add_argument("--transport", choices=["inprocess", "mcp"], default="mcp")
    o.add_argument("--shapes", nargs="+", default=["A", "B", "C"])
    o.add_argument("--out", default="results/oracle.json")
    o.set_defaults(fn=cmd_oracle)

    s = sub.add_parser("sizes", help="measure tool definition sizes per shape")
    s.add_argument("--transport", choices=["inprocess", "mcp"], default="mcp")
    s.add_argument("--out", default="results/tool_sizes.json")
    s.set_defaults(fn=cmd_sizes)

    e = sub.add_parser("export-tools", help="write each shape's tool list as JSON, for scanners")
    e.add_argument("--out", default="out/tools")
    e.set_defaults(fn=cmd_export_tools)

    sc = sub.add_parser("scripted", help="run the agent loop against a local fake endpoint that replays the oracle")
    sc.add_argument("--run-dir", default="runs/scripted")
    sc.add_argument("--transport", choices=["inprocess", "mcp"], default="inprocess")
    sc.add_argument("--max-turns", type=int, default=100)
    sc.add_argument("--fresh", action="store_true", help="delete the run folder first and record again")
    sc.set_defaults(fn=cmd_scripted)

    r = sub.add_parser("record", help="record a resumable run against an OpenAI-compatible endpoint")
    r.add_argument("--run-dir", default="runs/model")
    r.add_argument("--base-url", required=True, help="for example https://api.groq.com/openai/v1")
    r.add_argument("--model", required=True)
    r.add_argument("--key-env", default="GROQ_API_KEY", help="name of the env var that holds the key")
    r.add_argument("--shapes", nargs="+", default=["A", "B", "C"])
    r.add_argument("--tasks", nargs="*")
    r.add_argument("--reps", type=int, default=1)
    r.add_argument("--transport", choices=["inprocess", "mcp"], default="mcp")
    r.add_argument("--max-turns", type=int, default=20)
    r.add_argument("--limit", type=int, help="stop after this many items (run again to resume)")
    r.add_argument("--wait", type=float, default=5.0, help="first wait in seconds after a 429")
    r.set_defaults(fn=cmd_record)

    rp = sub.add_parser("replay", help="replay a recorded run from its fixtures, offline")
    rp.add_argument("--run-dir", default="runs/scripted")
    rp.add_argument("--out", default="runs/scratch/replay")
    rp.set_defaults(fn=cmd_replay)

    rep = sub.add_parser("report", help="write docs/REPORT.md from the results files")
    rep.add_argument("--out", default="docs/REPORT.md")
    rep.set_defaults(fn=cmd_report)

    rd = sub.add_parser("readme", help="rewrite the README tables from the results files")
    rd.add_argument("--check", action="store_true", help="fail if the README differs from the results files")
    rd.set_defaults(fn=cmd_readme)

    d = sub.add_parser("demo", help="show one task solved in each shape")
    d.add_argument("--task", default="t07")
    d.add_argument("--transport", choices=["inprocess", "mcp"], default="mcp")
    d.set_defaults(fn=cmd_demo)

    a = p.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
