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
    parser.add_argument("task_id", nargs="?", help="Specific task ID to evaluate (optional)")
    parser.add_argument("--tool-context-mode", choices=["minimal", "detailed"], 
                       help="Tool context mode (minimal or detailed). If not specified, both modes are run.")
    
    args = parser.parse_args()
    
    if args.task_id:
        # Evaluate specific task
        task_path = Path(f"tasks/{args.task_id}.json")
        if not task_path.exists():
            print(f"Error: Task file not found: {task_path}")
            sys.exit(1)
        
        task = load_task(task_path)
        
        if args.tool_context_mode:
            # Single mode
            print(f"Evaluating task: {task.id} (mode: {args.tool_context_mode})")
            result = evaluate_task(task, generate_data=True, tool_context_mode=args.tool_context_mode)
            print(f"\n✓ Evaluation complete!")
            print(f"  Answer score: {result['scores']['answer_requirements_satisfaction']}")
        else:
            # Both modes
            print(f"Evaluating task: {task.id} (both modes)")
            for mode in ["minimal", "detailed"]:
                print(f"\n[{mode}] Evaluating...")
                try:
                    result = evaluate_task(task, generate_data=True, tool_context_mode=mode)
                    print(f"  ✓ Answer score: {result['scores']['answer_requirements_satisfaction']}")
                except Exception as e:
                    print(f"  ⚠️  Error: {e}")
    else:
        # Evaluate all tasks
        tasks = load_all_tasks()
        
        if args.tool_context_mode:
            # Single mode
            print(f"Evaluating {len(tasks)} task(s) (mode: {args.tool_context_mode})...")
            results = evaluate_all_tasks(generate_data=True, tool_context_modes=[args.tool_context_mode])
        else:
            # Both modes (default)
            print(f"Evaluating {len(tasks)} task(s) (both modes)...")
            results = evaluate_all_tasks(generate_data=True, tool_context_modes=["minimal", "detailed"])
        
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

