import csv
import json
import importlib
import sys
from pathlib import Path

from typer.testing import CliRunner

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
score_mod = importlib.import_module("score")

runner = CliRunner()


def write_submissions(path):
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Git repo column", "other"])
        w.writerow(["https://github.com/a/b", "x"])
        w.writerow(["https://github.com/c/d", "y"])
        w.writerow(["invalid", "z"])


def test_score_writes_status_and_rows(tmp_path):
    repo_dir = tmp_path / "code"
    repo_dir.mkdir()
    (repo_dir / "a.b.json").write_text(
        json.dumps({"agent_loop": {"score": 0.1, "max": 0.2, "reason": ""}}),
        encoding="utf-8",
    )
    submissions = tmp_path / "submissions.csv"
    write_submissions(submissions)
    out_csv = tmp_path / "scores.csv"
    result = runner.invoke(
        score_mod.app,
        [
            "--submissions",
            str(submissions),
            "--column",
            "Git repo column",
            "--repos",
            str(repo_dir),
            "--check",
            "llm-browser-agent/evals.toml",
            "--score",
            str(out_csv),
        ],
    )
    assert result.exit_code == 0
    rows = list(csv.DictReader(out_csv.open()))
    assert len(rows) == 3
    assert rows[0]["status"] == "ok"
    assert rows[0]["repo"] == "https://github.com/a/b"
    assert rows[0]["agent_loop"] == "0.1"
    assert rows[0]["total"] == "0.1"
    assert rows[1]["status"] == "missing_json"
    assert rows[1]["repo"] == "https://github.com/c/d"
    assert rows[1]["agent_loop"] == ""
    assert rows[1]["total"] == ""
    assert rows[2]["status"] == "invalid_repo_url"
    assert rows[2]["repo"] == "invalid"


def test_score_handles_invalid_json(tmp_path):
    repo_dir = tmp_path / "code"
    repo_dir.mkdir()
    (repo_dir / "a.b.json").write_text("not json", encoding="utf-8")
    submissions = tmp_path / "submissions.csv"
    write_submissions(submissions)
    out_csv = tmp_path / "scores.csv"
    runner.invoke(
        score_mod.app,
        [
            "--submissions",
            str(submissions),
            "--column",
            "Git repo column",
            "--repos",
            str(repo_dir),
            "--check",
            "llm-browser-agent/evals.toml",
            "--score",
            str(out_csv),
        ],
    )
    rows = list(csv.DictReader(out_csv.open()))
    assert rows[0]["status"] == "invalid_json"
    assert rows[1]["status"] == "missing_json"
    assert rows[2]["status"] == "invalid_repo_url"
    assert rows[2]["repo"] == "invalid"


def test_score_missing_and_invalid_numbers(tmp_path):
    repo_dir = tmp_path / "code"
    repo_dir.mkdir()
    # JSON with one valid score, one invalid (string), one missing
    data = {
        "agent_loop": {"score": 0.2, "max": 0.2, "reason": ""},
        "sandboxing": {"score": "bad", "max": 0.1, "reason": ""},
        # a check present in evals but absent here should be blank
    }
    (repo_dir / "a.b.json").write_text(json.dumps(data), encoding="utf-8")
    submissions = tmp_path / "submissions.csv"
    write_submissions(submissions)
    out_csv = tmp_path / "scores.csv"

    runner.invoke(
        score_mod.app,
        [
            "--submissions",
            str(submissions),
            "--column",
            "Git repo column",
            "--repos",
            str(repo_dir),
            "--check",
            "llm-browser-agent/evals.toml",
            "--score",
            str(out_csv),
        ],
    )
    rows = list(csv.DictReader(out_csv.open()))
    # only valid numeric scores contribute to total
    assert rows[0]["status"] == "ok"
    assert rows[0]["total"] == "0.2"
    assert rows[0]["agent_loop"] == "0.2"
