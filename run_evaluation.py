#!/usr/bin/env python3
"""Simple script to run data generation and evaluation for MPCBench v2."""

import sys
import argparse
from pathlib import Path
from evaluate import evaluate_task, evaluate_all_tasks
from task_defs import load_task, load_all_tasks

def main():
    """Run evaluation."""
    parser = argparse.ArgumentParser(description="Run MPCBench evaluation")
    parser.add_argument("--tool-context-mode", choices=["minimal", "detailed"], 
                       help="Tool context mode (minimal or detailed). If not specified, both modes are run.")
    parser.add_argument("--task-id", type=str,
                       help="Evaluate only a specific task by task_id (e.g., example_planning_002)")
    
    args = parser.parse_args()
    
    # Load tasks
    all_tasks = load_all_tasks()
    
    # Filter by task_id if specified
    if args.task_id:
        tasks = [t for t in all_tasks if t.id == args.task_id]
        if not tasks:
            print(f"Error: Task '{args.task_id}' not found.")
            sys.exit(1)
    else:
        tasks = all_tasks
    
    # Evaluate tasks
    if args.tool_context_mode:
        # Single mode
        print(f"Evaluating {len(tasks)} task(s) (mode: {args.tool_context_mode})...")
        # Filter tasks in evaluate_all_tasks by modifying it temporarily
        # For now, we'll manually evaluate each task
        from config import MODEL_CONFIG_PATH
        import json
        
        try:
            with open(MODEL_CONFIG_PATH, 'r', encoding='utf-8') as f:
                model_config = json.load(f)
                agent_models = model_config.get("agent_models", ["gpt-4o-mini"])
        except Exception:
            agent_models = ["gpt-4o-mini"]
        
        results = {}
        for task in tasks:
            for model in agent_models:
                key = f"{task.id}__{model}__{args.tool_context_mode}"
                print(f"[{args.tool_context_mode}] Task ({model}): {task.id}...", end=" ", flush=True)
                try:
                    results[key] = evaluate_task(task, model, generate_data=True, tool_context_mode=args.tool_context_mode)
                    print(f"✓")
                except Exception as e:
                    print(f"⚠️  Error: {e}")
    else:
        # Both modes (default)
        print(f"Evaluating {len(tasks)} task(s) (both modes)...")
        # Filter tasks in evaluate_all_tasks by modifying it temporarily
        from config import MODEL_CONFIG_PATH
        import json
        
        try:
            with open(MODEL_CONFIG_PATH, 'r', encoding='utf-8') as f:
                model_config = json.load(f)
                agent_models = model_config.get("agent_models", ["gpt-4o-mini"])
        except Exception:
            agent_models = ["gpt-4o-mini"]
        
        results = {}
        for task in tasks:
            for model in agent_models:
                for mode in ["minimal", "detailed"]:
                    key = f"{task.id}__{model}__{mode}"
                    print(f"[{mode}] Task ({model}): {task.id}...", end=" ", flush=True)
                    try:
                        results[key] = evaluate_task(task, model, generate_data=True, tool_context_mode=mode)
                        print(f"✓")
                    except Exception as e:
                        print(f"⚠️  Error: {e}")
    
    print(f"\n✓ Evaluation complete for {len(results)} task-model-mode combinations!")
    
    # Print summary
    for key, result in results.items():
        parts = key.split("__")
        if len(parts) == 3:
            task_id, model, mode = parts
            print(f"\n[{mode}] {task_id} ({model}):")
        else:
            task_id, model = parts
            print(f"\n{task_id} ({model}):")
        print(f"  Answer score: {result['scores']['answer_requirements_satisfaction']}")

if __name__ == "__main__":
    main()

