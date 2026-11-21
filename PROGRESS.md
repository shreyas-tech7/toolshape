# Progress

## Done
- F01 to F13 and F15 to F20: the fake API, the 40 tasks and scorer, shapes A, B and C, the sandbox, the capability matrix, MCP servers, the oracle and wrong agents, the CLI, tool sizes, the agent loop with record and replay, the resumable runner, metrics and report, the shape guide, the README, CI, the site, the social preview, the scanner checks and the study kit.
- F14 is blocked with a fallback: the scripted run in `runs/scripted/` drives the real agent loop against a local fake endpoint. BLOCKERS.md and docs/HUMAN_STEPS.md step 6 cover the real run.

- F21: the release check is in docs/RELEASE_CHECK.md, with every code review and outside check finding and what was done.
- F22: the hand-off files are in place. The release commit is 84a5e62f4580d08cabb6747a2b6eb1a6ab52cec5. The commit after it records that SHA in CHANGELOG.md, docs/HUMAN_STEPS.md and HANDOVER.md and changes only hand-off files.

## Next
- Shreyas: the steps in docs/HUMAN_STEPS.md (pull request, tag, a real model run, making the repo public).
- Stretch: a fourth shape that loads tool definitions on demand.

## Open blockers
- Record mode against a real model (no key, hosts refused). See BLOCKERS.md.

## Last ./init.sh
- 2026-11-20: pass, 258 tests.
