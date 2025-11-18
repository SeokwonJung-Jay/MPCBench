"""Single task runner module."""

import argparse
import json
from pathlib import Path
from typing import Dict, Any

from evaluation.openai_agent_runner import run_task_with_openai


def sanitize_model_name(model_name: str) -> str:
    """
    Make a model name safe to use in filenames by replacing problematic characters.
    
    Example: 'gpt-4o-mini' -> 'gpt-4o-mini', 'openai/gpt-4o' -> 'openai-gpt-4o'
    """
    return (
        model_name.replace("/", "-")
                  .replace(":", "-")
                  .replace(" ", "_")
    )


def save_run_log(log: Dict[str, Any], output_path: str) -> None:
    """
    Write the run log dict as pretty-printed JSON to the given path.
    
    Args:
        log: Dictionary containing run log data
        output_path: Path where the log should be written
    """
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(log, f, indent=2, ensure_ascii=False)


def run_single_task(task_path: str, output_log_path: str = None, agent_model: str = "gpt-4o-mini") -> str:
    """
    Run a single task and save the run log.
    
    Uses OpenAI agent with tool calling to execute the task.
    
    Args:
        task_path: Path to the task JSON file
        output_log_path: Path where the run log should be saved (default: evaluation/logs/{task_id}__agent-{model}_run.json)
        agent_model: OpenAI model name for the agent (default: "gpt-4o-mini")
        
    Returns:
        Path to the saved run log file
    """
    print(f"[run_single_task] Starting task execution")
    print(f"[run_single_task] Task JSON path: {task_path}")
    
    # Load task JSON
    task_file = Path(task_path)
    if not task_file.exists():
        raise FileNotFoundError(f"Task file not found: {task_path}")
    
    with open(task_file, 'r', encoding='utf-8') as f:
        task = json.load(f)
    
    # Extract required fields
    task_id = task.get("task_id")
    user_prompt = task.get("user_prompt")
    task_type = task.get("task_type", "")
    
    print(f"[run_single_task] Task loaded: task_id={task_id}, task_type={task_type}")
    
    if not task_id:
        raise ValueError(f"Task file {task_path} missing 'task_id' field")
    if not user_prompt:
        raise ValueError(f"Task file {task_path} missing 'user_prompt' field")
    
    # Set default output path if not provided
    if output_log_path is None:
        logs_dir = Path("evaluation/logs")
        logs_dir.mkdir(parents=True, exist_ok=True)
        safe_model = sanitize_model_name(agent_model)
        output_path_obj = logs_dir / f"{task_id}__agent-{safe_model}_run.json"
    else:
        output_path_obj = Path(output_log_path)
        output_path_obj.parent.mkdir(parents=True, exist_ok=True)
    
    print(f"[run_single_task] Agent model: {agent_model}")
    print(f"[run_single_task] Run log will be saved to: {output_path_obj}")
    
    # Run with OpenAI agent (generic, works for all task types)
    # Use scenario_A as default (can be made configurable later)
    data_root = "data"
    print(f"[run_single_task] Executing agent with data_root={data_root}, model={agent_model}")
    print(f"[run_single_task] Running OpenAI agent with tool calling...")
    
    log = run_task_with_openai(
        task=task,
        data_root=data_root,
        model=agent_model,
    )
    
    num_tool_calls = len(log.get('raw_tool_calls', []))
    print(f"[run_single_task] Agent execution completed. Tool calls: {num_tool_calls}")
    
    # Save the log
    save_run_log(log, str(output_path_obj))
    
    print(f"[run_single_task] Run log saved to: {output_path_obj}")
    print(
        f"[run_single_task] Summary: task_id={task_id}, task_type={task_type}, agent_model={agent_model}, "
        f"tool_calls={num_tool_calls}, log_path={output_path_obj}"
    )
    
    return str(output_path_obj)


def main() -> None:
    """CLI entry point for running a single task."""
    parser = argparse.ArgumentParser(description="Run a single task with OpenAI agent")
    parser.add_argument(
        "--task",
        type=str,
        default="tasks/planning/planning_task.json",
        help="Path to task JSON file"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Path to output log file (default: evaluation/logs/{task_id}__agent-{model}_run.json)"
    )
    parser.add_argument(
        "--agent-model",
        type=str,
        default="gpt-4o-mini",
        help="OpenAI model name for the agent (tool-using model).",
    )
    
    args = parser.parse_args()
    task_path = args.task
    
    # Run the task
    output_log_path = run_single_task(
        task_path=task_path,
        output_log_path=args.output,
        agent_model=args.agent_model,
    )


if __name__ == "__main__":
    main()

