"""Judge runner module for scoring model responses."""

import json
import os
from pathlib import Path
from typing import Any, Dict

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

from common.log_utils import log_llm_run, build_llm_log_payload




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


def run_judge(input_path: str, model: str = "gpt-4o-mini", agent_model: str = None) -> Dict[str, Any]:
    """
    Programmatic wrapper: load judge input from file and run judge model.
    
    Reads a single judge_input JSON from input_path,
    calls the judge model, and returns the scores as a Python dict.
    
    Args:
        input_path: Path to judge input JSON file
        model: OpenAI model name (default: "gpt-4o-mini")
        agent_model: Agent model name (for logging purposes, optional)
        
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
    return call_judge_model(model, judge_input, agent_model=agent_model)


def call_judge_model(model: str, judge_input: Dict[str, Any], agent_model: str = None) -> Dict[str, Any]:
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
    
    # Load prompt config
    repo_root = Path(__file__).resolve().parent.parent
    config_path = repo_root / "prompt_config.json"
    with open(config_path, 'r', encoding='utf-8') as f:
        prompt_config = json.load(f)
    
    judge_system_prompt = prompt_config["evaluation"]["judge"]["system_prompt"]
    
    # Construct messages
    user_content = json.dumps(judge_input, ensure_ascii=False, indent=2)
    
    messages = [
        {"role": "system", "content": judge_system_prompt},
        {"role": "user", "content": user_content}
    ]
    
    # Set up LLM logging directory
    repo_root = Path(__file__).resolve().parent.parent
    llm_log_dir = repo_root / "evaluation" / "logs" / "llm" / "judge"
    safe_judge_model = model.replace("/", "-").replace(":", "-").replace(" ", "_")
    task_id = judge_input.get("task_id", "unknown")
    
    # Call OpenAI
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.0
    )
    
    # Log this LLM call
    if agent_model:
        safe_agent_model = agent_model.replace("/", "-").replace(":", "-").replace(" ", "_")
        log_file_name = f"{task_id}__agent-{safe_agent_model}__judge-{safe_judge_model}__llm.json"
    else:
        log_file_name = f"{task_id}__judge-{safe_judge_model}__llm.json"
    
    log_payload = build_llm_log_payload(
        model=model,
        component="judge",
        messages=messages,
        response=response,
        task_id=task_id,
        extra_params={"temperature": 0.0},
    )
    log_llm_run(llm_log_dir, log_file_name, log_payload)
    
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

