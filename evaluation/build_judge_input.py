"""Build judge input from run logs."""

import json
from pathlib import Path
from typing import Any, Dict


def load_task_by_id(task_id: str) -> Dict[str, Any]:
    """
    Load a task JSON by task_id.
    
    Searches through tasks directory subdirectories to find a matching task_id.
    
    Args:
        task_id: The task_id to search for
        
    Returns:
        The task JSON as a dict
        
    Raises:
        ValueError: If task_id is not found
    """
    tasks_dir = Path("tasks")
    
    if not tasks_dir.exists():
        raise ValueError(f"Tasks directory not found: {tasks_dir}")
    
    # Search in subdirectories: planning, email_reply, document_generation
    subdirs = ["planning", "email_reply", "document_generation"]
    
    for subdir in subdirs:
        subdir_path = tasks_dir / subdir
        if not subdir_path.exists():
            continue
        
        # Search for JSON files in this subdirectory
        for json_file in subdir_path.glob("*.json"):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    task_data = json.load(f)
                
                if task_data.get("task_id") == task_id:
                    return task_data
            except (json.JSONDecodeError, IOError):
                # Skip invalid files, continue searching
                continue
    
    raise ValueError(f"Task ID '{task_id}' not found in any task JSON file")


def infer_task_type(task: Dict[str, Any]) -> str:
    """
    Infer task_type from task JSON or task_id.
    
    Args:
        task: Task JSON dict
        
    Returns:
        Task type string: "planning", "email_reply", or "weekly_report"
    """
    # First check if task_type is explicitly set
    if "task_type" in task:
        return task["task_type"]
    
    # Infer from task_id
    task_id = task.get("task_id", "").lower()
    
    if "planning" in task_id:
        return "planning"
    elif "email" in task_id:
        return "email_reply"
    elif "weekly" in task_id or "report" in task_id:
        return "weekly_report"
    
    # Default fallback
    return "planning"


def build_judge_input_from_log(log_path: str) -> Dict[str, Any]:
    """
    Build judge input JSON from a run log.
    
    Args:
        log_path: Path to the run log JSON file
        
    Returns:
        Dict with judge input structure:
        {
            "task_id": str,
            "task_type": str,
            "user_prompt": str,
            "answer_requirements": list[str],
            "tool_trace_steps": list[str],
            "final_answer": str,
            "rationale": str
        }
    """
    # Load run log
    log_file = Path(log_path)
    if not log_file.exists():
        raise FileNotFoundError(f"Run log not found: {log_path}")
    
    with open(log_file, 'r', encoding='utf-8') as f:
        log_data = json.load(f)
    
    # Extract required fields from log
    task_id = log_data.get("task_id")
    user_prompt = log_data.get("user_prompt")
    tool_trace_steps = log_data.get("tool_trace_steps", [])
    final_answer = log_data.get("final_answer", "")
    rationale = log_data.get("rationale", "")
    
    if not task_id:
        raise ValueError(f"Run log missing 'task_id' field")
    if not user_prompt:
        raise ValueError(f"Run log missing 'user_prompt' field")
    
    # Load task JSON
    task = load_task_by_id(task_id)
    
    # Get answer_requirements from task
    answer_requirements = task.get("answer_requirements", [])
    if not answer_requirements:
        raise ValueError(f"Task {task_id} missing 'answer_requirements' field")
    
    # Infer task_type
    task_type = infer_task_type(task)
    
    # Build judge input
    judge_input = {
        "task_id": task_id,
        "task_type": task_type,
        "user_prompt": user_prompt,
        "answer_requirements": answer_requirements,
        "tool_trace_steps": tool_trace_steps,
        "final_answer": final_answer,
        "rationale": rationale
    }
    
    return judge_input


def build_judge_input_from_log_and_save(log_path: str, output_path: str) -> None:
    """
    Programmatic wrapper: build judge input from log and save to file.
    
    Given a run log JSON, build the judge input JSON at output_path.
    
    Args:
        log_path: Path to the run log JSON file
        output_path: Path where judge input JSON should be written
    """
    # Build judge input
    judge_input = build_judge_input_from_log(log_path)
    
    # Ensure output directory exists
    output_path_obj = Path(output_path)
    output_path_obj.parent.mkdir(parents=True, exist_ok=True)
    
    # Write judge input
    with open(output_path_obj, 'w', encoding='utf-8') as f:
        json.dump(judge_input, f, indent=2, ensure_ascii=False)


def main() -> None:
    """CLI entry point for building judge input."""
    import argparse
    
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--log",
        type=str,
        default="evaluation/logs/planning_dummy_run.json",
        help="Path to the run log JSON file"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="evaluation/logs/planning_judge_input.json",
        help="Path where judge input JSON should be written"
    )
    args = parser.parse_args()
    
    # Build judge input and save
    build_judge_input_from_log_and_save(args.log, args.output)
    
    print(f"Saved judge input to {args.output}")


if __name__ == "__main__":
    main()

