"""The report is built only from the committed results files."""

from pathlib import Path

from toolcut.report import END, START, fill, full_report, sections, stale

ROOT = Path(".")


def test_sections_build_from_results():
    s = sections(ROOT)
    assert set(s) == {"sizes", "results", "cost", "paired", "wins", "per_task", "model"}
    assert "40/40" in s["results"]
    assert s["per_task"].count("\n| t") == 40


def test_fill_and_stale():
    text = f"x\n{START.format('sizes')}\nold\n{END.format('sizes')}\ny"
    secs = {"sizes": "new"}
    assert stale(text, secs) == ["sizes"]
    out = fill(text, secs)
    assert stale(out, secs) == []
    assert out.startswith("x\n") and out.endswith("\ny")


def test_committed_report_matches_results():
    assert Path("docs/REPORT.md").read_text() == full_report(ROOT), "run `toolcut report`"


def test_report_says_the_scripted_run_is_not_a_model():
    assert "not a language model" in sections(ROOT)["cost"]
