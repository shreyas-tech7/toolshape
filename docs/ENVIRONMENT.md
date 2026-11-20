# Environment

Probed once on 2026-11-20 from the build machine with `curl -sS -o /dev/null -w '%{http_code}' -m 10 <url>`.

| Host | Result |
| --- | --- |
| pypi.org `toolshape` | 404 |
| registry.npmjs.org `toolshape` | 200 (taken) |
| pypi.org `toolcut` | 404 (free) |
| registry.npmjs.org `toolcut` | 404 (free) |
| pypi.org `mcp` | 200, newest 2.3.0, needs Python 3.10 or newer |
| api.groq.com | CONNECT tunnel 403 |
| openrouter.ai | CONNECT tunnel 403 |
| huggingface.co | CONNECT tunnel 403 |
| api.osv.dev, semgrep.dev | CONNECT tunnel 403 |
| proxy.golang.org | works (installed gitleaks v8.30.1 and actionlint v1.7.12) |

No model provider key is set.

## Machine

- Intel(R) Xeon(R) Processor @ 2.30GHz, 4 cores visible, 16 GB RAM.
- Python 3.13 in `.venv` made by uv. CI uses Python 3.11.
- Go 1.24 (it fetched go 1.26.11 to build gitleaks and actionlint).

## What this means

- Everything except record mode runs here.
- Record mode against a real model cannot run here. It is tested against a local fake provider. See BLOCKERS.md.
