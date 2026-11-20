# Interview questions and answers

Short answers to the questions this project invites, with the files that back each one. The numbers live in [REPORT.md](REPORT.md), so this page names files instead of quoting figures.

## What does toolcut measure?

It measures how the design of MCP tools changes what an agent pays and whether it succeeds, with the API, tasks, scorer and agent loop held fixed. The three designs are one tool per endpoint, task-sized tools, and search plus run code. See `src/toolcut/shapes/`.

## Why hold the API fixed?

A fixed API isolates the design choice. If you compare two real MCP servers, they differ in API, data, error messages and task difficulty all at once, so you cannot say which difference moved the result. Here every shape calls the same typed client over the same seeded data, and `tests/test_capability_matrix.py` proves every operation has the same effect through every shape. So a gap in the results comes from the tool layer, within the limits of one fake API, 40 tasks and a scripted agent that is not a language model.

## What does each shape cost in tokens?

Shape A pays for every endpoint's definition on every turn and for every intermediate result, which piles up in the history. Shape B sends fewer, larger definitions and needs fewer steps for name lookups and bulk changes. Shape C sends two small definitions and does the work in one script, so its input cost stays flat across tasks, but the script itself is output. The per-shape and per-category numbers are in `results/tool_sizes.json` and `runs/scripted/state.json`, rendered by `src/toolcut/report.py`.

## Where does shape C win, and where does it lose?

It wins most on lookups that read many pages, because the reading happens inside the sandbox and only the answer comes back. On a single known change it is no better than shape A or B, because it still pays for a search and a script. Its real risk is that the model has to write correct code, and only a run with a real model measures that.

## Why does the oracle matter?

The oracle runs a known correct plan for each task through each shape's own tools. If it fails, the shape cannot do the task or the task is wrong, and no model number would mean anything. It solves every task in every shape in `results/oracle.json`.

## Why have wrong agents?

A scorer that passes everything is useless. The noop agent changes nothing and the swap agent solves the next task instead. Both fail every task, which shows the checks catch a missing change and a wrong change. See `src/toolcut/oracle.py` and `tests/test_oracle.py`.

## How does the scorer avoid rewarding side effects?

After the task's own check, a collateral check compares every row the task was not allowed to touch against the seed, and new rows are allowed only in the tables the task names. An agent that deletes the wrong task fails even if it also does the right thing. See `src/toolcut/scorer.py`.

## What does the sandbox protect, and what does it not?

It stops a run_code script from opening sockets other than the fake API, opening files outside its temp folder, starting processes, running past its CPU or wall time and using too much memory. It does this with rlimits, a timeout, a CPython audit hook, an AST check and restricted builtins that hand out public-only copies of the allowed modules. An outside check found four ways past an earlier version through Python introspection, such as walking generator frames to reach the hook's settings. I fixed each and added a test, but audit hooks run in the same interpreter as the script, so more paths like that likely exist, and it has no seccomp, namespaces or container. It guards this local benchmark only and is not a security sandbox. See `src/toolcut/sandbox.py` and `docs/SECURITY_CHECKS.md`.

## How do you know the sandbox tests can fail?

`scripts/prove_sandbox_tests.py` turns the audit hook and the memory limit off and runs the sandbox tests again. They fail, which shows they test the sandbox and not something else. Two tests in `tests/test_sandbox.py` also switch the AST check off to show the audit hook holds by itself.

## How is tool output kept as data?

The agent loop returns each tool result as a tool message, never as a system or user message, and the system prompt says tool results are never instructions. The loop only acts on tool calls the model makes. `tests/test_agent_loop.py` plants an instruction in a comment and checks that the loop makes no extra call. This lowers the risk of prompt injection through data. It does not remove it.

## Why only one model, and why is that a limit?

The prompt allows one free model, and this machine had none. Even with one, its results say how that model handles these shapes, not how every model does. A stronger coder would likely do better with shape C and a weaker one worse. The README says so in its Limits part.

## Why is a fake API a limit?

A fake API is a limit on what the results can claim. TaskDesk is small and tidy. A real API has hundreds of endpoints, inconsistent naming and rate limits. More endpoints make shape A's definitions larger and shape C's search more useful, so the real gap is likely bigger, but the benchmark cannot show that. Synthetic numbers do not prove behavior on a real service.

## How are the token counts made?

When a provider returns a usage field, the loop uses it and marks the episode as provider counted. Otherwise it estimates bytes divided by four and marks it as an estimate. The scripted run's fake endpoint fills usage with the same estimate, so its numbers are estimates. See `src/toolcut/agent.py`.

## What makes the record run resumable?

`src/toolcut/runner.py` keeps a state file with one entry per task, shape and repeat, each pending, done or failed. It rewrites the file atomically after every item. Running the same command again skips done items and retries failed ones up to a limit. `tests/test_record_run.py` stops a run partway and resumes it.

## How do you stop the README from drifting?

No number is typed into it. `toolcut readme` writes each table from a results file between markers, `toolcut readme --check` fails when they differ, and CI runs the check. `tests/test_readme_sync.py` edits a number by hand and confirms the check catches it.

## What would you do next?

Record a run with a real free model in all three shapes, then a second model to see whether the ranking holds. After that, add a fourth shape that loads tool definitions on demand, and grow the API to see how the gap changes with size.
