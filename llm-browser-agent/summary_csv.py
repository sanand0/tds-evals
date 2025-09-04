#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "typer>=0.12",
# ]
# ///

"""Generate results/summary.csv from submissions and model outputs.

This provides:
- write_summary(rows, results, out_csv) callable for other modules
- A CLI to regenerate summary from files on disk

Usage:
  ./summary_csv.py --csv submissions.csv --results results --out results/summary.csv
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import typer


app = typer.Typer(add_completion=False, no_args_is_help=True)


GITHUB_REPO_RE = re.compile(
    r"^https?://(?:www\.)?github\.com/([^/]+)/([^/#?]+?)(?:\.git)?(?:[/#?].*)?$",
    re.IGNORECASE,
)


def is_valid_github_repo_url(url: str) -> Optional[Tuple[str, str]]:
    """Return (owner, repo) if URL is a valid GitHub repo URL; else None."""
    if not url:
        return None
    m = GITHUB_REPO_RE.match(url.strip())
    if not m:
        return None
    owner, repo = m.group(1), m.group(2)
    repo = repo.rstrip('.')
    return (owner, repo) if owner and repo else None


def write_summary(
    *,
    rows: List[Dict[str, str]],
    results: List[Dict[str, Any]],
    out_csv: Path,
) -> None:
    """Write results/summary.csv with one row per input row, including key columns.

    Adds dynamic columns for per-check scores extracted from each row's JSON output.
    """
    by_idx = {r["row_idx"]: r for r in results}

    email_key = "Email Address"
    demo_key = "Hosted App URL (Demo link)"
    url_key = "Browser JS App GitHub Repo URL"

    scores_by_idx: Dict[int, Dict[str, Any]] = {}
    all_score_cols: set[str] = set()
    for res in results:
        idx = res.get("row_idx")
        jp = res.get("json_path")
        if isinstance(idx, int) and isinstance(jp, str) and jp:
            p = Path(jp)
            if p.exists():
                sc = json.loads(p.read_text(encoding="utf-8"))
                scores_by_idx[idx] = sc
                all_score_cols.update(sc.keys())

    base_fieldnames = [
        email_key,
        demo_key,
        url_key,
        "status",
        "owner_repo",
        "json_path",
        "log_path",
    ]
    score_fieldnames = sorted(all_score_cols)
    fieldnames = base_fieldnames + score_fieldnames

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for i, row in enumerate(rows):
            res = by_idx.get(i, None)
            url_val = row.get(url_key, "")
            default_status = (
                "missing_url"
                if not (url_val or "").strip()
                else ("pending" if is_valid_github_repo_url(url_val) else "invalid_url")
            )
            out = {
                email_key: row.get(email_key, ""),
                demo_key: row.get(demo_key, ""),
                url_key: row.get(url_key, ""),
                "status": res.get("status") if res else default_status,
                "owner_repo": res.get("owner_repo", "") if res else "",
                "json_path": res.get("json_path", "") if res else "",
                "log_path": res.get("log_path", "") if res else "",
            }
            for col in score_fieldnames:
                out[col] = ""
            scmap = scores_by_idx.get(i, {})
            for k, v in scmap.items():
                out[k] = v["score"] if isinstance(v, dict) and "score" in v else v
            w.writerow(out)


def _read_csv_rows(csv_path: Path) -> List[Dict[str, str]]:
    with csv_path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _scan_results_for_rows(rows: List[Dict[str, str]], results_dir: Path) -> List[Dict[str, Any]]:
    """Best-effort reconstruction of `results` list from files on disk."""
    url_key = "Browser JS App GitHub Repo URL"
    results: List[Dict[str, Any]] = []
    for i, row in enumerate(rows):
        url = (row.get(url_key) or "").strip()
        parsed = is_valid_github_repo_url(url)
        if not parsed:
            continue
        owner, repo = parsed
        base = f"{owner}.{repo}"
        txt_path = results_dir / f"{base}.txt"
        json_path = results_dir / f"{base}.json"
        log_path = results_dir / f"{base}.log"
        status = "ok" if json_path.exists() or txt_path.exists() else "pending"
        results.append(
            {
                "row_idx": i,
                "status": status,
                "owner_repo": base,
                "repo_url": url,
                "txt_path": str(txt_path) if txt_path.exists() else "",
                "json_path": str(json_path) if json_path.exists() else "",
                "log_path": str(log_path) if log_path.exists() else "",
            }
        )
    return results


@app.command()
def run(
    csv_path: Path = typer.Option(Path("submissions.csv"), help="Path to submissions.csv"),
    results_dir: Path = typer.Option(Path("results"), help="Directory for repo outputs"),
    out_csv: Path = typer.Option(Path("scores.csv"), help="Path to write scores CSV"),
) -> None:
    rows = _read_csv_rows(csv_path)
    results = _scan_results_for_rows(rows, results_dir)
    write_summary(rows=rows, results=results, out_csv=out_csv)
    typer.echo(f"Wrote summary: {out_csv}")


if __name__ == "__main__":
    app()
