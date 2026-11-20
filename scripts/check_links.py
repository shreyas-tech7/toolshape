"""Check every relative link and anchor in the Markdown and HTML files.

Fails on missing files, missing anchors, bare "#" links and placeholders (<owner>, TODO,
example.com). External links are listed as "not checked": this script never goes online.
Run: .venv/bin/python scripts/check_links.py
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIP = {".venv", ".git", "node_modules", "graphify-out", "logs", ".pytest_cache", ".ruff_cache", "out", "data"}
# The build prompt is a verbatim copy, so it is not held to the placeholder rule.
# Its relative links are still checked.
PLACEHOLDER_EXEMPT = {"docs/build/BUILD_PROMPT.md"}
PLACEHOLDERS = [r"<owner>", r"\bTODO\b", r"example\.com"]
MD_LINK = re.compile(r"(?<!!)\[[^\]]*\]\(([^)\s]+)\)|!\[[^\]]*\]\(([^)\s]+)\)")
HTML_LINK = re.compile(r"""(?:href|src)=["']([^"']+)["']""")


def files():
    for p in sorted(ROOT.rglob("*")):
        rel = p.relative_to(ROOT)
        if p.is_file() and p.suffix in (".md", ".html") and not SKIP & set(rel.parts):
            yield p


def slug(heading: str) -> str:
    s = heading.strip().lower()
    s = re.sub(r"[^\w\- ]", "", s)
    return s.replace(" ", "-")


def anchors(path: Path) -> set[str]:
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".md":
        return {slug(m.group(1)) for m in re.finditer(r"^#{1,6}\s+(.+)$", text, re.M)}
    return set(re.findall(r"""id=["']([^"']+)["']""", text))


def strip_code(text: str) -> str:
    text = re.sub(r"```.*?```", "", text, flags=re.S)
    return re.sub(r"`[^`\n]*`", "", text)


def main() -> int:
    errors, external = [], set()
    for path in files():
        rel = path.relative_to(ROOT).as_posix()
        raw = path.read_text(encoding="utf-8")
        text = strip_code(raw) if path.suffix == ".md" else raw
        if rel not in PLACEHOLDER_EXEMPT:
            for pat in PLACEHOLDERS:
                for m in re.finditer(pat, text):
                    errors.append(f"{rel}: placeholder {m.group(0)!r}")
        links = [a or b for a, b in MD_LINK.findall(text)] if path.suffix == ".md" else []
        links += HTML_LINK.findall(text)
        for link in links:
            if link == "#":
                errors.append(f"{rel}: bare '#' link")
            elif re.match(r"^(https?:|mailto:)", link):
                external.add(link)
            else:
                target, _, anchor = link.partition("#")
                dest = (path.parent / target).resolve() if target else path
                if not dest.exists():
                    errors.append(f"{rel}: missing file {link}")
                elif anchor and dest.suffix in (".md", ".html") and anchor not in anchors(dest):
                    errors.append(f"{rel}: missing anchor {link}")
    for link in sorted(external):
        print(f"not checked (external): {link}")
    for e in errors:
        print(f"ERROR {e}")
    print(f"{len(errors)} errors, {len(external)} external links not checked")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
