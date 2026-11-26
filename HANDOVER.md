# Handover

For a fresh session that picks this up.

- Repo: the local clone, branch `claude/build-toolshape`. Remote: origin (GitHub).
- Push with `git push -u origin HEAD`. Never push main, never tag, never force push.
- Run `./init.sh` before and after a change. gitleaks and actionlint are in `~/go/bin`. pip-audit and mcp-scanner were installed with `uv tool`.
- Read PROGRESS.md for what is done and next, BLOCKERS.md for what cannot be done here, DECISIONS.md for why.
- The model block in the README stays "No run with a real model yet" unless a key and network access appear. Do not invent fixtures. The scripted run in `runs/scripted/` is labeled as not a model everywhere.
- After any change to results: `toolcut report`, `toolcut readme`, `scripts/make_site.py`, `scripts/make_social_preview.py`, `scripts/make_demo.sh`.

Release commit: 84a5e62f4580d08cabb6747a2b6eb1a6ab52cec5.
