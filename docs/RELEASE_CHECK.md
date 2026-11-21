# Release check

Run on 2026-11-20 before the v0.1.0-rc1 release commit. Each line says what ran and what it found.

| Check | Tool | Result |
| --- | --- | --- |
| Secret scan, full git history | gitleaks v8.30.1 (built from source), `gitleaks git --redact .` | No leaks found |
| Secret scan, working tree | gitleaks v8.30.1, `gitleaks dir --redact .` | No leaks found |
| Secret scan, each commit | `gitleaks git --pre-commit --redact --staged` | Ran before every commit, no leaks |
| Dependency audit | pip-audit 2.10.1 on the 34 packages pinned by `uv pip freeze` from `.venv` | No known vulnerabilities. toolcut itself is not on PyPI, so it was left out. |
| Security lint | ruff 0.17.6, `ruff check --select S src scripts` | 0 open. 9 findings are marked with a reason (see below). |
| Security lint, tests | ruff 0.17.6, `ruff check --select S tests` | 249 findings, all expected in test code: 240 asserts, 7 fixed argument subprocess calls and 2 fake key strings used to prove a key does not leak |
| Workflow lint | actionlint v1.7.12 | No findings |
| CI steps | the steps in `.github/workflows/ci.yml`, run by hand | The test suite passes on Python 3.13 and 3.11. Lint, the README check and the link check pass on 3.13. |
| MCP tool lists | cisco-ai-mcp-scanner v4.8.7, YARA, static mode | 0 unsafe tools in each shape (`SECURITY_CHECKS.md`) |
| Sandbox tests prove they can fail | `scripts/prove_sandbox_tests.py` | The limit tests fail with the audit hook and memory limit turned off |
| Links | `scripts/check_links.py` | 0 errors. External links are listed, not fetched. |
| Writing rules | `tests/test_repo_quality.py::test_writing_rules` (humanizer rules by hand) | Pass on every doc |
| Code review | a separate review subagent and the simplify pass (ponytail rules by hand) | See below |
| Outside check | a separate subagent that read the repo cold and tried to break the claims | See below |

The ponytail, humanizer and security-audit skills could not be installed (`BLOCKERS.md`). Their checks were done with the tools above and by hand.

## ruff check --select S

- S603 (subprocess): `sandbox.py` starts the child Python with a fixed argument list, no shell and a timeout. `prove_sandbox_tests.py` runs pytest the same way.
- S310 (urlopen): `agent.py` checks in `HttpChat.__init__` that the endpoint is http or https, and refuses to send a key over plain http to a host that is not local.
- S105 (password string): `agent.py` marks `token_source = "estimate"`, a label and not a secret.
- S311 (random): `metrics.py`, `oracle.py` and `taskdesk/db.py` use seeded `random` for the bootstrap, the wrong agents and the synthetic data, not for security.

## Code review

| Finding | What was done |
| --- | --- |
| `toolcut replay --out` could point at the source run and overwrite its fixtures | Refused when the two folders are the same or nest. Tested. |
| Failed items were replayed, and the replay lost the run's reps | Replay takes only done items and keeps reps. Tested. |
| An MCP client that failed to start left its background thread running | The session closes the portal when the client fails to enter. |
| A key could go over plain http, and a file URL was accepted | `HttpChat` takes http and https only and sends a key over http only to 127.0.0.1 or localhost. Tested. |
| A resumed run could mix models, transports or turn limits | `RunState.open` refuses a different model, transport or turn limit, and runs only the items in scope. Tested. |
| `category_wins` and the wins table counted tasks with missing items | Missing items show as n/a. Tested. |
| The cost table caption did not say the scripted run is not a model | Every table and caption for that run says "not a language model". |
| `is_local_url` accepted user info and other schemes | It needs http, 127.0.0.1 or localhost, a port and no `@`. Tested. |
| `scripted --fresh` could delete a folder that is not a run | It refuses a folder with no `state.json`. Tested. |
| Connection errors stopped a record run on the first try | `HttpChat` retries lost connections like 429 and 5xx, at most 5 tries. Tested. |
| Bad tool arguments were counted but left out of the call log | They are logged as error calls. Tested. |

## Outside check

A separate subagent read the repo cold, ran the tests and tried to break the claims. It reported these findings. Each was fixed with a test, or written into the docs.

| Finding | Level | What was done |
| --- | --- | --- |
| The `run_code` sandbox could be escaped. A script reached `__main__` through `statistics.sys.modules`, or through generator frames, or through attribute walks inside `str.format`, then rewrote the audit hook's settings and read `/proc/<ppid>/environ`, ran `os.system` and connected to another local address | High | The hook keeps its settings in a closure. The script runs with restricted builtins, its imports get public-only module copies with no submodules, `taskdesk` holds only the operations, and the AST check blocks frame, code and traceback attributes, `format`, `format_map` and attributes in match patterns. Eleven new tests in `tests/test_sandbox.py`. |
| The docs said only a CPython bug could get past the sandbox | High | `README.md`, `SECURITY_CHECKS.md` and `INTERVIEW_QA.md` now say an earlier version was escaped through Python introspection and that more paths likely exist. |
| The scorer checked rows, not fields, so the right change plus an extra field edit on the same row passed | High | Each task lists the fields it may change, and list fields may change only by the allowed items. Tested on t01, t04 and t15. |
| t39 accepted any answer that contained the right ids | Medium | `id_list` takes only a plain list of ids. Tested. |
| The fake endpoint's token counts were labeled as provider usage | Medium | The caption says the fake endpoint itself estimates bytes / 4. |
| The Wilson intervals on the oracle read like run to run noise | Low | The caption says the oracle is deterministic and the intervals describe the spread over the tasks. |
| `INTERVIEW_QA.md` said any gap comes from the tools alone | Low | Narrowed to the tool layer within the limits of one fake API, 40 tasks and a scripted agent. |
| Replay passed when the loop stopped before using every recorded exchange | Low | `ReplayChat.check_used` fails the item. Tested. |
