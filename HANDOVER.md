# Handover

For a fresh session that picks this up.

- Repo: /home/user/toolshape, branch `claude/build-toolshape`. Remotes: origin (GitHub, private) and backup (/mnt/project-files/portfolio/remotes/toolshape.git).
- Push with `git push -u origin HEAD` and `git push backup HEAD`. Never push main, never tag, never force push.
- Run `./init.sh` before and after a change. gitleaks and actionlint are in `~/go/bin`. pip-audit and mcp-scanner were installed with `uv tool`.
- Read PROGRESS.md for what is done and next, BLOCKERS.md for what cannot be done here, DECISIONS.md for why.
- The model block in the README stays "No run with a real model yet" unless a key and network access appear. Do not invent fixtures. The scripted run in `runs/scripted/` is labeled as not a model everywhere.
- After any change to results: `toolcut report`, `toolcut readme`, `scripts/make_site.py`, `scripts/make_social_preview.py`, `scripts/make_demo.sh`.
- At the end: bundle to /mnt/project-files/portfolio/bundles/toolshape.bundle, report to /mnt/project-files/portfolio/reports/toolshape.md, and set row 8 of /mnt/project-files/portfolio/QUEUE.md.

Release commit: this commit.
