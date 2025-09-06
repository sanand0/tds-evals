import json
from pathlib import Path
from importlib.util import module_from_spec, spec_from_file_location

from typer.testing import CliRunner

spec = spec_from_file_location("eval_mod", "eval.py")
eval_mod = module_from_spec(spec)
spec.loader.exec_module(eval_mod)  # type: ignore[arg-type]

runner = CliRunner()


def test_eval_writes_json(monkeypatch, tmp_path):
    repo_dir = tmp_path / "code"
    repo_dir.mkdir()
    txt_path = repo_dir / "a.b.txt"
    txt_path.write_text("repo", encoding="utf-8")
    instr, checks = eval_mod.load_config(Path("llm-browser-agent/evals.toml"))

    calls: list[dict[str, str]] = []

    invalid_scores = {name: 0.0 for name in checks}
    invalid_scores["agent_loop"] = checks["agent_loop"]["max"] * 2

    valid_scores = {name: 0.0 for name in checks}
    valid_scores["agent_loop"] = 0.1

    def build(scores: dict[str, float]) -> str:
        data = {
            name: {"score": scores[name], "max": info["max"], "reason": ""}
            for name, info in checks.items()
        }
        return json.dumps(data)

    async def fake_call(**kwargs):
        calls.append(kwargs)
        return build(invalid_scores if len(calls) == 1 else valid_scores)

    monkeypatch.setattr(eval_mod, "call_openai_json", fake_call)

    seen: dict[str, int] = {}

    def fake_tqdm(it, **kwargs):
        items = list(it)
        seen["count"] = len(items)
        return items

    monkeypatch.setattr(eval_mod, "tqdm", fake_tqdm)

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    result = runner.invoke(
        eval_mod.app,
        [
            "--repos",
            str(repo_dir),
            "--check",
            "llm-browser-agent/evals.toml",
        ],
    )

    assert result.exit_code == 0
    data = json.loads((repo_dir / "a.b.json").read_text(encoding="utf-8"))
    assert data["agent_loop"]["score"] == 0.1
    assert seen["count"] == 1
    assert len(calls) == 2
    assert "LLM Agent POC" in calls[0]["system_prompt"]
    assert not (repo_dir / "a.b.log").exists()


def test_eval_skips_existing_json(monkeypatch, tmp_path):
    repo_dir = tmp_path / "code"
    repo_dir.mkdir()
    (repo_dir / "a.b.txt").write_text("repo", encoding="utf-8")
    json_path = repo_dir / "a.b.json"
    json_path.write_text('{"existing":true}', encoding="utf-8")

    called = False

    async def fake_call(**kwargs):
        nonlocal called
        called = True
        return "{}"

    monkeypatch.setattr(eval_mod, "call_openai_json", fake_call)

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    runner.invoke(
        eval_mod.app,
        ["--repos", str(repo_dir), "--check", "llm-browser-agent/evals.toml"],
    )

    assert json.loads(json_path.read_text(encoding="utf-8")) == {"existing": True}
    assert not called


def test_eval_logs_on_openai_failure(monkeypatch, tmp_path):
    repo_dir = tmp_path / "code"
    repo_dir.mkdir()
    txt_path = repo_dir / "a.b.txt"
    txt_path.write_text("repo", encoding="utf-8")

    async def fake_call(**kwargs):
        return None

    monkeypatch.setattr(eval_mod, "call_openai_json", fake_call)

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    runner.invoke(
        eval_mod.app,
        ["--repos", str(repo_dir), "--check", "llm-browser-agent/evals.toml"],
    )

    assert not (repo_dir / "a.b.json").exists()
    log = (repo_dir / "a.b.log").read_text(encoding="utf-8")
    assert "openai" in log


def test_model_option_is_passed_to_openai(monkeypatch, tmp_path):
    repo_dir = tmp_path / "code"
    repo_dir.mkdir()
    txt_path = repo_dir / "a.b.txt"
    txt_path.write_text("repo", encoding="utf-8")

    seen_model: list[str] = []

    async def fake_call(**kwargs):
        seen_model.append(kwargs.get("model"))
        # Minimal valid JSON structure for one-pass success
        instr, checks = eval_mod.load_config(Path("llm-browser-agent/evals.toml"))
        _system_prompt, _schema = eval_mod.build_prompt_and_schema(instr, checks)
        data = {
            name: {"score": 0.0, "max": info["max"], "reason": ""} for name, info in checks.items()
        }
        return json.dumps(data)

    monkeypatch.setattr(eval_mod, "call_openai_json", fake_call)

    custom_model = "gpt-4o-mini"
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    result = runner.invoke(
        eval_mod.app,
        [
            "--repos",
            str(repo_dir),
            "--check",
            "llm-browser-agent/evals.toml",
            "--model",
            custom_model,
        ],
    )

    assert result.exit_code == 0
    assert seen_model == [custom_model]


