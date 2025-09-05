# TDS Evals

Assignment evaluations for the [Tools in Data Science](https://tds.s-anand.net/) course.

- 04 Sep 2025: [LLM Browser Agent](llm-browser-agent/)

## Usage

Fetch repositories listed in a CSV column:

```bash
uv run fetch.py \
  --submissions submissions.csv \
  --column "Git repo column" \
  --parallel 5 \
  --repos ./code/
```

Evaluate the fetched repositories with the rubric:

```bash
uv run eval.py \
  --repos ./code/ \
  --check evals.toml
```

Aggregate JSON results into a CSV:

```bash
uv run score.py \
  --repos ./code/ \
  --check evals.toml \
  --score scores.csv
```
