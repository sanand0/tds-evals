#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["typer>=0.12"]
# ///
"""Aggregate evaluation JSON files into a CSV."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import List

import tomllib
import typer

from fetch import find_first_repo, read_csv_rows

app = typer.Typer(add_completion=False, no_args_is_help=True)


def load_checks(path: Path) -> List[str]:
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    checks = data.get("checks", {})
    return list(checks.keys())


@app.command()
def main(
    submissions: Path = typer.Option(..., help="Path to submissions CSV"),
    column: str = typer.Option(..., help="CSV column with repo URLs"),
    repos: Path = typer.Option(Path("./code"), help="Directory with repo files"),
    check: Path = typer.Option(Path("evals.toml"), help="TOML file with checks"),
    score: Path = typer.Option(Path("scores.csv"), help="Path to write scores CSV"),
) -> None:
    names = load_checks(check)
    fieldnames = ["status", "repo", "total", *names]
    rows = read_csv_rows(submissions)
    with score.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for src in rows:
            text = src.get(column, "")
            row: dict[str, object] = {key: "" for key in fieldnames}
            res = find_first_repo(text)
            if not res:
                row["status"] = "invalid_repo_url"
                row["repo"] = text
                w.writerow(row)
                continue
            owner, repo = res
            row["repo"] = f"https://github.com/{owner}/{repo}"
            json_path = repos / f"{owner}.{repo}.json"
            if not json_path.exists():
                row["status"] = "missing_json"
                w.writerow(row)
                continue
            try:
                data = json.loads(json_path.read_text(encoding="utf-8"))
            except Exception:
                row["status"] = "invalid_json"
                w.writerow(row)
                continue
            total = 0.0
            for name in names:
                val = data.get(name, {}).get("score")
                if isinstance(val, (int, float)):
                    row[name] = val
                    total += val
                else:
                    row[name] = ""
            row["total"] = total
            row["status"] = "ok"
            w.writerow(row)


if __name__ == "__main__":
    app()
