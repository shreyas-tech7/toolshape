# Changelog

## v0.1.0-rc1 (2026-11-20)

Release commit: 84a5e62f4580d08cabb6747a2b6eb1a6ab52cec5.

First release candidate.

- TaskDesk, a fake project tracker API on 127.0.0.1 with a fixed clock and seeded data.
- Three MCP tool shapes over it: one tool per endpoint, task-sized tools, and search_api with run_code.
- A run_code sandbox with CPU, memory and wall time limits, an audit hook and an AST allowlist.
- Forty tasks in five categories with an end state scorer that also checks nothing else changed.
- An oracle that solves every task in every shape and two wrong agents that fail every task.
- An agent loop for OpenAI-compatible endpoints with record mode, fixtures and offline replay.
- A resumable record runner over task, shape and repeat.
- A report with intervals, paired differences, a per-task breakdown and a guide to when each shape wins.
- No run with a real model yet. See BLOCKERS.md.
