# Demo

A real terminal session, written by `scripts/make_demo.sh` on 2026-11-20. Each block shows the exit code. No model and no network.

## One task in each shape, over MCP

```console
$ toolcut demo --task t07
task t07 (single): Delete task 59.

shape A: PASS, 1 tool calls, 1 API requests, 28 bytes through the tools
  delete_task: 14 B in, 14 B out
shape B: PASS, 1 tool calls, 1 API requests, 33 bytes through the tools
  delete_tasks: 17 B in, 16 B out
shape C: PASS, 2 tool calls, 1 API requests, 6308 bytes through the tools
  search_api: 13 B in, 1863 B out
  run_code: 4427 B in, 5 B out
(exit code 0)
```

## A lookup task, where the shapes differ most

```console
$ toolcut demo --task t33
task t33 (lookup): Find the user who wrote the most comments and give that user the admin role.

shape A: PASS, 77 tool calls, 77 API requests, 23928 bytes through the tools
  list_tasks x4: 40 B in, 17191 B out
  list_comments x72: 999 B in, 5572 B out
  update_user: 28 B in, 98 B out
shape B: PASS, 74 tool calls, 80 API requests, 22230 bytes through the tools
  find_tasks: 2 B in, 14364 B out
  comments x72: 2151 B in, 5572 B out
  users: 43 B in, 98 B out
shape C: PASS, 2 tool calls, 77 API requests, 6494 bytes through the tools
  search_api: 13 B in, 1863 B out
  run_code: 4613 B in, 5 B out
(exit code 0)
```

## Tool definition sizes

```console
$ toolcut sizes --out out/demo/tool_sizes.json
shape A: 25 tools, 8265 bytes, about 2067 tokens
shape B: 8 tools, 4739 bytes, about 1185 tokens
shape C: 2 tools, 1136 bytes, about 284 tokens
(exit code 0)
```

## The oracle and the wrong agents in shape C

```console
$ toolcut oracle --transport mcp --shapes C --out out/demo/oracle-c.json
shape C: oracle 40/40, wrong agents passed 0
wrote out/demo/oracle-c.json: all checks hold
(exit code 0)
```

## Replay the scripted agent run from its fixtures

```console
$ toolcut replay --out out/demo/replay
replayed 120 items, 0 outcome differences
(exit code 0)
```

## Confirm the README tables

```console
$ toolcut readme --check
README matches the results files
(exit code 0)
```

