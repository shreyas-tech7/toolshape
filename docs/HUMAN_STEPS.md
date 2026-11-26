# Human steps

Steps that only Shreyas can do, in order. While Shreyas was away, Claude was allowed to open and merge the pull request, create the pre-release and set the About box and topics. Check each of those on GitHub before you redo it.

Release commit: 84a5e62f4580d08cabb6747a2b6eb1a6ab52cec5.

The commits after the release commit only record this SHA and the hand-off notes. Tag the release commit.

## 1. Create main on GitHub, if it is missing

The GitHub repo was empty when the build started, and the build was told never to create `main`. So `claude/build-toolshape` starts from a fresh first commit, `953ef1691311d67b9f0c97abff589fbb4ce70d0a`. If `main` is still missing, create it from that commit before you open the pull request:

```bash
git fetch origin
git push origin 953ef1691311d67b9f0c97abff589fbb4ce70d0a:refs/heads/main
```

Then set `main` as the default branch in Settings, General.

## 2. Check that CI runs

Open the Actions tab. The `CI` workflow should finish green on `claude/build-toolshape` in under five minutes. The build session also ran every CI step locally and all passed.

## 3. Open and merge the pull request

1. Open a pull request from `claude/build-toolshape` into `main`, unless one is already merged.
2. Read the diff.
3. Merge with a merge commit, not a squash, so the release commit stays in the history of `main`.

## 4. Tag the release candidate

```bash
git fetch origin
git tag -a v0.1.0-rc1 84a5e62f4580d08cabb6747a2b6eb1a6ab52cec5 -m "Release candidate 1"
git push origin v0.1.0-rc1
```

Or create a pre-release with that tag on GitHub.

## 5. Run the secret scan once more

```bash
gitleaks git -v .
```

The build ran it on the full history with no findings.

## 6. Record a run with a free model

This is the step the build could not do. There was no key, and the proxy refused every model host (`BLOCKERS.md`). Until it is done, the README has no model numbers.

1. Create a free key at Groq (https://console.groq.com/keys) or OpenRouter. Check the free limits first. Only the synthetic TaskDesk data is sent.
2. Run locally:

   ```bash
   ./init.sh
   export GROQ_API_KEY=your-key            # never commit it
   .venv/bin/toolcut record --run-dir runs/model --base-url https://api.groq.com/openai/v1 \
     --model llama-3.1-8b-instant --key-env GROQ_API_KEY
   .venv/bin/toolcut report && .venv/bin/toolcut readme
   .venv/bin/python scripts/make_site.py && .venv/bin/python scripts/make_social_preview.py
   ```

   The run is resumable. If a rate limit stops it, run the same record command again. Add `--limit 20` to go in small steps.
3. Commit `runs/model/`, `docs/REPORT.md`, `docs/index.html`, `docs/social-preview.png` and the README.

## 7. Make the repo public

Done 2026-11-26: the repo is public.

## 8. Turn on Pages

Settings, Pages, deploy from the `main` branch and the `/docs` folder. `docs/index.html` is the results page. Put the Pages URL in the About box.

## 9. Social preview, About box and topics

- Upload `docs/social-preview.png` in Settings, General, Social preview.
- The description is in `docs/GITHUB_ABOUT.md`. The topics are in `docs/topics.txt`, one per line.

## 10. Rename the repo (optional)

The package and command are called `toolcut`, because `toolshape` is taken on npm (DECISIONS.md). The repo can stay `toolshape` or be renamed to `toolcut` in Settings, General. If you rename it, update the CI badge and clone links in the README.

## 11. Publish to PyPI (optional)

The name `toolcut` answered 404 on PyPI on 2026-11-20. If you want the package, set up trusted publishing on PyPI for this repo and add a release workflow. The build did not do this.

## 12. Decide whether the build prompt stays public

`docs/build/BUILD_PROMPT.md` holds the full prompt the agents followed. Keep it, trim it or remove it.

## 13. Update the human checks in the README

The README lists three human checks as "not done yet". Change each one only after you do it.
