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
