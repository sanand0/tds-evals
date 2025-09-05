#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["typer>=0.12", "tqdm>=4.66"]
# ///

"""Fetch GitHub repos listed in a CSV via gitingest."""

from __future__ import annotations

import asyncio
import csv
import re
from pathlib import Path

import typer
from tqdm import tqdm

app = typer.Typer(add_completion=False, no_args_is_help=True)

GITHUB_REPO_RE = re.compile(
    r"https?://(?:www\.)?github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)(?:[/#?]\S*)?",
    re.IGNORECASE,
)


def find_first_repo(text: str) -> tuple[str, str] | None:
    """Return (owner, repo) from first GitHub URL in text."""
    if not text:
        return None
    m = GITHUB_REPO_RE.search(text)
    if not m:
        return None
    owner, repo = m.group(1), re.sub(r"\.git$", "", m.group(2)).rstrip(".")
    return (owner, repo) if owner and repo else None


def read_csv_rows(csv_path: Path) -> list[dict[str, str]]:
    """Read CSV into list of dict rows."""
    with csv_path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


async def run_cmd(cmd: list[str]) -> tuple[int, str, str]:
    """Run subprocess command."""
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    out, err = await proc.communicate()
    return proc.returncode, out.decode(), err.decode()


async def run_gitingest(url: str, txt_path: Path) -> bool:
    """Run gitingest if txt_path missing."""
    if txt_path.exists():
        return True
    txt_path.parent.mkdir(parents=True, exist_ok=True)
    log_path = txt_path.with_suffix(".log")
    cmd = ["uvx", "gitingest", url, "-o", str(txt_path)]
    rc, out, err = await run_cmd(cmd)
    if rc == 0 and txt_path.exists():
        if log_path.exists():
            log_path.unlink()
        return True
    log_path.write_text(out + err, encoding="utf-8")
    if txt_path.exists():
        txt_path.unlink()
    return False


async def worker(sem: asyncio.Semaphore, url: str, txt_path: Path) -> None:
    async with sem:
        await run_gitingest(url, txt_path)


async def fetch_all(
    rows: list[dict[str, str]], column: str, parallel: int, repos_dir: Path
) -> None:
    sem = asyncio.Semaphore(parallel)
    tasks = []
    seen: set[str] = set()
    for row in rows:
        text = row.get(column, "")
        res = find_first_repo(text)
        if not res:
            continue
        owner, repo = res
        base = f"{owner}.{repo}"
        if base in seen:
            continue
        seen.add(base)
        txt_path = repos_dir / f"{base}.txt"
        if txt_path.exists():
            continue
        url = f"https://github.com/{owner}/{repo}"
        tasks.append(asyncio.create_task(worker(sem, url, txt_path)))
    if tasks:
        pbar = tqdm(total=len(tasks), desc="Fetching repos", unit="repo")
        for coro in asyncio.as_completed(tasks):
            await coro
            pbar.update(1)
        pbar.close()


@app.command()
def main(
    submissions: Path = typer.Option(..., help="Path to submissions CSV"),
    column: str = typer.Option(..., help="CSV column with repo URLs"),
    parallel: int = typer.Option(5, help="Number of parallel gitingests"),
    repos: Path = typer.Option(Path("./code"), help="Output directory"),
) -> None:
    rows = read_csv_rows(submissions)
    asyncio.run(fetch_all(rows, column, parallel, repos))


if __name__ == "__main__":
    app()
