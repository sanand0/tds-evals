# LLM Browser Agent

On 20 Aug 2025, the [Tools in Data Science](https://tds.s-anand.net/) team [posted](https://discourse.onlinedegree.iitm.ac.in/t/bonus-marks-tds-may-2025/185301) two assignments for bonus marks.

One was to build a [browser-based LLM agent with tool use](assignment.md).

The evaluation was LLM-enabled. Here's the process:

**Step 1: Create an evaluation prompt**

We passed [ChatGPT](https://chatgpt.com/share/68b8eef6-60ec-800c-8b10-cfff1a571590) this prompt:

```
Below are the details of a student assignment.

I will be passing the code that the student has written to an LLM to evaluate and do a code review
against the parameters mentioned in this assignment specification.
Write a detailed prompt that will allow the LLM to evaluate the code against the criteria in the assignment.

Ensure that the prompt generates structured JSON which has a score and reason against multiple criteria.

<ASSIGNMENT>
${assignment.md}
</ASSIGNMENT>
```

The result was re-crafted into this [system-prompt.md](system-prompt.md)

**Step 2: Create an evaluation script**

We passed [Codex](https://openai.com/codex/) on VS Code this prompt:

```
Write an app that will

- Go through submissions.csv
- Pick the URLs in the column labeled "Browser JS App GitHub Repo URL"
- Drop invalid GitHub URLs
- For the valid URLs, do this in batches of 5 running in parallel, showing progress via tqdm:
  - Run `uvx gitingest {url} -o owner.repo.txt` to extract the contents into results/owner:repo.txt (unless it exists)
  - Send a request to OpenAI's API with these parameters and save output to results/owner:repo.json (unless it exists).
    Check docs as required
    - model: gpt-5-mini
    - system prompt: from system-prompt.md
    - user message: contents of owner.repo.txt
    - response_format: { type: json_object }
  - Save failure logs in results/owner.repo.log
- Summarize results into results/summary.csv, 1 row per input row in submissions.csv.
  Include the `Email Address` and `Hosted App URL (Demo link)` columns from submissions.csv

SKIP TESTS!
```

It generated [process_submissions.py](process_submissions.py) which we made minor enhancements to.

We then added a [summary_csv.py](summary_csv.py) that summarizes the results.

**Step 3: Run the evaluation**

We downloaded [submissions.csv](https://docs.google.com/spreadsheets/d/1FtmA5Gxbav9AWdXfKrarfDoRri9pmNpjV17FZgY6nGY/edit?usp=sharing) (private) and ran the app.

This took under 2 hours.

**Step 4: Analyze the results**

We optimized this prompt via [GPT-5 Prompt Optimizer](https://platform.openai.com/chat/edit?models=gpt-5&optimize=true):

> Analyze scores.csv for deep, non-obvious insights that will help instructors improve the evaluation process and education outcomes.

... and [asked ChatGPT]() to do the following:

```
Analyze scores.csv to discover significant, non-obvious insights that can guide instructors in refining evaluation methods and improving student outcomes.

**Context:**
- `scores.csv` contains results of LLM-based evaluations for a student assignment.
- Refer to `assignment.md` for details about the assignment, and `system-prompt.md` for the evaluation criteria used.

**Tasks:**

Begin with a concise checklist (3-7 bullets) of what you will do; keep items conceptual, not implementation-level.

1. Examine `scores.csv` and uncover 10 distinct, highly surprising or counter-intuitive findings.
   - Each finding must clearly state the insight and provide a detailed explanation of why it is surprising.
   - Continue analysis until 10 meaningful and original findings are identified. If an analysis is not particularly counter-intuitive, do not count it.
   - If fewer than 10 authentic surprises are derived from data, creatively hypothesize additional plausible surprises to reach a total of 10, and explicitly flag which findings are generated versus data-derived.
2. Create actionable LLM prompt instructions that inspire creative, non-obvious hypothesis generation from tabular data, pushing beyond surface-level observations.

After generating code or performing analysis, validate that each finding and instruction aligns with requirements. If a requirement is not met, revise or supplement outputs as appropriate.

Share the results as follows:

- List findings clearly stating the insight, explain thoroughly why this is unexpected or impactful.
- Rank findings from most to least surprising, based on potential educational impact and novelty on a scale of 1-10.
```

[ChatGPT did a good analysis](https://chatgpt.com/share/68b8f962-16a4-800c-84ff-fb9e3f0c779a) including catching errors in the LLM output format (e.g. sporadic extra columns). Here are the top insights:

1. **Rubric drift: Search scored above its stated maximum**. Two records have `google_search_tool = 0.25`, exceeding the rubric’s stated max of **0.15** for this criterion.
2. **“Overall score” and “max_total” are missing for ~99.8% of rows**. Only **1/502** rows have non-null `overall_score` and `max_total`.
3. **A third of submissions are duplicates per student**. **74** emails appear multiple times; **166/502 (33.1%)** rows are duplicates (same email).
4. **Strong “agent loop” scores coexist with zero sandboxing**. **~40%** of all submissions got **full** `agent_loop = 0.20` **and** `js_exec_sandboxed = 0`.
5. **Search awarded without OpenAI-style function calling**. **8** submissions scored on `google_search_tool > 0` while `openai_tool_calls = 0`.
6. **Model picker almost universally omitted**. Only **35/434 (8.1%)** non-null rows scored **> 0** on `model_picker_bootstrap_llm_provider`; only **19/434 (4.4%)** hit full credit.
7. **A UI criterion with near-zero discrimination**. `conversation_ui_clarity` = **0.10** for **~99%** of non-null rows (std ≈ 0.0049).
8. **“Simplicity” rises with more complete tool integration**. `simplicity` correlates **positively** with `google_search_tool` (**r ≈ 0.56**) and `openai_tool_calls` (**r ≈ 0.46**).
9. **AIPipe points are nearly independent of the rest**. `aipipe_tool` has ~zero correlation with `google_search_tool` (**r ≈ –0.02**) and weak correlation with `openai_tool_calls` (**r ≈ 0.03**).
10. **Loop ≠ Streaming: nearly 1 in 5 have loops but weak/no streaming**. Among those with `agent_loop=0.2`, **~18.8%** have `streaming_or_updates ≤ 0.05`.

After re-running for a few students, based on these logs, we have a cleaner result set.
