"""Evaluation runner for MPCBench v2.

Runs evaluation over many tasks, computes scores, and writes logs.
"""

from typing import Dict, Any, List
from pathlib import Path
import json

from config import LOGS_DIR
from task_defs import load_all_tasks, Task
from data_gen import generate_source_data
from agent_runner import run_task


def evaluate_task(
    task: Task,
    agent_model: str = "gpt-4o-mini",
    generate_data: bool = True
) -> Dict[str, Any]:
    """
    Evaluate a single task.
    
    Args:
        task: The task definition
        agent_model: Model name to use for the agent
        generate_data: Whether to generate source data if it doesn't exist
        
    Returns:
        Dictionary containing evaluation results
    """
    # Generate or load source data
    task_data_dir = LOGS_DIR / task.id / "data"
    if generate_data:
        source_data = generate_source_data(task, task_data_dir)
    else:
        # TODO: Load existing source data
        source_data = {}

    # Run agent
    run_log_path = LOGS_DIR / task.id / f"agent-{agent_model}_run.json"
    agent_result = run_task(task, source_data, agent_model, run_log_path)

    # TODO: Run judge/evaluator to score the result
    # For now, return basic structure
    result = {
        "task_id": task.id,
        "agent_model": agent_model,
        "agent_result": agent_result,
        "scores": {
            "answer_requirements_satisfaction": 0,
            "source_grounded_reasoning": 0
        }
    }

    # Save evaluation result
    eval_log_path = LOGS_DIR / task.id / f"agent-{agent_model}_eval.json"
    eval_log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(eval_log_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2)

    return result


def evaluate_all_tasks(
    agent_models: List[str] = None,
    generate_data: bool = True
) -> Dict[str, Any]:
    """
    Evaluate all tasks.
    
    Args:
        agent_models: List of agent models to test (defaults to config)
        generate_data: Whether to generate source data if it doesn't exist
        
    Returns:
        Dictionary containing evaluation results for all tasks
    """
    if agent_models is None:
        # TODO: Load from model_config.json
        agent_models = ["gpt-4o-mini"]

    tasks = load_all_tasks()
    results = {}

    for task in tasks:
        for model in agent_models:
            key = f"{task.id}__{model}"
            results[key] = evaluate_task(task, model, generate_data)

    return results

