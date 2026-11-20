# Blockers

| Date | What failed | Exact error | What I did instead | Manual step |
| --- | --- | --- | --- | --- |
| 2026-11-20 | `npx -y skills add DietrichGebert/ponytail -g -a claude-code -y` | Permission for this action was denied by the Claude Code auto mode classifier | Did not retry. Used the skills already present and applied the Ponytail and humanizer rules by hand. See docs/TOOLING.md | none |
| 2026-11-20 | Record-mode hosts | `api.groq.com:443`, `openrouter.ai:443`, `huggingface.co:443`: CONNECT tunnel refused by the egress proxy, HTTP 403. No `GROQ_API_KEY` or `OPENROUTER_API_KEY` in the environment | Built record mode and proved it end to end against a local fake provider. No real model run happened. The README says so | docs/HUMAN_STEPS.md: add a key or network secret, then run `toolcut record` |
| 2026-11-20 | `api.osv.dev`, `semgrep.dev` | CONNECT tunnel refused, HTTP 403 | pip-audit uses the PyPI advisory service. ruff `--select S` replaces semgrep | none |
| 2026-11-20 | `raw.githubusercontent.com/cheahjs/free-llm-api-resources/main/README.md` | HTTP 404 (wrong default branch path) | The record run is blocked anyway. Recheck the free limits before the first real record run | docs/HUMAN_STEPS.md |
