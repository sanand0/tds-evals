import csv
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

from typer.testing import CliRunner

spec = spec_from_file_location("fetch", "fetch.py")
fetch = module_from_spec(spec)
spec.loader.exec_module(fetch)  # type: ignore[arg-type]

runner = CliRunner()


def write_csv(tmp_path: Path) -> Path:
    csv_path = tmp_path / "submissions.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Git repo column", "Other"])
        writer.writerow(["See https://github.com/a/b for code", "x"])
        writer.writerow(["https://github.com/a/b again", "x"])
        writer.writerow(["https://github.com/c/d.git some text", "y"])
        writer.writerow(["invalid", "z"])
    return csv_path


def test_find_first_repo():
    cases = [
        ("https://github.com/owner/repo", ("owner", "repo")),
        ("Check https://github.com/owner/repo.git ", ("owner", "repo")),
        ("text https://github.com/o/r/path", ("o", "r")),
        ("stuff https://github.com/x/y?ref=main", ("x", "y")),
        ("no url here", None),
    ]
    for text, expected in cases:
        assert fetch.find_first_repo(text) == expected


def test_fetch_skips_existing(monkeypatch, tmp_path):
    csv_path = write_csv(tmp_path)
    repos_dir = tmp_path / "code"
    repos_dir.mkdir()
    (repos_dir / "c.d.txt").write_text("existing", encoding="utf-8")

    calls: list[list[str]] = []

    async def fake_run_cmd(cmd: list[str]):
        calls.append(cmd)
        Path(cmd[-1]).write_text("fetched", encoding="utf-8")
        return 0, "", ""

    monkeypatch.setattr(fetch, "run_cmd", fake_run_cmd)

    result = runner.invoke(
        fetch.app,
        [
            "--submissions",
            str(csv_path),
            "--column",
            "Git repo column",
            "--parallel",
            "5",
            "--repos",
            str(repos_dir),
        ],
    )

    assert result.exit_code == 0
    assert (repos_dir / "a.b.txt").read_text(encoding="utf-8") == "fetched"
    assert (repos_dir / "c.d.txt").read_text(encoding="utf-8") == "existing"
    assert len(calls) == 1
    assert "Fetching repos" in result.output


def test_fetch_logs_on_failure(monkeypatch, tmp_path):
    csv_path = write_csv(tmp_path)
    repos_dir = tmp_path / "code"
    repos_dir.mkdir()

    async def fake_run_cmd(cmd: list[str]):
        return 1, "out", "err"

    monkeypatch.setattr(fetch, "run_cmd", fake_run_cmd)

    result = runner.invoke(
        fetch.app,
        [
            "--submissions",
            str(csv_path),
            "--column",
            "Git repo column",
            "--parallel",
            "5",
            "--repos",
            str(repos_dir),
        ],
    )

    txt = repos_dir / "a.b.txt"
    log = repos_dir / "a.b.log"
    assert result.exit_code == 0
    assert not txt.exists()
    content = log.read_text(encoding="utf-8")
    assert "gitingest failure" in content
    assert "rc: 1" in content
    assert "stdout:" in content and "out" in content
    assert "stderr:" in content and "err" in content


def test_run_cmd_executes_subprocess(monkeypatch):
    class FakeProc:
        def __init__(self):
            self.returncode = 0

        async def communicate(self):
            return b"OUT", b"ERR"

    async def fake_create(*args, **kwargs):
        return FakeProc()

    monkeypatch.setattr(fetch.asyncio, "create_subprocess_exec", fake_create)

    import asyncio

    rc, out, err = asyncio.run(fetch.run_cmd(["echo", "hi"]))
    assert rc == 0 and out == "OUT" and err == "ERR"


def test_run_gitingest_success_log_cleanup(monkeypatch, tmp_path):
    txt = tmp_path / "a.b.txt"
    log = tmp_path / "a.b.log"
    log.write_text("old", encoding="utf-8")

    async def fake_run_cmd(cmd):
        txt.write_text("ok", encoding="utf-8")
        return 0, "", ""

    monkeypatch.setattr(fetch, "run_cmd", fake_run_cmd)

    import asyncio

    ok = asyncio.run(fetch.run_gitingest("https://github.com/a/b", txt))
    assert ok is True
    assert txt.exists() and txt.read_text(encoding="utf-8") == "ok"
    assert not log.exists()


def test_run_gitingest_zero_length_is_failure(monkeypatch, tmp_path):
    txt = tmp_path / "a.b.txt"
    log = tmp_path / "a.b.log"

    async def fake_run_cmd(cmd):
        txt.touch()
        return 0, "o", "e"

    monkeypatch.setattr(fetch, "run_cmd", fake_run_cmd)

    import asyncio

    ok = asyncio.run(fetch.run_gitingest("https://github.com/a/b", txt))
    assert ok is False
    assert not txt.exists()
    content = log.read_text(encoding="utf-8")
    assert "empty output" in content
    assert "stdout:" in content and "o" in content
    assert "stderr:" in content and "e" in content


def test_empty_existing_file_triggers_fetch(monkeypatch, tmp_path):
    csv_path = write_csv(tmp_path)
    repos_dir = tmp_path / "code"
    repos_dir.mkdir()
    (repos_dir / "a.b.txt").touch()  # empty file should be treated as missing

    calls: list[list[str]] = []

    async def fake_run_cmd(cmd: list[str]):
        calls.append(cmd)
        Path(cmd[-1]).write_text("fetched", encoding="utf-8")
        return 0, "", ""

    monkeypatch.setattr(fetch, "run_cmd", fake_run_cmd)

    result = runner.invoke(
        fetch.app,
        [
            "--submissions",
            str(csv_path),
            "--column",
            "Git repo column",
            "--parallel",
            "5",
            "--repos",
            str(repos_dir),
        ],
    )

    assert result.exit_code == 0
    assert (repos_dir / "a.b.txt").read_text(encoding="utf-8") == "fetched"
    assert len(calls) == 2
