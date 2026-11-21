"""Write docs/index.html, a static results page that opens from disk with no server.
Every number comes from the results files through toolcut.report. Run: .venv/bin/python scripts/make_site.py
Add --check to compare without writing."""

import html
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from toolcut.report import sections  # noqa: E402


def md_table(md: str) -> str:
    """Turn one generated markdown block (a table plus an optional note) into HTML."""
    rows, notes = [], []
    for line in md.splitlines():
        if line.startswith("|"):
            if re.fullmatch(r"\|[-:| ]+\|", line):
                continue
            rows.append([c.strip() for c in line.strip("|").split("|")])
        elif line.strip():
            notes.append(line.strip())
    out = ""
    if rows:
        head = "".join(f"<th>{html.escape(c)}</th>" for c in rows[0])
        body = "".join("<tr>" + "".join(f"<td>{html.escape(c)}</td>" for c in r) + "</tr>" for r in rows[1:])
        out += f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"
    for n in notes:
        out += f'<p class="muted">{html.escape(n.replace("`", ""))}</p>'
    return out


def render() -> str:
    s = sections(ROOT)
    status = html.escape(s["status"].replace("**Status:** ", ""))
    parts = [
        ("Tool definition sizes", "sizes"),
        ("Oracle and wrong agents over MCP", "results"),
        ("Cost per task through the agent loop", "cost"),
        ("Paired differences against shape A", "paired"),
        ("When each shape wins", "wins"),
        ("Real model run", "model"),
        ("Every task", "per_task"),
    ]
    body = "".join(f"<h2>{t}</h2>{md_table(s[k])}" for t, k in parts)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>toolcut results</title>
<style>
:root {{ --bg: #f6f7fa; --fg: #182030; --muted: #5a6478; --line: #d4d9e2; --accent: #1f7a62; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg: #141a28; --fg: #e8ecf4; --muted: #a0aabe;
  --line: #313a4e; --accent: #6ec4aa; }} }}
body {{ background: var(--bg); color: var(--fg); font: 16px/1.5 system-ui, sans-serif; margin: 0 auto;
  max-width: 1080px; padding: 24px 16px; }}
table {{ border-collapse: collapse; width: 100%; display: block; overflow-x: auto; }}
th, td {{ border-bottom: 1px solid var(--line); padding: 6px 8px; text-align: left; vertical-align: top; }}
small, .muted {{ color: var(--muted); }}
a {{ color: var(--accent); }}
</style>
</head>
<body>
<h1>toolcut</h1>
<p>toolcut holds one fake API fixed and changes only the shape of the MCP tools an agent uses to reach it:
one tool per endpoint, task-sized tools, or search plus run code. Then it measures what each shape costs.</p>
<p><strong>Status:</strong> {status}</p>
{body}
<p class="muted">Written by scripts/make_site.py from the results folder. See the <a href="../README.md">README</a>.</p>
</body>
</html>
"""


def main(argv) -> int:
    out = ROOT / "docs" / "index.html"
    page = render()
    if "--check" in argv:
        ok = out.exists() and out.read_text(encoding="utf-8") == page
        print("docs/index.html matches the results files" if ok else "docs/index.html is stale: run scripts/make_site.py")
        return 0 if ok else 1
    out.write_text(page, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
