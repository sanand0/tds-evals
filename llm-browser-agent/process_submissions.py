#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "typer>=0.12",
#   "tqdm>=4.66",
#   "httpx>=0.27",
# ]
# ///

"""Process submissions.csv, ingest repos, call OpenAI, and summarize.

Usage:
  ./process_submissions.py --csv submissions.csv --results results

Environment:
  OPENAI_API_KEY must be set for OpenAI calls.
"""

from __future__ import annotations

import asyncio
import csv
import json
import os
import re
import shlex
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx
import typer
from tqdm import tqdm


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
    # Guard against repo names ending with '.' after stripping .git
    repo = repo.rstrip(".")
    return (owner, repo) if owner and repo else None


def read_csv_rows(csv_path: Path) -> List[Dict[str, str]]:
    """Read CSV into list of dict rows; empty on failure."""
    with csv_path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def ensure_dir(path: Path) -> None:
    """Create directory if missing."""
    path.mkdir(parents=True, exist_ok=True)


def read_text(path: Path) -> str:
    """Read text file, return empty string if not found."""
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


async def run_cmd(cmd: List[str]) -> Tuple[int, str, str]:
    """Run a subprocess command, returning (returncode, stdout, stderr)."""
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out_b, err_b = await proc.communicate()
    return proc.returncode, out_b.decode(), err_b.decode()


async def run_gitingest(url: str, txt_path: Path, log_path: Path) -> bool:
    """Run `uvx gitingest` to extract repo contents into txt_path.

    Returns True on success (file exists or created), False on failure and logs to log_path.
    """
    if txt_path.exists():
        return True
    ensure_dir(txt_path.parent)
    # Use `uvx gitingest {url} -o {txt_path}`
    cmd = ["uvx", "gitingest", url, "-o", str(txt_path)]
    rc, out, err = await run_cmd(cmd)
    if rc != 0 or not txt_path.exists():
        append_log(
            log_path,
            f"gitingest failed (rc={rc})\nCMD: {shlex.join(cmd)}\nSTDOUT:\n{out}\nSTDERR:\n{err}\n",
        )
        return False
    return True


def append_log(log_path: Path, msg: str) -> None:
    """Append message to log file."""
    ensure_dir(log_path.parent)
    with log_path.open("a", encoding="utf-8") as f:
        f.write(msg.rstrip("\n") + "\n")


async def call_openai_json(
    *,
    api_key: str,
    system_prompt: str,
    user_content: str,
    timeout_s: float = 120.0,
) -> Optional[str]:
    """Call OpenAI Chat Completions with JSON response_format and return content string.

    Returns the message content string on success, else None.
    """
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    body = {
        "model": "gpt-5-mini",
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
    }
    url = "https://api.openai.com/v1/chat/completions"
    async with httpx.AsyncClient(timeout=timeout_s) as client:
        try:
            resp = await client.post(url, headers=headers, json=body)
        except Exception:
            return None
    if resp.status_code != 200:
        return None
    try:
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        if isinstance(content, str) and content.strip():
            return content
    except Exception:
        return None
    return None


