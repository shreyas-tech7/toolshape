# Adding a shape

A shape is a set of MCP tools over the same TaskDesk API. To compare a new design, you add one class and register it. The tasks, the scorer, the API and the agent loop stay the same. That is the point of the benchmark: only the tool design changes.

The worked example is shape D, which has one tool per resource with the operation as an argument. Its code is in `src/toolcut/shapes/example_grouped.py` and `tests/test_shape_guide.py` runs it.

## 1. Write the class

Subclass `Shape` and fill in two methods. `tools()` returns MCP tool definitions. `dispatch()` runs one call and returns a dict or a list. The base class turns API errors into tool errors, so a bad call comes back as text with `is_error` set and never crashes the agent.

```python
class ShapeD(Shape):
    key = "D"
    title = "D: one tool per resource"

    def __init__(self, api_url: str):
        super().__init__(api_url)
        self.client = TaskDesk(api_url)

    def tools(self) -> list[dict]:
        ...  # one tool per resource, with "operation" as an enum

    def dispatch(self, name: str, args: dict) -> object:
        return self.client.call(args["operation"], args.get("args") or {})
```

Use the typed client in `toolcut.taskdesk.client`. Never talk to the database directly, because then the shape could do things the API cannot.

## 2. Register it

Add the class to `SHAPES` in `src/toolcut/shapes/__init__.py`. The MCP server, `open_session` and the CLI read that dict, so `python -m toolcut.mcp_server --shape D` works with no other change.

## 3. Teach the oracle to drive it

The oracle runs one plan per task against a small helper layer. Add a branch to `run_plan` in `src/toolcut/oracle.py` that builds those helpers on your tools. Shape D reuses the shape A helpers through a proxy that routes each client method to its resource tool. See `GroupedProxy` in `tests/test_shape_guide.py`.

## 4. Prove it reaches every operation

Add a row per operation to `MATRIX` in `tests/test_capability_matrix.py`. The test runs each operation through every shape and checks that the database ends up the same. A shape that cannot do something the API can do is a different benchmark, so this test must pass before any numbers count.

## 5. Measure it

```bash
toolcut sizes
toolcut oracle --transport mcp
toolcut scripted
toolcut report
toolcut readme
```

`toolcut oracle` must show 40 of 40 for the oracle and 0 for the wrong agents in your shape. If the oracle fails, fix the shape or the helpers. Never change a task or the scorer to make a shape pass.

## 6. Check what it costs a model

The scripted run is a floor. It makes the oracle's calls one per turn, so it shows the tokens that the definitions and results cost and nothing else. To see whether a model can use the shape, record a real run with `toolcut record --shapes D` as `docs/HUMAN_STEPS.md` describes.
