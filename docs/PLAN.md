# Plan

The brief in docs/build/BUILD_PROMPT.md (Part 2) is the spec. This plan turns it into build steps. Assumptions are marked and also logged in DECISIONS.md.

## Goal

Measure how tool shape changes an agent's success, tool calls, tokens and time, with the API held fixed.

## Architecture

1. `toolcut.taskdesk`: the fake API. `ops.py` lists the 25 operations. `db.py` holds seeded data and the logic. `server.py` serves it on 127.0.0.1. `client.py` is the typed client.
2. `toolcut.shapes`: shape A (one tool per operation), shape B (task-sized tools), shape C (`search_api` and `run_code`). Each shape is a plain object with `list_tools()` and `call_tool(name, args)`.
3. `toolcut.sandbox`: runs a `run_code` script in a child process with rlimits, a wall-clock timeout, an AST allowlist and an audit hook.
4. `toolcut.mcp_server`: wraps any shape as an MCP server over stdio with the official SDK.
5. `toolcut.tasks`: 40 tasks with a predicate on the final database and a collateral check. `toolcut.scorer` reads the database through the admin dump.
6. `toolcut.oracle`: one solve plan per task, run through each shape. Wrong agents `noop` and `swap`.
7. `toolcut.agent`: a minimal OpenAI-compatible tool-calling loop. Record mode saves each exchange to a fixture. Replay mode reads them back. A local fake provider tests the loop offline.
8. `toolcut.runner`: the resumable state machine over (task, shape, repetition).
9. `toolcut.metrics` and `toolcut.report`: Wilson and bootstrap intervals, paired differences, the README tables, the results page.

## Steps (build order from the brief)

1. Initializer files, then the fake API and its tests.
2. The 40 tasks and the scorer.
3. Shapes A, B, C (`search_api` first).
4. The sandbox and its limit tests.
5. The capability matrix test.
6. Oracle agents and wrong agents. MCP servers.
7. Tool definition sizes.
8. Agent loop with fixture replay.
9. Resumable record run. The real record run is blocked here (no key, provider hosts refused), so it is tested with the fake provider.
10. Report, shape guide, README, study kit, release check, hand-off.

## Assumptions

- A1: "About 25 endpoints" means exactly 25 operations.
- A2: The brief allows `mcp` as the only runtime dependency. Everything else is standard library.
- A3: Token sizes are estimated as bytes / 4 when no provider usage field exists.
- A4: The oracle run that feeds the README goes through real MCP stdio servers, so its latency includes the protocol.
- A5: Lookup tasks write their answer into TaskDesk so every task has a checkable end state.
