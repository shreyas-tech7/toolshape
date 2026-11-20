# Security checks

## MCP scanner on each shape's tool list

Run on 2026-11-20 with cisco-ai-mcp-scanner v4.8.7, YARA analyzer, static mode on exported tool lists. Static mode reads JSON files and starts no server.

```bash
.venv/bin/toolcut export-tools --out out/tools
mcp-scanner --analyzers yara --format summary static --tools out/tools/shape_A.json
```

| Shape | Tools scanned | Unsafe | Raw output |
|---|---:|---:|---|
| A: one tool per endpoint | 25 | 0 | [mcp-scanner-shape_A.txt](../results/security/mcp-scanner-shape_A.txt) |
| B: task-sized tools | 8 | 0 | [mcp-scanner-shape_B.txt](../results/security/mcp-scanner-shape_B.txt) |
| C: search_api + run_code | 2 | 0 | [mcp-scanner-shape_C.txt](../results/security/mcp-scanner-shape_C.txt) |

The scanner prints "Scan Target: https://mcp.deepwiki.com/mcp" as a default label in static mode. It did not scan that server. The YARA rules look for prompt injection, hidden instructions and data theft wording in tool names, descriptions and schemas. A clean result means the descriptions carry none of those patterns. It says nothing about what the code behind a tool does. The LLM and API analyzers need keys and were not run.

## What the run_code sandbox does

Shape C runs model-written Python, so it has a sandbox in `src/toolcut/sandbox.py`. Each script runs in a fresh `python -I` child process with only `PATH` and `LANG` in its environment.

- **Time:** a CPU limit through `RLIMIT_CPU` and a wall clock timeout that kills the child.
- **Memory:** an address space limit through `RLIMIT_AS`.
- **Network:** an audit hook blocks every socket connect, bind, send and DNS lookup except to the fake API's own host and port.
- **Files:** the audit hook blocks any open outside the script's temp folder, after resolving symlinks.
- **Processes:** the audit hook blocks subprocess, os.system, the exec and spawn family, fork, pty, ctypes, kill and file deletion calls.
- **Code:** before the script runs, an AST check rejects names and attributes that start with an underscore, `eval`, `exec`, `compile`, `open`, `getattr` and similar, and imports outside a short allowlist.

Each limit has a test in `tests/test_sandbox.py`, and two of them switch the AST check off to prove the audit hook holds on its own. `scripts/prove_sandbox_tests.py` turns the audit hook and the memory limit off and checks that those tests then fail, so the tests can catch a broken sandbox.

## What it does not protect

This sandbox guards the local benchmark only. It is not a security sandbox.

- Audit hooks run inside the same interpreter as the script. A bug in CPython or a C extension that gives the script raw memory access can remove them.
- The fake API is reachable on purpose, so a script can change any TaskDesk data. That is the point of shape C.
- There is no seccomp filter, no namespace and no container. For untrusted code use a real isolation layer such as a container with no network, gVisor or a microVM.

## Other checks

The release check in [RELEASE_CHECK.md](RELEASE_CHECK.md) lists gitleaks, pip-audit, `ruff check --select S` and the outside review.
