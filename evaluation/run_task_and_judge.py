"""Orchestrator for running a task end-to-end: agent → judge input → judge scores."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from evaluation.run_single_task import run_single_task, sanitize_model_name
from evaluation.build_judge_input import build_judge_input_from_log_and_save
from evaluation.judge_runner import run_judge


def run_task_and_judge(
    task_path: str,
    scenario_id: str,
    agent_models: List[str],
    judge_models: List[str],
) -> Dict[str, Any]:
    """
    Run a single task end-to-end for all agent × judge combinations:
    1) Model A (agent) with tools
    2) Build judge input
    3) Model B (judge) scoring
    
    Args:
        task_path: Path to task JSON file
        scenario_id: Scenario identifier (required)
        agent_models: List of OpenAI model names for the agent (tool-using model A)
        judge_models: List of OpenAI model names for the judge (model B)
        
    Returns:
        Dict with all scores keyed by "agent={model}__judge={model}"
    """
    all_scores: Dict[str, Any] = {}
    
    for agent_model in agent_models:
        # 1) Run agent
        log_path = run_single_task(
            task_path=task_path,
            scenario_id=scenario_id,
            output_log_path=None,  # Will use default with model name
            agent_model=agent_model
        )
        
        log_path_obj = Path(log_path)
        
        # Load run log to get task_id
        with open(log_path_obj, 'r', encoding='utf-8') as f:
            run_log = json.load(f)
        
        task_id = run_log.get("task_id", "unknown")
        task_type = run_log.get("task_type", "")
        
        safe_agent = sanitize_model_name(agent_model)
        
        for judge_model in judge_models:
            safe_judge = sanitize_model_name(judge_model)
            
            # 2) Build judge_input path with model names
            judge_input_path = log_path_obj.parent / (
                f"{task_id}__agent-{safe_agent}__judge-{safe_judge}_judge_input.json"
            )
            build_judge_input_from_log_and_save(str(log_path_obj), str(judge_input_path))
            
            # 3) Run judge (Model B)
            scores = run_judge(str(judge_input_path), model=judge_model, agent_model=agent_model)
            
            # 4) Save judge_result file with model names
            result_path = log_path_obj.parent / (
                f"{task_id}__agent-{safe_agent}__judge-{safe_judge}_judge_result.json"
            )
            with result_path.open("w", encoding="utf-8") as f:
                json.dump(scores, f, ensure_ascii=False, indent=2)
            
            print(
                f"\n[run_task_and_judge] task_id={task_id}, task_type={task_type}\n"
                f"  agent_model:   {agent_model}\n"
                f"  judge_model:   {judge_model}\n"
                f"  run_log:       {log_path_obj}\n"
                f"  judge_input:   {judge_input_path}\n"
                f"  judge_result:  {result_path}\n"
                f"  scores:\n{json.dumps(scores, ensure_ascii=False, indent=4)}"
            )
            
            # Store scores keyed by combination
            key = f"agent={agent_model}__judge={judge_model}"
            all_scores[key] = scores
    
    return all_scores


def main() -> None:
    """CLI entry point for running task and judge end-to-end."""
    parser = argparse.ArgumentParser(
        description="Run a task end-to-end: agent → judge input → judge scores"
    )
    parser.add_argument(
        "--task",
        type=str,
        required=True,
        help="Path to a task JSON file (any task_type).",
    )
    parser.add_argument(
        "--model-config",
        type=str,
        default="model_config.json",
        help="Path to a JSON file specifying agent_models and judge_models (default: model_config.json at repo root).",
    )
    parser.add_argument(
        "--scenario-id",
        type=str,
        required=True,
        help="Scenario identifier (e.g., scenario_A). Required.",
    )
    args = parser.parse_args()
    
    # Load model config from JSON file
    if args.model_config == "model_config.json":
        # Default: use model_config.json at repo root
        repo_root = Path(__file__).resolve().parent.parent
        config_path = repo_root / "model_config.json"
    else:
        # Custom path provided
        config_path = Path(args.model_config)
    
    if not config_path.exists():
        raise FileNotFoundError(f"Model config file not found: {config_path}")
    
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    agent_models: List[str] = config.get("agent_models", [])
    judge_models: List[str] = config.get("judge_models", [])
    
    if not agent_models:
        raise ValueError("No agent_models specified in model_config.")
    if not judge_models:
        raise ValueError("No judge_models specified in model_config.")
    
    run_task_and_judge(
        task_path=args.task,
        scenario_id=args.scenario_id,
        agent_models=agent_models,
        judge_models=judge_models,
    )


if __name__ == "__main__":
    main()

