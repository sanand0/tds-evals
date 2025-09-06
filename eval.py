#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["typer>=0.12", "httpx>=0.27", "tqdm>=4.66"]
# ///

"""Evaluate repo text files using OpenAI and a TOML check config."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict

import httpx
import typer
import tomllib
from tqdm import tqdm


app = typer.Typer(add_completion=False, no_args_is_help=True)


def load_config(path: Path) -> tuple[str, Dict[str, Dict[str, Any]]]:
    with path.open("rb") as f:
        data = tomllib.load(f)
    instructions: str = data.get("instructions", "")
    checks: Dict[str, Dict[str, Any]] = data.get("checks", {})
    return instructions, checks


def build_prompt_and_schema(
    instr: str, checks: Dict[str, Dict[str, Any]]
) -> tuple[str, Dict[str, Any]]:
    system = instr.strip()
    for name, info in checks.items():
        system += f"\n\n[{name}] (max {info['max']}): {info['check'].strip()}"
    schema: Dict[str, Any] = {
        "type": "object",
        "properties": {},
        "required": [],
        "additionalProperties": False,
    }
    for name, info in checks.items():
        schema["properties"][name] = {
            "type": "object",
            "properties": {
                "score": {"type": "number"},
                "max": {"type": "number", "const": info["max"]},
                "reason": {"type": "string"},
            },
            "required": ["score", "max", "reason"],
            "additionalProperties": False,
        }
        schema["required"].append(name)
    return system, schema


async def call_openai_json(
    *,
    api_key: str,
    model: str,
    system_prompt: str,
    user_content: str,
    schema: Dict[str, Any],
    timeout_s: float = 120.0,
) -> str | None:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "checks", "schema": schema},
        },
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


async def eval_one(
    txt_path: Path,
    api_key: str,
    model: str,
    system_prompt: str,
    checks: Dict[str, Dict[str, Any]],
    schema: Dict[str, Any],
) -> Dict[str, Any] | None:
    repo_txt = txt_path.read_text(encoding="utf-8")
    log_path = txt_path.with_suffix(".log")
    errors: list[str] = []
    for _ in range(2):
        attempt = len(errors) + 1
        content = await call_openai_json(
            api_key=api_key,
            model=model,
            system_prompt=system_prompt,
            user_content=repo_txt,
            schema=schema,
        )
        if content is None:
            errors.append(f"attempt {attempt}: openai call failed")
            continue
        try:
            data = json.loads(content)
        except Exception:
            snippet = content[:500] if isinstance(content, str) else str(type(content))
            errors.append(f"attempt {attempt}: invalid json: {snippet}")
            continue
        start_errors = len(errors)
        for name, info in checks.items():
            obj = data.get(name)
            if not isinstance(obj, dict):
                errors.append(
                    f"attempt {attempt}: check {name}: invalid structure: {type(obj).__name__}"
                )
                break
            score = obj.get("score")
            max_val = obj.get("max")
            reason = obj.get("reason")
            if not isinstance(score, (int, float)) or not isinstance(max_val, (int, float)):
                errors.append(
                    f"attempt {attempt}: check {name}: invalid types: score={type(score).__name__}, max={type(max_val).__name__}"
                )
                break
            if not isinstance(reason, str):
                errors.append(
                    f"attempt {attempt}: check {name}: invalid reason type: {type(reason).__name__}"
                )
                break
            if max_val != info["max"] or score > info["max"] or score < 0:
                errors.append(
                    f"attempt {attempt}: check {name}: invalid scores: score={score}, max={max_val}, expected_max={info['max']}"
                )
                break
        if len(errors) == start_errors:
            out = txt_path.with_suffix(".json")
            out.write_text(
                json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
            )
            if log_path.exists():
                log_path.unlink()
            return data
    timestamp = datetime.now(timezone.utc).isoformat()
    error_log = f"""eval failure
file: {txt_path.name}
model: {model}
attempts: {len(errors)}
time: {timestamp}

{"\n".join(errors)}
"""
    log_path.write_text(error_log, encoding="utf-8")
    return None


async def eval_all(
    repos_dir: Path,
    checks: Dict[str, Dict[str, Any]],
    schema: Dict[str, Any],
    model: str,
    system_prompt: str,
) -> Dict[str, Dict[str, Any]]:
    api_key = os.environ["OPENAI_API_KEY"].strip()
    results: Dict[str, Dict[str, Any]] = {}
    paths = sorted(repos_dir.glob("*.txt"))
    for txt_path in tqdm(paths, desc="Evaluating repos", unit="repo"):
        if txt_path.with_suffix(".json").exists():
            continue
        data = await eval_one(txt_path, api_key, model, system_prompt, checks, schema)
        if data:
            results[txt_path.stem] = data
    return results


@app.command()
def main(
    repos: Path = typer.Option(Path("./code"), help="Directory with repo .txt files"),
    check: Path = typer.Option(Path("evals.toml"), help="TOML file with instructions and checks"),
    model: str = typer.Option("gpt-5-mini", help="OpenAI model to use"),
) -> None:
    instr, checks = load_config(check)
    system_prompt, schema = build_prompt_and_schema(instr, checks)
    asyncio.run(eval_all(repos, checks, schema, model, system_prompt))


if __name__ == "__main__":
    app()
