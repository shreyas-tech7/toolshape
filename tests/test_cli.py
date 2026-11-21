"""The CLI reproduces the committed numbers that need no model."""

import json

from toolcut.cli import main


def test_sizes_reproduce_in_process(tmp_path):
    out = tmp_path / "s.json"
    assert main(["sizes", "--transport", "inprocess", "--out", str(out)]) == 0
    got = json.loads(out.read_text())["shapes"]
    want = json.loads(open("results/tool_sizes.json").read())["shapes"]
    assert got == want


def test_export_tools(tmp_path):
    assert main(["export-tools", "--out", str(tmp_path)]) == 0
    a = json.loads((tmp_path / "shape_A.json").read_text())["tools"]
    assert len(a) == 25 and {"name", "description", "inputSchema"} <= set(a[0])


def test_oracle_subset_in_process(tmp_path):
    out = tmp_path / "o.json"
    assert main(["oracle", "--transport", "inprocess", "--shapes", "C", "--out", str(out)]) == 0
    eps = json.loads(out.read_text())["episodes"]
    assert sum(e["passed"] for e in eps if e["agent"] == "oracle") == 40


def test_committed_oracle_results_hold():
    d = json.loads(open("results/oracle.json").read())
    assert d["meta"]["transport"] == "mcp"
    for e in d["episodes"]:
        assert e["passed"] == (e["agent"] == "oracle"), (e["task"], e["shape"], e["agent"])


def test_version(capsys):
    import pytest

    with pytest.raises(SystemExit):
        main(["--version"])
    assert "toolcut 0.1.0rc1" in capsys.readouterr().out


def test_replay_refuses_to_overwrite_its_source(tmp_path):
    import shutil

    src = tmp_path / "run"
    shutil.copytree("runs/scripted", src)
    assert main(["replay", "--run-dir", str(src), "--out", str(src)]) == 2
    assert main(["replay", "--run-dir", str(src), "--out", str(src / "sub")]) == 2
    assert (src / "state.json").exists() and (src / "fixtures").is_dir()


def test_scripted_fresh_refuses_a_folder_that_is_not_a_run(tmp_path):
    (tmp_path / "keep.txt").write_text("x")
    assert main(["scripted", "--fresh", "--run-dir", str(tmp_path)]) == 2
    assert (tmp_path / "keep.txt").exists()


def test_record_needs_key_env():
    import pytest

    with pytest.raises(SystemExit):
        main(["record", "--base-url", "http://127.0.0.1:1", "--model", "m"])