def test_model_option_defaults_when_omitted(monkeypatch, tmp_path):
    repo_dir = tmp_path / "code"
    repo_dir.mkdir()
    (repo_dir / "a.b.txt").write_text("repo", encoding="utf-8")

    seen_model: list[str] = []

    async def fake_call(**kwargs):
        seen_model.append(kwargs.get("model"))
        instr, checks = eval_mod.load_config(Path("llm-browser-agent/evals.toml"))
        _system_prompt, _schema = eval_mod.build_prompt_and_schema(instr, checks)
        data = {
            name: {"score": 0.0, "max": info["max"], "reason": ""} for name, info in checks.items()
        }
        return json.dumps(data)

    monkeypatch.setattr(eval_mod, "call_openai_json", fake_call)

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    result = runner.invoke(
        eval_mod.app,
        ["--repos", str(repo_dir), "--check", "llm-browser-agent/evals.toml"],
    )

    assert result.exit_code == 0
    assert seen_model == ["gpt-5-mini"]


def test_call_openai_json_handles_non_200(monkeypatch):
    class FakeResp:
        status_code = 429

        def json(self):  # pragma: no cover - not called on non-200
            return {}

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, *a, **k):
            return FakeResp()

    monkeypatch.setattr(eval_mod.httpx, "AsyncClient", FakeClient)

    import asyncio

    instr, checks = eval_mod.load_config(Path("llm-browser-agent/evals.toml"))
    _system_prompt, schema = eval_mod.build_prompt_and_schema(instr, checks)
    res = asyncio.run(
        eval_mod.call_openai_json(
            api_key="k",
            model="gpt-5-mini",
            system_prompt="sys",
            user_content="u",
            schema=schema,
            timeout_s=1.0,
        )
    )
    assert res is None


def test_call_openai_json_success(monkeypatch):
    class FakeResp:
        status_code = 200

        def json(self):
            return {"choices": [{"message": {"content": "{}"}}]}

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, *a, **k):
            return FakeResp()

    monkeypatch.setattr(eval_mod.httpx, "AsyncClient", FakeClient)

    import asyncio

    instr, checks = eval_mod.load_config(Path("llm-browser-agent/evals.toml"))
    _system_prompt, schema = eval_mod.build_prompt_and_schema(instr, checks)
    res = asyncio.run(
        eval_mod.call_openai_json(
            api_key="k",
            model="gpt-5-mini",
            system_prompt="sys",
            user_content="u",
            schema=schema,
            timeout_s=1.0,
        )
    )
    assert res == "{}"


def test_eval_one_invalid_cases_then_valid(monkeypatch, tmp_path):
    repo_dir = tmp_path
    txt_path = repo_dir / "a.b.txt"
    txt_path.write_text("repo", encoding="utf-8")
    instr, checks = eval_mod.load_config(Path("llm-browser-agent/evals.toml"))
    system_prompt, schema = eval_mod.build_prompt_and_schema(instr, checks)

    # Build various invalid payloads
    def payload_with(overrides: dict[str, dict]):
        data = {
            name: {"score": 0.0, "max": info["max"], "reason": "ok"}
            for name, info in checks.items()
        }
        for k, v in overrides.items():
            data[k] = v
        return json.dumps(data)

    invalids = [
        "not json",
        payload_with({"agent_loop": 123}),  # invalid structure
        payload_with({"agent_loop": {"score": "x", "max": 0.2, "reason": "ok"}}),  # invalid types
        payload_with({"agent_loop": {"score": -0.1, "max": 0.2, "reason": "ok"}}),  # negative score
    ]

    import asyncio

    for bad in invalids:
        calls = {"i": 0}

        async def fake_call(**kwargs):
            i = calls["i"]
            calls["i"] += 1
            return bad if i == 0 else payload_with({})

        monkeypatch.setattr(eval_mod, "call_openai_json", fake_call)

        out = asyncio.run(
            eval_mod.eval_one(
                txt_path,
                api_key="k",
                model="m",
                system_prompt=system_prompt,
                checks=checks,
                schema=schema,
            )
        )
        assert out is not None
        # log should not persist after success
        assert not txt_path.with_suffix(".log").exists()


def test_eval_clears_previous_log_on_success(monkeypatch, tmp_path):
    repo_dir = tmp_path / "code"
    repo_dir.mkdir()
    txt_path = repo_dir / "a.b.txt"
    txt_path.write_text("repo", encoding="utf-8")
    # pre-existing log
    (repo_dir / "a.b.log").write_text("old error", encoding="utf-8")

    async def fake_call(**kwargs):
        instr, checks = eval_mod.load_config(Path("llm-browser-agent/evals.toml"))
        _sp, _schema = eval_mod.build_prompt_and_schema(instr, checks)
        data = {
            name: {"score": 0.0, "max": info["max"], "reason": ""} for name, info in checks.items()
        }
        return json.dumps(data)

    monkeypatch.setattr(eval_mod, "call_openai_json", fake_call)

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    runner.invoke(
        eval_mod.app,
        ["--repos", str(repo_dir), "--check", "llm-browser-agent/evals.toml"],
    )
    assert (repo_dir / "a.b.json").exists()
    assert not (repo_dir / "a.b.log").exists()
