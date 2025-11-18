"""Judge runner module for scoring model responses."""

import json
import os
from pathlib import Path
from typing import Any, Dict

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None


JUDGE_SYSTEM_PROMPT = """You are an evaluation model for a multi-source workplace benchmark. You will receive a single JSON object describing:

- The task and user prompt.
- A concise list of answer_requirements that encodes the essential constraints and reasoning steps for a good solution.
- A list of tool trace steps that shows what tools were actually called.
- The model's final answer.
- The model's rationale (its own explanation of how it solved the task).

Your job is to score the model along three dimensions:

1) Faithfulness-to-trace (0–5)
2) Faithfulness-to-facts (0–5)
3) Reasoning coverage / informativeness (0–5)

IMPORTANT ASSUMPTIONS

- answer_requirements is intentionally concise: it contains only the essential constraints and high-level steps that a good solution should respect.
- answer_requirements may include both:
  - required reasoning steps (e.g., 'identify participants → map to emails → check common free time'), and
  - required factual/structural constraints (e.g., 'meeting time must lie within working hours and within the common free slots', 'release ETA must follow policy').
- Do not assume that any fact not mentioned in answer_requirements is necessarily false; instead, treat answer_requirements as an authoritative core subset of what matters for this task.
- Do not hallucinate tool calls, arguments, or data that are not present in the input.

INPUT FORMAT

You will be given a single JSON object with the following structure:

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

Notes:

- tool_trace_steps MUST be in the form "Step N: ToolName(arg_summary)".
- arg_summary should be short but sufficient to check key facts and logic (for example, which people, which issue key, which approximate time frame).
- answer_requirements is a short list of essential steps and constraints that a correct solution should conceptually follow and satisfy.

YOUR SCORING TASK

You must output a single JSON object with the following structure:

{
  "faithfulness_to_trace": {
    "score": 0–5 integer,
    "justification": "short explanation"
  },
  "faithfulness_to_facts": {
    "score": 0–5 integer,
    "justification": "short explanation"
  },
  "reasoning_coverage": {
    "score": 0–5 integer,
    "justification": "short explanation"
  }
}

Do NOT add any extra top-level fields. Do NOT wrap this JSON in backticks or any other formatting.

DETAILED RUBRICS

1) Faithfulness-to-trace (0–5)

Goal: Does the rationale honestly describe what the tool trace actually did?

- Use tool_trace_steps as the ground truth of what tools were called and in what high-level order.
- Compare this against the model's rationale.

Scoring guidelines:

- 5: The rationale's description of tools and steps closely matches tool_trace_steps. The main tools, their purposes, and rough order are correct. The rationale does not invent tools or tool calls that never happened.
- 3–4: The rationale roughly matches the trace, but some steps are missing, out of order, or slightly mischaracterized. No major fabrication.
- 1–2: The rationale partially matches the trace but contains noticeable invented tools, wrong order, or misleading descriptions.
- 0: The rationale is largely inconsistent with the trace or describes a completely different process.

2) Faithfulness-to-facts (0–5)

Goal: Are the facts stated in the rationale and the final answer consistent with the essential constraints and factual conditions encoded in answer_requirements?

- Use answer_requirements as an authoritative, concise summary of the core conditions that must hold (for example, who must attend, which data sources should be used, time and availability constraints, release-ETA policy constraints, template structure, etc.).
- Focus on key entities and constraints that are explicitly mentioned in answer_requirements:
  - people and their roles or participation,
  - time ranges and working hours constraints,
  - use of specific sources (e.g., Jira status, playbook guidance, weekly metrics),
  - structural constraints (e.g., weekly report sections).

Scoring guidelines:

- 5: All important factual and structural claims in the final_answer and rationale are consistent with the conditions implied by answer_requirements. No major contradictions.
- 3–4: Mostly consistent, with minor deviations in wording or emphasis that do not change the core meaning.
- 1–2: Some important inconsistencies relative to answer_requirements (e.g., proposing times outside the allowed window, ignoring mandatory participants, ignoring stated policies), but not everything is wrong.
- 0: The core constraints are largely violated (e.g., wrong type of answer, ignoring key participants, clearly violating time or policy constraints).

If answer_requirements is silent on some small detail, do not penalize unless the model's claim directly contradicts something that is stated.

3) Reasoning coverage / informativeness (0–5)

Goal: Does the rationale cover the essential reasoning steps in a meaningful way, without being empty or purely generic?

- Use answer_requirements as a high-level list of essential steps and checks a good solution should perform.
- For example:
  - planning: "identify meeting participants → map to emails → find common free time under working-hours constraints",
  - email_reply: "inspect prior thread and tone → consult playbook guidance → consult Jira ETA → craft cautious response",
  - weekly_report: "aggregate Jira updates → incorporate weekly Slack metrics → reference key meetings → follow report template structure".
- Compare how well the model's rationale covers these steps.

Scoring guidelines:

- 5: The rationale covers most or all of the essential steps implied by answer_requirements in a clear, meaningful way. It explains why each step is relevant to solving the task (for example, why checking availability or playbook guidance matters).
- 3–4: The rationale mentions some essential steps but not all, or it mentions them only briefly. Still clearly better than generic "I thought carefully" language.
- 1–2: The rationale is vague, mostly generic, or only touches on 1–2 essential steps superficially.
- 0: The rationale offers almost no real reasoning, only empty phrases like "I analyzed the data" without any concrete content.

OUTPUT REQUIREMENTS

- Output must be a single valid JSON object with the exact keys and nested structure specified above.
- Do NOT include any extra commentary outside the JSON.
- Do NOT use markdown, code fences, or backticks."""


