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

app = typer.Typer(add_completion=False, no_args_is_help=True)


def load_checks(path: Path) -> List[str]:
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    checks = data.get("checks", {})
    return list(checks.keys())


@app.command()
def main(
    repos: Path = typer.Option(Path("./code"), help="Directory with repo .json files"),
    check: Path = typer.Option(Path("evals.toml"), help="TOML file with checks"),
    score: Path = typer.Option(Path("scores.csv"), help="Path to write scores CSV"),
) -> None:
    names = load_checks(check)
    fieldnames = ["repo", *names]
    with score.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for path in sorted(repos.glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            row = {"repo": path.stem}
            for name in names:
                row[name] = data.get(name, {}).get("score", "")
            w.writerow(row)


if __name__ == "__main__":
    app()
