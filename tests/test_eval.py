import csv
import json
from importlib.util import module_from_spec, spec_from_file_location

from typer.testing import CliRunner

spec = spec_from_file_location("eval_mod", "eval.py")
eval_mod = module_from_spec(spec)
spec.loader.exec_module(eval_mod)  # type: ignore[arg-type]

runner = CliRunner()


def test_eval_writes_json_and_csv(monkeypatch, tmp_path):
    repo_dir = tmp_path / "code"
    repo_dir.mkdir()
    txt_path = repo_dir / "a.b.txt"
    txt_path.write_text("repo", encoding="utf-8")

    calls: list[dict[str, str]] = []

    async def fake_call(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            return json.dumps(
                {
                    "agent_loop": {"score": 1.0, "max": 0.2, "reason": ""},
                    "openai_tool_calls": {"score": 0.1, "max": 0.2, "reason": ""},
                }
            )
        return json.dumps(
            {
                "agent_loop": {"score": 0.1, "max": 0.2, "reason": ""},
                "openai_tool_calls": {"score": 0.1, "max": 0.2, "reason": ""},
            }
        )

    monkeypatch.setattr(eval_mod, "call_openai_json", fake_call)

    csv_path = tmp_path / "scores.csv"
    result = runner.invoke(
        eval_mod.app,
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
    data = json.loads((repo_dir / "a.b.json").read_text(encoding="utf-8"))
    assert data["agent_loop"]["score"] == 0.1
    with csv_path.open() as f:
        rows = list(csv.DictReader(f))
    assert rows[0]["agent_loop"] == "0.1"
    assert len(calls) == 2
    assert "LLM Agent POC" in calls[0]["system_prompt"]
