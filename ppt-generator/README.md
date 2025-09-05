# PPT Generator

On 20 Aug 2025, the [Tools in Data Science](https://tds.s-anand.net/) team [posted](https://discourse.onlinedegree.iitm.ac.in/t/bonus-marks-tds-may-2025/185301) two assignments for bonus marks.

One was to build a [browser-based LLM agent with tool use](assignment).

The evaluation was LLM-enabled. Here's the process:

## Step 1: Create an evaluation prompt

We passed [ChatGPT](https://chatgpt.com/share/68ba7f78-1d48-800c-90b0-ab624ddac87e) this prompt:

````markdown
Below are the details of a student assignment.

I will be passing the code that the student has written to an LLM to evaluate and do a code review
against the parameters mentioned in this assignment.

Write the results as a TOML file with like this:

```toml
instructions = """
(Write a detailed prompt that will allow the LLM to evaluate the code against the criteria in the assignment.)
```

# This is an example. Replace with an actual check
[checks.simplicity]
max = 0.20
check = """
Simplicity/minimal deps; small, hackable codebase
"""

# This is an example. Replace with an actual check
[checks.error_handling]
max = 0.10
check = """
Robust error handling paths (try/catch, user-visible messages).
"""

# ... Ensure all checks are covered
```

The output should be a JSON like this:

```json
{
  "<check_id>": {"score": number, "max": number, "reason": "short, evidence-based justification with file paths & symbols" },
  ...
}
```

<ASSIGNMENT>
${assignment.md}
</ASSIGNMENT>
````

The result was re-crafted into this [evals.toml](evals.toml)


## Usage

Run these commands from this directory:

```bash
uv run ../fetch.py \
  --submissions submissions.csv \
  --column "Public GitHub Repository URL" \
  --repos ./results/

uv run ../eval.py \
  --repos ./results/ \
  --check evals.toml

uv run ../score.py \
  --submissions submissions.csv \
  --column "Public GitHub Repository URL" \
  --repos ./results/ \
  --check evals.toml \
  --score scores.csv
```
