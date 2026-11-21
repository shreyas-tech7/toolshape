# Prompt for Claude Cowork

Paste everything below the line into Claude Cowork.

---

You are helping Shreyas finish the browser steps for the private GitHub repo `shreyas-tech7/toolshape`. Read `docs/HUMAN_STEPS.md` in the repo first.

Do only steps that are free and can be undone:

1. Open the Actions tab and report whether the latest `CI` run on `main` and on `claude/build-toolshape` is green. If one is red, copy the failing step name and its last lines.
2. In Settings, General, check that `main` exists and is the default branch. If not, tell Shreyas. Do not change it unless Shreyas says so.
3. Check the About box. The description should match `docs/GITHUB_ABOUT.md` and the topics should match `docs/topics.txt`. Fill in what is missing.
4. Upload `docs/social-preview.png` as the social preview in Settings, General.
5. Check the Releases page for a `v0.1.0-rc1` pre-release on the release commit named in `docs/HUMAN_STEPS.md`. Report what you see.

Do not:

- make the repo public,
- rename the repo,
- publish a package,
- enter any key, token or secret,
- sign in for Shreyas or create an account,
- pay for anything or change a billing setting,
- delete a branch, a tag or a release.

When you finish, write a short report of what you checked and changed. Then end with this prompt for the next Claude Code session, filled in:

> Context: toolcut holds one fake API fixed and compares three MCP tool designs over it (one tool per endpoint, task-sized tools, search plus run code). It measures tool definition sizes, calls, tokens and success.
> Complete: every Done-means item except the run with a real model. The oracle solves every task in every shape, the wrong agents fail, the sandbox has tests for network, files and time, and the agent loop, record mode, fixtures and resumable runner are built and tested offline against a local fake endpoint.
> Open: the record run with a free model needs a key (see `docs/HUMAN_STEPS.md`, step 6), the stretch fourth shape that loads definitions on demand, plus anything this Cowork report found.
> Read docs/build/BUILD_PROMPT.md and follow it. Resume from PROGRESS.md on branch claude/build-toolshape. Do not ask questions. Do not stop until every Done-means item is true or blocked with a fallback.