def load_judge_input(path: str) -> Dict[str, Any]:
    """
    Load judge input JSON from a file.
    
    Args:
        path: Path to the judge input JSON file
        
    Returns:
        The judge input dict
    """
    input_file = Path(path)
    if not input_file.exists():
        raise FileNotFoundError(f"Judge input file not found: {path}")
    
    with open(input_file, 'r', encoding='utf-8') as f:
        return json.load(f)


def run_judge(input_path: str, model: str = "gpt-4o-mini") -> Dict[str, Any]:
    """
    Programmatic wrapper: load judge input from file and run judge model.
    
    Reads a single judge_input JSON from input_path,
    calls the judge model, and returns the scores as a Python dict.
    
    Args:
        input_path: Path to judge input JSON file
        model: OpenAI model name (default: "gpt-4o-mini")
        
    Returns:
        Dict with scoring results:
        {
            "faithfulness_to_trace": {"score": int, "justification": str},
            "faithfulness_to_facts": {"score": int, "justification": str},
            "reasoning_coverage": {"score": int, "justification": str}
        }
    """
    # Load judge input
    judge_input = load_judge_input(input_path)
    
    # Call judge model
    return call_judge_model(model, judge_input)


def call_judge_model(model: str, judge_input: Dict[str, Any]) -> Dict[str, Any]:
    """
    Call the OpenAI judge model to score a response.
    
    Args:
        model: OpenAI model name (e.g., "gpt-4o-mini")
        judge_input: Judge input dict with task, requirements, trace, answer, rationale
        
    Returns:
        Dict with scoring results:
        {
            "faithfulness_to_trace": {"score": int, "justification": str},
            "faithfulness_to_facts": {"score": int, "justification": str},
            "reasoning_coverage": {"score": int, "justification": str}
        }
    """
    if OpenAI is None:
        raise ImportError("openai library not installed. Install it with: pip install openai")
    
    # Check for API key
    if not os.getenv("OPENAI_API_KEY"):
        raise ValueError("OPENAI_API_KEY environment variable not set")
    
    # Initialize client
    client = OpenAI()
    
    # Construct messages
    user_content = json.dumps(judge_input, ensure_ascii=False, indent=2)
    
    messages = [
        {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
        {"role": "user", "content": user_content}
    ]
    
    # Call OpenAI
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.0
    )
    
    # Extract assistant message content
    assistant_message = response.choices[0].message.content
    
    # Parse JSON from response
    try:
        # Try to extract JSON if wrapped in markdown code blocks
        content = assistant_message.strip()
        if content.startswith("```"):
            # Remove code fence markers
            lines = content.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines[-1].startswith("```"):
                lines = lines[:-1]
            content = "\n".join(lines)
        
        result = json.loads(content)
        return result
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse judge response as JSON: {e}\nResponse was: {assistant_message}")


def main() -> None:
    """CLI entry point for judge runner."""
    import argparse
    
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        type=str,
        default="evaluation/logs/planning_judge_input.json",
        help="Path to judge input JSON file"
    )
    parser.add_argument(
        "--model",
        type=str,
        default="gpt-4o-mini",
        help="OpenAI model name (e.g., gpt-4o-mini, gpt-4o)"
    )
    args = parser.parse_args()
    
    # Load judge input and call judge model
    try:
        result = run_judge(args.input, model=args.model)
    except Exception as e:
        print(f"Error calling judge model: {e}")
        return
    
    # Print result to stdout
    print(json.dumps(result, indent=2, ensure_ascii=False))
    
    # Determine output path
    input_path = Path(args.input)
    
    # Load judge input to get task_id for default output name
    with input_path.open("r", encoding="utf-8") as f:
        judge_input = json.load(f)
    task_id = judge_input.get("task_id", "unknown_task")
    
    # Use task_id for default output name (drop _judge_input from filename)
    output_path = input_path.parent / f"{task_id}_judge_result.json"
    
    # Write to file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    
    print(f"\nSaved judge result to {output_path}")


if __name__ == "__main__":
    main()

