import csv
import json
from importlib.util import module_from_spec, spec_from_file_location

from typer.testing import CliRunner

spec = spec_from_file_location("score_mod", "score.py")
score_mod = module_from_spec(spec)
spec.loader.exec_module(score_mod)  # type: ignore[arg-type]

runner = CliRunner()


def test_score_writes_csv(tmp_path):
    repo_dir = tmp_path / "code"
    repo_dir.mkdir()
    (repo_dir / "a.b.json").write_text(
        json.dumps({"agent_loop": {"score": 0.1, "max": 0.2, "reason": ""}}),
        encoding="utf-8",
    )
    (repo_dir / "c.d.json").write_text(
        json.dumps({"agent_loop": {"score": 0.2, "max": 0.2, "reason": ""}}),
        encoding="utf-8",
    )
    csv_path = tmp_path / "scores.csv"
    result = runner.invoke(
        score_mod.app,
        [
            "--repos",
            str(repo_dir),
            "--check",
            "llm-browser-agent/evals.toml",
            "--score",
            str(csv_path),
        ],
    )
    assert result.exit_code == 0
    rows = list(csv.DictReader(csv_path.open()))
    assert rows[0]["agent_loop"] == "0.1"
    assert rows[1]["agent_loop"] == "0.2"
