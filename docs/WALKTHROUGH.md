# Walkthrough

A tour of every file, in the order a request flows through the code. Read it with the code open.

## 1. The fixed API

TaskDesk is a small invented project tracker. Holding it fixed is what lets the benchmark compare tool designs and nothing else.

- `src/toolcut/taskdesk/ops.py` lists every endpoint once: its name, method, path, parameters and whether it writes. Everything else is built from this list, so the shapes cannot drift apart.
- `src/toolcut/taskdesk/db.py` holds the seeded data and the rules, like "an assignee must be an active member of the project". The clock is fixed and the seed is fixed, so every run starts from the same state.
- `src/toolcut/taskdesk/server.py` serves the endpoints over HTTP on 127.0.0.1 with the standard library only. Two admin routes, guarded by a token, dump and reset the data for the scorer.
- `src/toolcut/taskdesk/client.py` is the typed Python client. Shapes B and C call it, and so does the run_code sandbox.
- `src/toolcut/taskdesk/__init__.py` exports those pieces.

## 2. The three shapes

- `src/toolcut/shapes/base.py` defines a shape as a tool list plus a dispatch method. It turns every error into tool output with an error flag, so an agent never sees a crash.
- `src/toolcut/shapes/shape_a.py` makes one tool per endpoint straight from `ops.py`.
- `src/toolcut/shapes/shape_b.py` has task-sized tools. They accept names as well as ids, read every page for you and update many tasks in one call.
- `src/toolcut/shapes/shape_c.py` has `search_api`, which ranks client methods by word overlap, and `run_code`, which hands a script to the sandbox.
- `src/toolcut/shapes/example_grouped.py` is shape D from the shape guide. It is not part of the benchmark.
- `src/toolcut/shapes/__init__.py` holds the `SHAPES` registry.
- `src/toolcut/sandbox.py` runs a script in a child process with CPU and memory limits, a wall clock timeout, an audit hook that blocks network, files and processes, and an AST check that rejects dunders and dangerous names.

## 3. MCP and sessions

- `src/toolcut/mcp_server.py` serves one shape over MCP stdio with the low level server from the MCP SDK. It refuses any API address that is not local.
- `src/toolcut/sessions.py` gives the harness one interface for both transports: in process for fast tests and a real MCP client for the measured runs. Every session logs each call's bytes and time.

## 4. Tasks and scoring

- `src/toolcut/tasks.py` has the forty tasks. Each one has a prompt, a check on the end state and the tables it may touch.
- `src/toolcut/scorer.py` runs the task's check and then a collateral check: rows the task should not touch must equal the seed.

## 5. Agents without a model

- `src/toolcut/oracle_helpers.py` is a small helper layer used by every plan.
- `src/toolcut/solutions.py` has one plan per task, written against those helpers.
- `src/toolcut/oracle.py` runs a plan through each shape: through per-endpoint tools for A, through task-sized tools for B and as one script for C. It also defines the noop and swap wrong agents.
- `src/toolcut/harness.py` runs one episode: reset the API, run the agent, dump the end state and score it.

## 6. The agent loop

- `src/toolcut/agent.py` is a tool-calling loop for any OpenAI-compatible endpoint. It sends tool results back as data, records exchanges to fixtures, replays them and counts tokens from the provider or by estimate.
- `src/toolcut/fake_provider.py` is a local endpoint that replays the oracle's calls one per turn. It is how the loop runs with no model.
- `src/toolcut/runner.py` is the resumable record run, a state machine over task, shape and repeat with pending, done and failed states.

## 7. Numbers

- `src/toolcut/metrics.py` has the Wilson interval, the bootstrap and the paired bootstrap.
- `src/toolcut/report.py` turns the results files into tables for the README, the report and the site.
- `src/toolcut/cli.py` is the `toolcut` command. Every results file comes from one of its subcommands.
- `src/toolcut/__init__.py` holds the version.
- `results/tool_sizes.json`, `results/oracle.json` and `runs/scripted/state.json` are the committed results. `runs/scripted/fixtures/` holds one fixture per scripted episode.
- `results/security/` holds the raw scanner output: `mcp-scanner-shape_A.txt`, `mcp-scanner-shape_B.txt` and `mcp-scanner-shape_C.txt`.

## 8. Tests

- `tests/conftest.py` blocks every network connection that is not local and starts a fresh API for each test.
- `tests/test_network_guard.py` proves the guard works.
- `tests/test_fakeapi.py` covers the API's routes and rules.
- `tests/test_tasks.py` checks that each task's check fails on the seed and that tasks are well formed.
- `tests/test_shapes.py` covers each shape's tools and errors.
- `tests/test_capability_matrix.py` runs every operation through every shape and checks the effect is the same.
- `tests/test_sandbox.py` covers network, files, time, memory and processes.
- `tests/test_mcp_servers.py` starts the real MCP servers.
- `tests/test_oracle.py` runs the oracle and the wrong agents on all tasks.
- `tests/test_agent_loop.py` covers the loop, both token paths, fixtures, retries and tool output as data.
- `tests/test_record_run.py` stops and resumes a record run.
- `tests/test_metrics.py`, `tests/test_report.py`, `tests/test_readme_sync.py` and `tests/test_cli.py` check the numbers and the pages.
- `tests/test_shape_guide.py` runs the shape guide's example.
- `tests/test_repo_quality.py` checks the files, the writing rules, the study kit and the hand-off.

## 9. Scripts and pages

- `scripts/make_site.py` writes `docs/index.html`. `scripts/make_social_preview.py` draws `docs/social-preview.png`. Both have a `--check` mode used by CI.
- `scripts/make_demo.sh` writes `docs/DEMO.md` from a real terminal session.
- `scripts/check_links.py` checks every relative link offline.
- `scripts/prove_sandbox_tests.py` breaks the sandbox on purpose and checks that its tests then fail.
- `README.md` is the front page. `docs/REPORT.md` is the full report.

## 10. Project files

- `init.sh` installs, lints and tests. `pyproject.toml` declares the package. `.github/workflows/ci.yml` runs the same steps on GitHub. The issue templates live under `.github/ISSUE_TEMPLATE/`.
- `.env.example` names the key variables. `.gitignore` keeps keys and build output out. `.pre-commit-config.yaml` runs gitleaks.
- `LICENSE` is MIT. `CHANGELOG.md`, `CONTRIBUTING.md`, `docs/GITHUB_ABOUT.md` and `docs/topics.txt` are for the GitHub page.
- `CLAUDE.md`, `PROJECT_CONTEXT.md`, `PROGRESS.md`, `feature_list.json`, `HANDOVER.md`, `DECISIONS.md` and `BLOCKERS.md` let a new session pick up the work.
- `docs/PLAN.md`, `docs/ENVIRONMENT.md` and `docs/TOOLING.md` record the plan, the machine and the tools. `docs/build/BUILD_PROMPT.md` is the prompt the build followed.
- `docs/ADDING_A_SHAPE.md` is the shape guide. `docs/SECURITY_CHECKS.md` covers the scanner and the sandbox.
- `docs/INTERVIEW_QA.md` and this WALKTHROUGH.md are the study kit. `docs/RELEASE_CHECK.md`, `docs/HUMAN_STEPS.md` and `docs/handoff/COWORK_PROMPT.md` are the hand-off.
