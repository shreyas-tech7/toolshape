"""README number blocks come from results files, and the check catches drift."""

import json
import shutil
from pathlib import Path

from toolcut.cli import main
from toolcut.report import START, sections, stale

ROOT = Path(".")


def _copy(tmp_path):
    dest = tmp_path / "repo"
    dest.mkdir()
    shutil.copy("README.md", dest / "README.md")
    shutil.copytree("results", dest / "results")
    (dest / "runs" / "scripted").mkdir(parents=True)
    shutil.copy("runs/scripted/state.json", dest / "runs/scripted/state.json")
    return dest


def test_readme_matches_results():
    assert stale(Path("README.md").read_text(), sections(ROOT)) == []


def test_every_section_has_a_block():
    text = Path("README.md").read_text()
    for name in sections(ROOT):
        if name != "per_task":
            assert START.format(name) in text, name


def test_hand_edited_number_is_caught(tmp_path, monkeypatch):
    repo = _copy(tmp_path)
    p = repo / "README.md"
    text = p.read_text()
    i = text.index(START.format("sizes"))
    p.write_text(text[:i] + text[i:].replace("8,265", "8,000", 1))
    monkeypatch.chdir(repo)
    monkeypatch.setattr("toolcut.cli.ROOT", repo)
    assert main(["readme", "--check"]) == 1
    assert main(["readme"]) == 0
    assert main(["readme", "--check"]) == 0


def test_numbers_follow_the_results_file(tmp_path, monkeypatch):
    repo = _copy(tmp_path)
    f = repo / "results/tool_sizes.json"
    d = json.loads(f.read_text())
    d["shapes"]["C"]["bytes"] = 4321
    f.write_text(json.dumps(d))
    monkeypatch.setattr("toolcut.cli.ROOT", repo)
    assert main(["readme", "--check"]) == 1
    main(["readme"])
    assert "4,321" in (repo / "README.md").read_text()


def test_model_block_says_blocked_without_a_model_run():
    assert "No run with a real model yet" in sections(ROOT)["model"]
