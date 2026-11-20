# Tooling

| Tool | Version | Used for | How it got here | Check |
| --- | --- | --- | --- | --- |
| uv | 0.11 | venv and installs | present | n/a |
| mcp (Python SDK) | 2.3.0 | the three MCP servers and the test client | `uv pip install` via `pyproject.toml` | pip-audit, see docs/RELEASE_CHECK.md |
| ruff | from `.[dev]` | lint, and `--select S` security rules | `./init.sh` | n/a |
| pytest | from `.[dev]` | tests | `./init.sh` | n/a |
| gitleaks | v8.30.1 | secret scan, pre-commit hook | `go install github.com/zricethezav/gitleaks/v8@v8.30.1` | n/a |
| actionlint | v1.7.12 | CI workflow lint | `go install github.com/rhysd/actionlint/cmd/actionlint@latest` | n/a |
| pip-audit, pre-commit, cisco-ai-mcp-scanner | latest at build time | release check and MCP tool scan | `uv tool install` | see docs/SECURITY_CHECKS.md |

## Skills

The build prompt asks for the ponytail, caveman, humanizer, find-skills and security-audit skills. `npx skills add` was denied by the permission system on 2026-11-20 and not retried. The build used the skills already present (superpowers, the built-in security-review and simplify skills) and applied the Ponytail and humanizer rules by hand. graphify was not needed because this was a first run.
