# Evaluation Rubric for Multi-Source Workplace Benchmark

This document describes the scoring methodology for evaluating model responses in the MPCBench benchmark.

## Overview

The evaluation model receives a JSON object describing:
- The task and user prompt
- A concise list of answer_requirements (essential constraints and reasoning steps)
- A list of tool trace steps (what tools were actually called)
- The model's final answer
- The model's rationale (the model's explanation of how it solved the task)

The model is scored along two dimensions:
1. **Answer requirements satisfaction** (0–5)
2. **Source grounded reasoning** (0–5)

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
  "raw_tool_calls": [
    {"tool_name": "...", "arguments": {...}, "result": {...}},
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
- `raw_tool_calls` is an optional field that may contain detailed tool call information (tool_name, arguments, result) when available

## Output Format

The evaluation model must output a single JSON object with the following structure:

```json
{
  "answer_requirements_satisfaction": {
    "score": 0-5,
    "justification": "short explanation"
  },
  "source_grounded_reasoning": {
    "score": 0-5,
    "justification": "short explanation"
  }
}
```

**Important:** Do NOT add any extra top-level fields. Do NOT wrap this JSON in backticks or any other formatting.

## Detailed Rubrics

### 1. Answer requirements satisfaction (0–5)

**Goal:** Does the final_answer (and rationale) satisfy the answer_requirements? Treat this as "correctness / success" in the absence of an oracle answer.

- Use `answer_requirements` as the specification of what a good answer should do.
- For each requirement sentence, check whether the final_answer (and rationale) satisfies it:
  - Does the answer produce the required type of output (e.g., concrete meeting time slots)?
  - Are constraints and conditions respected (e.g., participant set, date range, duration, working hours)?
- Use wording cues for importance:
  - Phrases like "must", "must not", "required to", "cannot" indicate a stronger / more critical requirement.
  - Phrases like "if possible", "preferably", "ideally", "it is better to" indicate softer preferences.
  - You may treat "should" as intermediate; when it concerns safety/privacy/core constraints, treat it closer to a hard requirement.

**Scoring guidelines:**
- **5:** All important requirements (strong wording) are satisfied; soft preferences are largely respected.
- **3–4:** Most important requirements satisfied, but some requirements or soft preferences are missing or only partially addressed.
- **1–2:** Multiple important requirements are violated or missing; the answer conflicts with key constraints.
- **0:** The answer is largely off-spec (wrong type/format or ignores almost all requirements).

### 2. Source grounded reasoning (0–5)

**Goal:** Evaluate how well the rationale and final_answer are grounded in the tool/source calls and their results.

- You have:
  - `tool_trace_steps`: a high-level, human-readable trace
  - `raw_tool_calls`: tool_name, arguments, and result objects (when provided)
- Check two aspects together in this single axis:

  **(a) Source result factual faithfulness**
  - The answer/rationale should not invent facts that contradict the tool results.
  - Do not:
    - Claim a free time slot that is not supported by the calendar results.
    - Attribute messages to Slack that do not appear in the Slack results.
    - Change numerical values, times, or key entities from what the tools returned.
  - Small paraphrases are fine; fabricating or distorting important details is not.

  **(b) Consistency with the tool trace (process description)**
  - The rationale's description of "what tools were used and why" should match `tool_trace_steps` / `raw_tool_calls`.
  - Do not:
    - Claim to have used tools that were never called.
    - Invent an entirely different sequence of steps than what the trace shows.
  - It is okay to omit minor details, but the main story of the process should match.

**Scoring guidelines:**
- **5:** The explanation is strongly aligned with both the tool results and the tool trace; no major fabrications or process inconsistencies.
- **3–4:** Mostly grounded and correct, but with some minor inaccuracies or omissions in how tool results or steps are described.
- **1–2:** Several mismatches between the explanation and the tool results/trace; noticeable invented details or misleading process description.
- **0:** The reasoning largely ignores the tools, contradicts their results, or invents an incompatible process.

## Usage

This rubric should be used by an LLM-based evaluator to score model responses. The evaluator should:
1. Receive the input JSON as described above
2. Apply the two rubrics independently
3. Output the scoring JSON with justifications
4. Not add any commentary outside the JSON structure

