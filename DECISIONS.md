# Decisions

One line for each choice: what I picked, what I weighed, and why.

- 2026-11-20 Name: package and command are `toolcut`. Checked `toolshape`: PyPI 404 but npm 200 (an unrelated package that converts tool definitions between providers), so it is not free by the brief's rule. `toolcut`: PyPI 404, npm 404, and a web search found no well-known GitHub project. The repo stays `shreyas-tech7/toolshape`. Renaming it is optional and listed in docs/HUMAN_STEPS.md.
- 2026-11-20 Branch: origin had no `main` and no commits, so `claude/build-toolshape` starts from a fresh first commit. I did not create `main`.
- 2026-11-20 MCP SDK: pinned `mcp==2.3.0`, the newest release on PyPI on the build date. Version 2 renamed FastMCP, so the servers use the low-level `mcp.server.lowlevel.Server` with explicit `list_tools` and `call_tool` handlers. That keeps each shape's tool list exactly as written, with no schema generated from type hints.
- 2026-11-20 One shape core, two transports: each shape is a plain Python object (`list_tools`, `call_tool`). The MCP server wraps it over stdio. Tests and quick runs use the object in process. The oracle report run goes through real MCP stdio servers. Options weighed: MCP only (slow tests), in-process only (no MCP practice). The capability matrix and the MCP test prove both paths match.
- 2026-11-20 The fake API is a real HTTP server (ThreadingHTTPServer on 127.0.0.1) so every shape pays the same HTTP cost and the sandbox client reaches it the same way. The scorer reads the database through an admin dump endpoint that needs a random per-run token and is not in the operation list.
- 2026-11-20 A fixed clock: TaskDesk says today is 2026-03-15 and every created row gets that timestamp. Task prompts state the date. This makes "overdue" and end states deterministic.
- 2026-11-20 Scoring: each task has a predicate on the final database plus a collateral check. Rows the task may not touch must equal the seed. New rows are allowed only in the tables the task names. Exact state equality was rejected because a real model words comments differently.
- 2026-11-20 Every task ends in a write, so the scorer can check it. Lookup tasks write their answer into TaskDesk (a comment or a task title). This avoids a free-text answer channel that only some shapes would have.
- 2026-11-20 Oracle design: each task has one `solve(h)` function written against a small helper layer. Shape A runs the helper with each API call routed to its one-op tool. Shape C sends the helper source plus the solve source as one `run_code` script. Shape B has its own helper that maps each step to its task-sized tools. Weighed: three hand-written solutions per task (120 functions, more bugs) against one plan per task.
- 2026-11-20 Wrong agents: `noop` (does nothing) and `swap` (runs the next task's oracle solution). Both must fail all 40 tasks in all shapes. This shows the scorer rejects both "nothing happened" and "something plausible but wrong happened".
- 2026-11-20 Token counts: tool definition size is the JSON of the MCP tool list, counted in bytes and estimated tokens (bytes / 4, rounded up). No tokenizer package, to keep dependencies at `mcp` only. The README says the counts are estimates. In record mode the provider's `usage` field wins when present.
- 2026-11-20 Intervals: success uses the Wilson 95% interval (a count with a fixed denominator). Means use a seeded percentile bootstrap (2,000 resamples, seed 7). Paired shape differences use a paired bootstrap over tasks. Oracle call counts and sizes are fixed counts with no sampling error, and the README says so.
- 2026-11-20 Sandbox AST rule also forbids any attribute or name that starts with `_`, plus `getattr`, `setattr`, `delattr`, `globals`, `locals`, `vars`, `__import__`, `open` stays allowed so the audit hook test can show it is limited to the temp dir.
- 2026-11-20 Third-party skills (ponytail, caveman, humanizer, security-audit, find-skills): `npx skills add` was denied by the permission system. Not retried. Ponytail and humanizer rules are applied by hand, and the release check uses the skills already present (superpowers, security-review, simplify).
- 2026-11-20 Assumption for the plan: the brief is the spec, so no question rounds. Each assumption is in docs/PLAN.md and here.

## 16. Scripted agent run stands in for a model run
The model hosts are blocked and there is no key, so no real model can run here. A local fake endpoint replays the oracle's calls one per turn through the real agent loop. That gives a lower bound on what an agent pays in tokens per shape, and it exercises record mode, fixtures and replay end to end. The README and report say plainly that it is not a model.

## 17. Scripted run allows 100 turns
Two lookup tasks need about 80 calls in shapes A and B when made one per turn. At 40 turns those episodes stopped early and failed, which measured the turn cap and not the shape. The scripted run uses 100 turns. Real record runs default to 20 turns, and the README notes that a real model can batch calls in one turn.

## 18. Token counts are bytes / 4
The prompt asks for provider usage when it exists. The agent reads `usage` when present and marks the episode `provider`, otherwise it estimates bytes / 4 and marks it `estimate`. The fake endpoint fills `usage` with the same estimate, so the scripted numbers are estimates either way, and the report says so.

## 19. Cited numbers in the README prose
The project rule is that no number is typed into the README. The generated blocks follow it. The related work part quotes the AIMultiple figures by name and link, because the prompt asks for that comparison, and the 10-minute heading and the 95% in the glossary name a method, not a result.

## 20. Exported tool lists use the tools/list shape
`toolcut export-tools` writes `{"tools": [...]}` for each shape, which is what `mcp-scanner static --tools` reads.
