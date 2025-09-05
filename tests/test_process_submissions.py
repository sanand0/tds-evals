from importlib.util import module_from_spec, spec_from_file_location
import asyncio
import json
from pathlib import Path


def load_module():
    spec = spec_from_file_location(
        "process_submissions", "llm-browser-agent/process_submissions.py"
    )
    module = module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[arg-type]
    return module


def test_extract_first_github_repo_url_canonicalization():
    m = load_module()
    extract = m.extract_first_github_repo_url
    s = (
        "My repos: https://github.com/user1/repo-one and "
        "https://github.com/user2/repo-two"
    )
    assert extract(s) == "https://github.com/user1/repo-one"
    assert extract("https://github.com/u/r.git") == "https://github.com/u/r"
    assert extract("nothing here") is None


def test_process_all_uses_public_column_and_writes_outputs(tmp_path, monkeypatch):
    m = load_module()

    async def fake_gitingest(url: str, txt_path: Path, log_path: Path) -> bool:
        txt_path.parent.mkdir(parents=True, exist_ok=True)
        txt_path.write_text("repo", encoding="utf-8")
        return True

    async def fake_openai_json(**kwargs):
        return json.dumps({})

    monkeypatch.setattr(m, "run_gitingest", fake_gitingest)
    monkeypatch.setattr(m, "call_openai_json", fake_openai_json)

    rows = [
        {
            "Public GitHub Repository URL": "Text + https://github.com/u1/r1 and more",
            "Browser JS App GitHub Repo URL": "https://github.com/ignored/ignored",
        },
        {"Public GitHub Repository URL": "https://notgithub.com/u2/r2"},
        {"Public GitHub Repository URL": ""},
    ]

    results_dir = tmp_path / "results"
    res = asyncio.run(
        m.process_all(rows=rows, results_dir=results_dir, system_prompt="prompt", parallel=2)
    )

    assert len(res) == 1
    r = res[0]
    assert r["status"] == "ok"
    assert r["repo_url"] == "https://github.com/u1/r1"
    assert (results_dir / "u1.r1.txt").exists()
