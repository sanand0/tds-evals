# LLM Browser Agent

On 20 Aug 2025, the [Tools in Data Science](https://tds.s-anand.net/) team [posted](https://discourse.onlinedegree.iitm.ac.in/t/bonus-marks-tds-may-2025/185301) two assignments for bonus marks.

One was to build a [browser-based LLM agent with tool use](assignment.md).

The evaluation was LLM-enabled. Here's the process:

## Step 1: Create an evaluation prompt

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

## Step 2: Create an evaluation script

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

## Step 3: Run the evaluation

We downloaded [submissions.csv](https://docs.google.com/spreadsheets/d/1FtmA5Gxbav9AWdXfKrarfDoRri9pmNpjV17FZgY6nGY/edit?usp=sharing) (private) and ran the app.

This took under 2 hours.

## Step 4: Analyze the results

We optimized this prompt via [GPT-5 Prompt Optimizer](https://platform.openai.com/chat/edit?models=gpt-5&optimize=true):

> Analyze scores.csv for deep, non-obvious insights that will help instructors improve the evaluation process and education outcomes.

... and [asked ChatGPT](https://chatgpt.com/share/68b8f962-16a4-800c-84ff-fb9e3f0c779a) to do the following:

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

- Student behavior needs to be factored in.
  - **A third of submissions are duplicates per student**. **74** emails appear multiple times; **166/502 (33.1%)** rows are duplicates (same email).
- LLMs _will_err across hundreds of evaluations. Use structured output (e.g. `response_format: "json_schema"`), clamp min/max scores, etc.
  - **Rubric drift: Search scored above its stated maximum**. Two records have `google_search_tool = 0.25`, exceeding the rubric’s stated max of **0.15** for this criterion.
  - **“Overall score” and “max_total” are missing for ~99.8% of rows**. Only **1/502** rows have non-null `overall_score` and `max_total`.
- Drop rubrics that don't discriminate.
  - **Strong “agent loop” scores coexist with zero sandboxing**. **~40%** of all submissions got **full** `agent_loop = 0.20` **and** `js_exec_sandboxed = 0`.
  - **Search awarded without OpenAI-style function calling**. **8** submissions scored on `google_search_tool > 0` while `openai_tool_calls = 0`.
  - **Model picker almost universally omitted**. Only **35/434 (8.1%)** non-null rows scored **> 0** on `model_picker_bootstrap_llm_provider`; only **19/434 (4.4%)** hit full credit.
  - **A UI criterion with near-zero discrimination**. `conversation_ui_clarity` = **0.10** for **~99%** of non-null rows (std ≈ 0.0049).
- Correlations reveal patterns.
  - **“Simplicity” rises with more complete tool integration**. Simple ≠ fewer features. `simplicity` correlates **positively** with `google_search_tool` (**r ≈ 0.56**) and `openai_tool_calls` (**r ≈ 0.46**).
  - **Loop ≠ Streaming: nearly 1 in 5 have loops but weak/no streaming**. Among those with `agent_loop=0.2`, **~18.8%** have `streaming_or_updates ≤ 0.05`.
  - **AIPipe points are nearly independent of the rest**. `aipipe_tool` has ~zero correlation with `google_search_tool` (**r ≈ –0.02**) and weak correlation with `openai_tool_calls` (**r ≈ 0.03**).

## Lessons from approach

LLM-graded code reviews are more than a cost-saving hack. They're a scale and quality lever.

LLMs are about as good as teaching assistants, but they're faster and scalable. So:

- We can use them to create new assessments quickly.
- We can also run these assessments, analyze results, drop what doesn't work, and iterate fast.


- Tips & techniques that actually work
  - **Design the judge**
    - **Lock the schema, lock the math.** Enforce JSON schema with hard `max` per criterion and a computed total; reject any record that violates it. This prevents “rubric drift” (scores exceeding max) and forces recalculation on re-runs. Pair with deterministic decoding _and_ multiple samples for reliability. Determinism alone isn’t enough.
    - **Require evidence, not vibes.** For every non-zero score, demand **file:line spans or code snippets** that justify it (“show your work”). This curbs tool hallucinations (e.g., claiming streaming exists) and makes audits trivial.
  - **Operate like psychometricians**
    - **Calibrate with anchors.** Build 10–20 “gold” repos with TA-agreed scores. Before each run, score anchors, compute agreement (Cohen’s κ or Krippendorff’s α), and block deployment if reliability dips.
    - **Measure discrimination, then prune.** After a run, check variance and criterion-total correlations; rewrite or drop near-constant items (those that give ~the same score to everyone). Revise criteria that co-award points illogically (e.g., _full agent loop_ co-occurring with _zero sandboxing_).
    - **Use multi-judge aggregation.** Have two LLM judges plus a lightweight adjudicator (LLM or rule-based). Majority/mode scores or median of three stabilizes outliers—mirroring human double-marking.
  - **Engineer the pipeline**
    - **Pre-clean ruthlessly.** Deduplicate submissions (by email, repo hash), validate URLs, pin tool versions, and keep a **no-op baseline** run to catch pipeline regressions.
    - **Adversarial tests.** Seed repos with:
      - _Readme bragging, no code_ → judge must score zero without evidence.
      - _Dead code paths_ → judge must require usage, not mere presence.
      - _Function-call look-alikes_ → regex alone should fail; prefer AST or static checks that the judge can cite.
    - **Feedback with guardrails.** Let the LLM produce formative comments only from referenced lines. No ungrounded advice; no policy violations.
  - **Use LLM strengths wisely**
    - **Triage first, humans last.** Let the model separate “clearly meets/clearly fails” from “borderline.” Humans spend time only where it matters—exactly where model-human agreement is typically lowest.
    - **Prompt for comparisons, not absolutes.** Pairwise or “best-of-N” comparisons are more reliable than absolute scoring on open-ended outputs—an insight from LLM-as-judge research and human preference learning.
- What to watch out for (and how to defuse it)
  - **Reliability illusions.** Setting `temperature=0` does not guarantee stable judgments. Sample multiple chains and aggregate; track run-to-run variation and flag deltas beyond tolerance bands.
  - **Non-discriminating criteria.** If a criterion yields ~the same score for 99% of students, it isn’t teaching or measuring anything—rewrite the instruction or drop it. (This is standard test-design hygiene.)
  - **Spec compliance vs. learning goals.** Models often reward surface features (API calls present) over capability (calls used meaningfully). Force _usage proofs_ (e.g., where output is streamed to UI; where tool results are integrated).
  - **Goodhart creep.** Once students optimize against the rubric, creativity can narrow. Rotate part of the rubric each run, and include one **“novelty”** or **“insight”** criterion that demands reasoning beyond templates.
  - **Ethics & privacy.** Student repos may contain personal data. Make retention windows explicit; strip PII in logs; disclose LLM use in evaluation and allow opt-outs where policy requires.
- A pragmatic playbook
  1. **Author** a rubric with hard maxima and _evidence requirements per point_.
  2. **Implement** schema validation + adjudicated multi-judge sampling.
  3. **Calibrate** on anchors; compute κ/α each run; block if reliability falls.
  4. **Diagnose** after each batch: variance, discrimination, weird correlations; prune and re-run.
  5. **Audit** failures with evidence snippets; keep a human-in-the-loop for the gray zone.

---

## For the skeptics

The literature is clear on two points:

1. Strong LLM judges can approximate human preference judgments at practical levels, enabling scalable first-pass evaluation
2. reliability is not guaranteed—biases and variance persist, so multi-sample aggregation, explicit evidence, and psychometric checks are non-negotiable. Treat the grader like any rater in an exam system, and you’ll get dependable, fast, and _teachable_ assessments.
