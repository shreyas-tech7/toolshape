"""Part 1 sections 9 to 12 (quality bar, study kit, release, hand-off), checked by code."""

import json
import re
import struct
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

REQUIRED = [
    "LICENSE",
    "CHANGELOG.md",
    "CONTRIBUTING.md",
    ".github/ISSUE_TEMPLATE/bug_report.md",
    ".github/ISSUE_TEMPLATE/feature_request.md",
    ".github/workflows/ci.yml",
    "docs/GITHUB_ABOUT.md",
    "docs/topics.txt",
    "docs/social-preview.png",
    "docs/index.html",
    "docs/DEMO.md",
    "docs/REPORT.md",
    "docs/ADDING_A_SHAPE.md",
    "docs/SECURITY_CHECKS.md",
    "docs/build/BUILD_PROMPT.md",
    ".env.example",
    ".pre-commit-config.yaml",
    "PROJECT_CONTEXT.md",
    "docs/PLAN.md",
]
BANNED = ["it is important to note", "testament", "not just", "pivotal", "seamless", "delve"]


def test_required_files_exist():
    assert [f for f in REQUIRED if not (ROOT / f).is_file()] == []


def test_license_is_mit_for_shreyas():
    text = (ROOT / "LICENSE").read_text()
    assert text.startswith("MIT License") and "Copyright (c) 2026 Shreyas" in text


def test_social_preview_size():
    data = (ROOT / "docs/social-preview.png").read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    assert struct.unpack(">II", data[16:24]) == (1280, 640)


def test_topics_are_valid():
    topics = (ROOT / "docs/topics.txt").read_text().split()
    assert 5 <= len(topics) <= 20
    assert all(re.fullmatch(r"[a-z0-9][a-z0-9-]{0,24}", t) for t in topics)


def test_about_description_is_short():
    m = re.search(r"^> (.+)$", (ROOT / "docs/GITHUB_ABOUT.md").read_text(), flags=re.M)
    assert m and len(m.group(1)) < 350


def test_ci_workflow_follows_the_rules():
    ci = (ROOT / ".github/workflows/ci.yml").read_text()
    for need in (
        "workflow_dispatch",
        "pull_request",
        "cancel-in-progress: true",
        "paths-ignore",
        'python-version: "3.11"',
        "./init.sh",
        "timeout-minutes: 5",
        "make_site.py --check",
        "make_social_preview.py --check",
        "check_links.py",
        "readme --check",
        "toolcut oracle --transport mcp",
        "toolcut replay",
    ):
        assert need in ci, need