async def process_one(
    *,
    row_idx: int,
    row: Dict[str, str],
    url: str,
    owner: str,
    repo: str,
    results_dir: Path,
    system_prompt: str,
    api_key: Optional[str],
) -> Dict[str, Any]:
    """Process a single valid repo: gitingest, OpenAI call, outputs and logs."""
    base_name = f"{owner}.{repo}"
    txt_path = results_dir / f"{base_name}.txt"
    json_path = results_dir / f"{base_name}.json"
    log_path = results_dir / f"{base_name}.log"

    status = "ok"

    # Step 1: gitingest
    ok = await run_gitingest(url, txt_path, log_path)
    if not ok:
        status = "gitingest_failed"
        return {
            "row_idx": row_idx,
            "status": status,
            "owner_repo": base_name,
            "repo_url": url,
            "txt_path": str(txt_path) if txt_path.exists() else "",
            "json_path": str(json_path) if json_path.exists() else "",
            "log_path": str(log_path),
        }

    # Step 2: OpenAI call (skip if exists)
    if json_path.exists():
        return {
            "row_idx": row_idx,
            "status": status,
            "owner_repo": base_name,
            "repo_url": url,
            "txt_path": str(txt_path),
            "json_path": str(json_path),
            "log_path": str(log_path) if log_path.exists() else "",
        }

    repo_txt = read_text(txt_path)
    if not repo_txt:
        status = "empty_repo_txt"
        append_log(log_path, f"Empty or unreadable txt: {txt_path}")
        return {
            "row_idx": row_idx,
            "status": status,
            "owner_repo": base_name,
            "repo_url": url,
            "txt_path": str(txt_path),
            "json_path": "",
            "log_path": str(log_path),
        }

    content = await call_openai_json(
        api_key=api_key, system_prompt=system_prompt, user_content=repo_txt
    )
    if content is None:
        status = "openai_failed"
        append_log(log_path, "OpenAI call failed or returned no content.")
        return {
            "row_idx": row_idx,
            "status": status,
            "owner_repo": base_name,
            "repo_url": url,
            "txt_path": str(txt_path),
            "json_path": "",
            "log_path": str(log_path),
        }

    # Try to ensure it’s valid JSON. Save minified; on parse error, save raw and log.
    try:
        parsed = json.loads(content)
        ensure_dir(json_path.parent)
        json_path.write_text(
            json.dumps(parsed, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
        )
    except Exception as e:  # save raw if not valid
        ensure_dir(json_path.parent)
        json_path.write_text(content, encoding="utf-8")
        append_log(log_path, f"Warning: response not valid JSON: {e}")

    return {
        "row_idx": row_idx,
        "status": status,
        "owner_repo": base_name,
        "repo_url": url,
        "txt_path": str(txt_path),
        "json_path": str(json_path),
        "log_path": str(log_path) if log_path.exists() else "",
    }


async def process_all(
    *,
    rows: List[Dict[str, str]],
    results_dir: Path,
    system_prompt: str,
    parallel: int = 5,
) -> List[Dict[str, Any]]:
    """Process all valid repo URLs with up to `parallel` concurrency and tqdm progress."""
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()

    # Identify valid URLs tied to row indices
    url_key = "Browser JS App GitHub Repo URL"
    valids: List[Tuple[int, Dict[str, str], str, str, str]] = []
    for i, row in enumerate(rows):
        url = (row.get(url_key) or "").strip()
        parsed = is_valid_github_repo_url(url)
        if parsed:
            owner, repo = parsed
            valids.append((i, row, url, owner, repo))

    ensure_dir(results_dir)

    sem = asyncio.Semaphore(parallel)
    results: Dict[int, Dict[str, Any]] = {}

    async def bound_task(args: Tuple[int, Dict[str, str], str, str, str]) -> Dict[str, Any]:
        i, row, url, owner, repo = args
        async with sem:
            return await process_one(
                row_idx=i,
                row=row,
                url=url,
                owner=owner,
                repo=repo,
                results_dir=results_dir,
                system_prompt=system_prompt,
                api_key=api_key or None,
            )

    # Launch tasks and update a single progress bar as each completes
    tasks = [asyncio.create_task(bound_task(v)) for v in valids]
    pbar = tqdm(total=len(tasks), desc="Processing repos", unit="repo")
    for coro in asyncio.as_completed(tasks):
        res = await coro
        results[res["row_idx"]] = res
        pbar.update(1)
    pbar.close()

    # Return results ordered by row index
    return [results[i] for i in sorted(results.keys())]


@app.command()
def run(
    csv_path: Path = typer.Option(Path("submissions.csv"), help="Submissions CSV path"),
    results_dir: Path = typer.Option(Path("results"), help="Directory for outputs"),
    system_prompt_path: Path = typer.Option(Path("system-prompt.md"), help="System prompt path"),
    parallel: int = typer.Option(5, min=1, max=32, help="Parallel workers"),
) -> None:
    """Run the ingestion + OpenAI pipeline"""
    system_prompt = read_text(system_prompt_path)
    rows = read_csv_rows(csv_path)

    # Process valid repos with concurrency and tqdm
    asyncio.run(
        process_all(
            rows=rows,
            results_dir=results_dir,
            system_prompt=system_prompt,
            parallel=parallel,
        )
    )


if __name__ == "__main__":
    app()
