# Contributing

## Setup

```bash
./init.sh
```

It makes `.venv`, installs toolcut with its dev tools, runs ruff and runs every test offline. Run it before and after a change.

## Rules

- One change per commit, with a test that fails before the change and passes after it.
- Tests run offline. The conftest guard fails any connection that is not to 127.0.0.1.
- Every subprocess call needs a timeout. Every test that writes files uses a temp folder.
- Never type a number into the README. Change the results files with a real run, then run `toolcut readme`, `toolcut report`, `scripts/make_site.py` and `scripts/make_social_preview.py`.
- Never change a task, the scorer or the oracle's plans to make a shape pass. If the oracle fails, the shape is wrong.
- Keys live in environment variables only. `.env` is ignored by git. Run gitleaks before you commit.

## Adding a shape

See [docs/ADDING_A_SHAPE.md](docs/ADDING_A_SHAPE.md).

## Adding a task

Add it to `src/toolcut/tasks.py` with a check on the end state, add its plan to `src/toolcut/solutions.py`, and run `toolcut oracle`. The oracle must pass it in every shape and the wrong agents must fail it. Then regenerate the results and the README.
