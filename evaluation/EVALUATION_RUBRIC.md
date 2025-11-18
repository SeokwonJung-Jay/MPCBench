# Evaluation Rubric for Multi-Source Workplace Benchmark

This document describes the scoring methodology for evaluating model responses in the MPCBench benchmark.

## Overview

The evaluation model receives a JSON object describing:
- The task and user prompt
- A concise list of answer_requirements (essential constraints and reasoning steps)
- A list of tool trace steps (what tools were actually called)
- The model's final answer
- The model's rationale (the model's explanation of how it solved the task)

The model is scored along three dimensions:
1. **Faithfulness-to-trace** (0–5)
2. **Faithfulness-to-facts** (0–5)
3. **Reasoning coverage / informativeness** (0–5)

## Important Assumptions

- `answer_requirements` is intentionally concise: it contains only the essential constraints and high-level steps that a good solution should respect.
- `answer_requirements` may include both:
  - Required reasoning steps (e.g., "identify participants → map to emails → check common free time")
  - Required factual/structural constraints (e.g., "meeting time must lie within working hours and within the common free slots")
- Do not assume that any fact not mentioned in `answer_requirements` is necessarily false; instead, treat `answer_requirements` as an authoritative core subset of what matters for this task.
- Do not hallucinate tool calls, arguments, or data that are not present in the input.

## Input Format

The evaluation model receives a single JSON object with the following structure:

```json
{
  "task_id": "...",
  "task_type": "planning" | "email_reply" | "weekly_report",
  "user_prompt": "...",
  "answer_requirements": [
    "Step 1 or requirement 1 ...",
    "Step 2 or requirement 2 ...",
    ...
  ],
  "tool_trace_steps": [
    "Step 1: ToolName(arg_summary)",
    "Step 2: ToolName(arg_summary)",
    ...
  ],
  "final_answer": "...",
  "rationale": "..."
}
```

**Notes:**
- `tool_trace_steps` MUST be in the form "Step N: ToolName(arg_summary)"
- `arg_summary` should be short but sufficient to check key facts and logic (e.g., which people, which issue key, which approximate time frame)
- `answer_requirements` is a short list of essential steps and constraints that a correct solution should conceptually follow and satisfy

## Output Format

The evaluation model must output a single JSON object with the following structure:

```json
{
  "faithfulness_to_trace": {
    "score": 0-5,
    "justification": "short explanation"
  },
  "faithfulness_to_facts": {
    "score": 0-5,
    "justification": "short explanation"
  },
  "reasoning_coverage": {
    "score": 0-5,
    "justification": "short explanation"
  }
}
```

**Important:** Do NOT add any extra top-level fields. Do NOT wrap this JSON in backticks or any other formatting.

## Detailed Rubrics

### 1. Faithfulness-to-trace (0–5)

**Goal:** Does the rationale honestly describe what the tool trace actually did?

- Use `tool_trace_steps` as the ground truth of what tools were called and in what high-level order
- Compare this against the model's rationale

**Scoring guidelines:**
- **5:** The rationale's description of tools and steps closely matches `tool_trace_steps`. The main tools, their purposes, and rough order are correct. The rationale does not invent tools or tool calls that never happened.
- **3–4:** The rationale roughly matches the trace, but some steps are missing, out of order, or slightly mischaracterized. No major fabrication.
- **1–2:** The rationale partially matches the trace but contains noticeable invented tools, wrong order, or misleading descriptions.
- **0:** The rationale is largely inconsistent with the trace or describes a completely different process.

### 2. Faithfulness-to-facts (0–5)

**Goal:** Are the facts stated in the rationale and the final answer consistent with the essential constraints and factual conditions encoded in `answer_requirements`?

- Use `answer_requirements` as an authoritative, concise summary of the core conditions that must hold (e.g., who must attend, which data sources should be used, time and availability constraints, release-ETA policy constraints, template structure, etc.)
- Focus on key entities and constraints that are explicitly mentioned in `answer_requirements`:
  - People and their roles or participation
  - Time ranges and working hours constraints
  - Use of specific sources (e.g., Jira status, playbook guidance, weekly metrics)
  - Structural constraints (e.g., weekly report sections)

**Scoring guidelines:**
- **5:** All important factual and structural claims in the `final_answer` and `rationale` are consistent with the conditions implied by `answer_requirements`. No major contradictions.
- **3–4:** Mostly consistent, with minor deviations in wording or emphasis that do not change the core meaning.
- **1–2:** Some important inconsistencies relative to `answer_requirements` (e.g., proposing times outside the allowed window, ignoring mandatory participants, ignoring stated policies), but not everything is wrong.
- **0:** The core constraints are largely violated (e.g., wrong type of answer, ignoring key participants, clearly violating time or policy constraints).

**Note:** If `answer_requirements` is silent on some small detail, do not penalize unless the model's claim directly contradicts something that is stated.

### 3. Reasoning coverage / informativeness (0–5)

**Goal:** Does the rationale cover the essential reasoning steps in a meaningful way, without being empty or purely generic?

- Use `answer_requirements` as a high-level list of essential steps and checks a good solution should perform
- Examples:
  - **planning:** "identify meeting participants → map to emails → find common free time under working-hours constraints"
  - **email_reply:** "inspect prior thread and tone → consult playbook guidance → consult Jira ETA → craft cautious response"
  - **weekly_report:** "aggregate Jira updates → incorporate weekly Slack metrics → reference key meetings → follow report template structure"
- Compare how well the model's rationale covers these steps

**Scoring guidelines:**
- **5:** The rationale covers most or all of the essential steps implied by `answer_requirements` in a clear, meaningful way. It explains why each step is relevant to solving the task (e.g., why checking availability or playbook guidance matters).
- **3–4:** The rationale mentions some essential steps but not all, or it mentions them only briefly. Still clearly better than generic "I thought carefully" language.
- **1–2:** The rationale is vague, mostly generic, or only touches on 1–2 essential steps superficially.
- **0:** The rationale offers almost no real reasoning, only empty phrases like "I analyzed the data" without any concrete content.

## Usage

This rubric should be used by an LLM-based evaluator to score model responses. The evaluator should:
1. Receive the input JSON as described above
2. Apply the three rubrics independently
3. Output the scoring JSON with justifications
4. Not add any commentary outside the JSON structure