@pytest.mark.parametrize("script", ["make_site.py", "make_social_preview.py"])
def test_generated_pages_match_the_results(script):
    proc = subprocess.run([sys.executable, str(ROOT / "scripts" / script), "--check"], capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stdout


def test_site_shows_the_sizes():
    sizes = json.loads((ROOT / "results/tool_sizes.json").read_text())["shapes"]
    page = (ROOT / "docs/index.html").read_text()
    assert all(f"{sizes[k]['bytes']:,}" in page for k in "ABC") and "not a language model" in page


def test_demo_is_a_real_transcript():
    demo = (ROOT / "docs/DEMO.md").read_text()
    assert "written by `scripts/make_demo.sh`" in demo and demo.count("(exit code 0)") >= 5
    assert "shape C: PASS" in demo and "all checks hold" in demo
    assert "README matches the results files" in demo


def _prose(text: str) -> str:
    text = re.sub(r"```.*?```", "", text, flags=re.S)
    text = re.sub(r"`[^`\n]*`", "", text)
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    return "\n".join(ln for ln in text.splitlines() if not ln.lstrip().startswith(("|", ">")))


def _docs() -> list[Path]:
    skip = {"BUILD_PROMPT.md", "DEMO.md"}
    files = [ROOT / "README.md", ROOT / "CONTRIBUTING.md", ROOT / "CHANGELOG.md", ROOT / "PROJECT_CONTEXT.md"]
    files += sorted(ROOT.glob("docs/**/*.md"))
    files += [ROOT / f for f in ("DECISIONS.md", "HANDOVER.md", "BLOCKERS.md", "PROGRESS.md") if (ROOT / f).exists()]
    return [f for f in files if f.name not in skip]


@pytest.mark.parametrize("path", _docs(), ids=lambda p: str(p.relative_to(ROOT)))
def test_writing_rules(path):
    """No em dashes, no dashes as punctuation, no semicolons in prose, no listed filler words."""
    prose = _prose(path.read_text(encoding="utf-8"))
    assert "—" not in prose and "–" not in prose, "em or en dash"
    assert " - " not in prose.replace("\n- ", "\n"), "dash as punctuation"
    assert ";" not in prose, "semicolon"
    low = prose.lower()
    assert [w for w in BANNED if w in low] == []


def test_link_checker_passes():
    proc = subprocess.run([sys.executable, str(ROOT / "scripts/check_links.py")], capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stdout[-2000:]


def test_readme_parts_in_order():
    text = (ROOT / "README.md").read_text()
    parts = [
        "**Status:**",
        "## The problem",
        "```mermaid",
        "## Results",
        "## Cost per task",
        "## 10-minute run guide",
        "## Limits",
        "## Glossary",
        "## Related work",
        "## How this was built",
    ]
    pos = [text.find(p) for p in parts]
    assert -1 not in pos, [p for p, i in zip(parts, pos, strict=True) if i == -1]
    assert pos == sorted(pos), parts
    assert "actions/workflows/ci.yml/badge.svg" in text.split("**Status:**")[0]
    assert "95%" in text.split("## Results")[1].split("## Cost per task")[0]
    assert "not done yet" in text.split("## How this was built")[1]


STUDY = ["docs/WALKTHROUGH.md", "docs/INTERVIEW_QA.md", "DECISIONS.md"]


def test_study_kit_exists():
    assert [f for f in STUDY if not (ROOT / f).is_file()] == []


def test_study_interview_qa_covers_the_points():
    qa = (ROOT / "docs/INTERVIEW_QA.md").read_text().lower()
    assert qa.count("\n## ") >= 12
    for point in ("isolates the design choice", "cost in tokens", "is not a security sandbox", "only one model", "fake api is a limit"):
        assert point in qa, point
    assert "src/toolcut/" in qa and "results/" in qa


def test_study_qa_cites_real_paths():
    qa = (ROOT / "docs/INTERVIEW_QA.md").read_text()
    paths = set(re.findall(r"`((?:src|results|scripts|tests|examples|docs)/[^`\s]+?)/?`", qa))
    assert paths and [p for p in paths if not (ROOT / p).exists()] == []


def test_study_walkthrough_tours_every_file():
    text = (ROOT / "docs/WALKTHROUGH.md").read_text()
    tracked = subprocess.run(["git", "-C", str(ROOT), "ls-files"], capture_output=True, text=True, timeout=30).stdout.split()
    skip = ("runs/scripted/fixtures/", ".github/ISSUE_TEMPLATE/")
    names = {Path(f).name for f in tracked if not f.startswith(skip)}
    names |= {"WALKTHROUGH.md", "INTERVIEW_QA.md", "RELEASE_CHECK.md", "HUMAN_STEPS.md", "COWORK_PROMPT.md"}
    assert sorted(n for n in names if n not in text) == []


RELEASE = ["docs/RELEASE_CHECK.md", "docs/HUMAN_STEPS.md", "docs/handoff/COWORK_PROMPT.md", "HANDOVER.md"]
HANDOFF = {"CHANGELOG.md", "docs/HUMAN_STEPS.md", "HANDOVER.md", "PROGRESS.md", "docs/RELEASE_CHECK.md"}


def test_handoff_files_exist():
    assert [f for f in RELEASE if not (ROOT / f).is_file()] == []


def _release_line(path: Path) -> str:
    m = re.search(r"^Release commit: (.+?)\.?$", path.read_text(), flags=re.M)
    assert m, f"no release commit line in {path.name}"
    return m.group(1).strip()


def test_handoff_release_sha_is_recorded():
    """The release commit says "this commit". The next commit records the full SHA, and only hand-off
    files change after it, so the tagged tree passes its own tests."""
    lines = {_release_line(ROOT / f) for f in ("CHANGELOG.md", "docs/HUMAN_STEPS.md", "HANDOVER.md")}
    assert len(lines) == 1, lines
    line = lines.pop()
    steps = (ROOT / "docs/HUMAN_STEPS.md").read_text()
    assert "v0.1.0-rc1" in steps and "public" in steps.lower() and "key" in steps.lower()
    if line.startswith("this commit"):
        return
    assert re.fullmatch(r"[0-9a-f]{40}", line), line
    assert "RELEASE_SHA" not in steps and line in steps
    if not (ROOT / ".git").exists():
        return
    git = ["git", "-C", str(ROOT)]
    if subprocess.run(git + ["cat-file", "-e", line + "^{commit}"], capture_output=True, timeout=30).returncode:
        pytest.skip("shallow clone: the release commit is not fetched")
    ok = subprocess.run(git + ["merge-base", "--is-ancestor", line, "HEAD"], capture_output=True, timeout=30)
    assert ok.returncode == 0, "the release commit is not in the history of HEAD"
    changed = subprocess.run(git + ["diff", "--name-only", line, "HEAD"], capture_output=True, text=True, timeout=30).stdout.split()
    assert set(changed) <= HANDOFF, set(changed) - HANDOFF


def test_handoff_cowork_prompt_has_guards_and_launcher():
    text = (ROOT / "docs/handoff/COWORK_PROMPT.md").read_text()
    for need in (
        "make the repo public",
        "publish a package",
        "enter any key",
        "sign in for Shreyas",
        "pay for",
        "Resume from PROGRESS.md on branch claude/build-toolshape",
    ):
        assert need in text, need


def test_release_check_lists_every_tool():
    text = (ROOT / "docs/RELEASE_CHECK.md").read_text()
    assert "PENDING" not in text
    for tool in ("gitleaks", "pip-audit", "ruff check --select S", "actionlint", "check_links", "Outside check"):
        assert tool in text, tool
