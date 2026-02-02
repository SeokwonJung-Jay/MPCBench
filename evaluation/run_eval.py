#!/usr/bin/env python3
"""
MPCBench Evaluation Runner.

Runs the benchmark evaluation pipeline for a given level.
"""

import argparse
import copy
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from evaluation.sanitizer import sanitize_world, sanitize_instance
from evaluation.metrics import calculate_f1, candidates_from_oracle_output
from evaluation.agents import get_openai_agent


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Run MPCBench evaluation for a specific level."
    )
    parser.add_argument(
        "--level",
        type=int,
        required=True,
        choices=[1, 2, 3],
        help="Task difficulty level (1, 2, or 3)."
    )
    parser.add_argument(
        "--input_dir",
        type=str,
        default="generate/output",
        help="Data root directory (default: generate/output)."
    )
    parser.add_argument(
        "--output_dir",
        type=str,
        default="results",
        help="Results output directory (default: results)."
    )
    parser.add_argument(
        "--model",
        type=str,
        default="gpt-4o",
        help="Model name to use (default: gpt-4o)."
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit to first N instances (for testing)."
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.0,
        help="Model temperature (default: 0.0)."
    )
    parser.add_argument(
        "--suffix",
        type=str,
        default="test",
        help="Data file suffix (default: test). E.g., 'exp1' for world_level1_exp1.json"
    )
    return parser.parse_args()


def load_world(input_dir: str, level: int, suffix: str = "test") -> Dict[str, Any]:
    """
    Load world data for the given level.
    
    Args:
        input_dir: Data root directory.
        level: Task level (1, 2, or 3).
        suffix: File suffix (default: "test").
        
    Returns:
        World dict.
        
    Raises:
        FileNotFoundError: If world file does not exist.
    """
    # Flat file structure: input_dir/world_level{level}_{suffix}.json
    world_path = Path(input_dir) / f"world_level{level}_{suffix}.json"
    
    if not world_path.exists():
        raise FileNotFoundError(f"World file not found: {world_path}")
    
    with open(world_path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_instances(input_dir: str, level: int, suffix: str = "test") -> List[Dict[str, Any]]:
    """
    Load instance data for the given level.
    
    Args:
        input_dir: Data root directory.
        level: Task level (1, 2, or 3).
        suffix: File suffix (default: "test").
        
    Returns:
        List of instance dicts with oracle_output merged.
        
    Raises:
        FileNotFoundError: If instances file does not exist.
    """
    # Flat file structure: input_dir/instances_level{level}_{suffix}.jsonl
    instances_path = Path(input_dir) / f"instances_level{level}_{suffix}.jsonl"
    
    if not instances_path.exists():
        raise FileNotFoundError(f"Instances file not found: {instances_path}")
    
    instances = []
    with open(instances_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                instances.append(json.loads(line))
    
    # Try to load oracle output and merge
    # Flat file structure: input_dir/oracle_level{level}_{suffix}.jsonl
    oracle_path = Path(input_dir) / f"oracle_level{level}_{suffix}.jsonl"
    if oracle_path.exists():
        oracle_by_id = {}
        with open(oracle_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    oracle_data = json.loads(line)
                    instance_id = oracle_data.get("instance_id")
                    if instance_id:
                        oracle_by_id[instance_id] = oracle_data
        
        # Merge oracle_output into instances
        for instance in instances:
            instance_id = instance.get("instance_id")
            if instance_id in oracle_by_id:
                instance["oracle_output"] = oracle_by_id[instance_id]
    
    return instances


def build_context_data(world: Dict[str, Any], instance: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build context data for agent from sanitized world and instance.
    
    Args:
        world: Sanitized world dict.
        instance: Sanitized instance dict.
        
    Returns:
        Combined context data dict.
    """
    return {
        "world": world,
        "instance": instance,
    }


def run_evaluation(args: argparse.Namespace) -> None:
    """
    Run the evaluation pipeline.
    
    Args:
        args: Parsed command line arguments.
    """
    print(f"=" * 60)
    print(f"MPCBench Evaluation - Level {args.level}")
    print(f"=" * 60)
    print(f"Model: {args.model}")
    print(f"Input Directory: {args.input_dir}")
    print(f"Output Directory: {args.output_dir}")
    print(f"Data Suffix: {args.suffix}")
    if args.limit:
        print(f"Limit: {args.limit} instances")
    print()
    
    # Load data
    print("Loading data...")
    try:
        world = load_world(args.input_dir, args.level, args.suffix)
        instances = load_instances(args.input_dir, args.level, args.suffix)
    except FileNotFoundError as e:
        print(f"ERROR: {e}")
        sys.exit(1)
    
    print(f"  World loaded: {world.get('world_id', 'unknown')}")
    print(f"  Instances loaded: {len(instances)}")
    
    # Apply limit if specified
    if args.limit and args.limit < len(instances):
        instances = instances[:args.limit]
        print(f"  Limited to: {len(instances)} instances")
    
    # Sanitize world (remove oracle-only tags)
    sanitized_world = sanitize_world(world)
    
    # Initialize agent
    print("\nInitializing agent...")
    try:
        OpenAIAgent = get_openai_agent()
        agent = OpenAIAgent(
            model_name=args.model,
            temperature=args.temperature,
        )
        print(f"  Agent initialized: {args.model}")
    except ImportError as e:
        print(f"ERROR: Failed to import OpenAIAgent. Install dependencies: pip install openai python-dotenv")
        print(f"  Details: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: Failed to initialize agent: {e}")
        sys.exit(1)
    
    # Prepare output directory and file
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    model_safe = args.model.replace("/", "_").replace(":", "_")
    output_file = output_dir / f"eval_L{args.level}_{args.suffix}_{model_safe}_{timestamp}.jsonl"
    
    print(f"\nOutput file: {output_file}")
    print()
    
    # Run evaluation loop
    print("Running evaluation...")
    print("-" * 60)
    
    results: List[Dict[str, Any]] = []
    total_count = 0
    failed_count = 0
    f1_scores: List[float] = []
    
    with open(output_file, "w", encoding="utf-8") as f_out:
        for i, instance in enumerate(instances):
            instance_id = instance.get("instance_id", f"instance_{i}")
            total_count += 1
            
            result: Dict[str, Any] = {
                "instance_id": instance_id,
                "metrics": None,
                "pred": None,
                "gold": None,
                "error": None,
            }
            
            try:
                # Create a deep copy of instance for agent input (prevent data leakage)
                agent_input = copy.deepcopy(instance)
                
                # Remove oracle_output from agent input (critical: prevent data leakage)
                agent_input.pop("oracle_output", None)
                
                # Sanitize instance (remove oracle-only tags)
                sanitized_instance = sanitize_instance(agent_input)
                
                # Build context for agent (oracle_output is NOT included)
                context_data = build_context_data(sanitized_world, sanitized_instance)
                
                # Get task text from original instance
                task_text = instance.get("task_text", "")
                
                # Run agent
                pred_tuples = agent.solve(task_text, context_data)
                
                # Save agent trace if available (silent tool use tracking)
                if hasattr(agent, 'last_trace'):
                    result["trace"] = agent.last_trace
                else:
                    result["trace"] = None
                
                # Get gold candidates from oracle_output (from original instance, not agent_input)
                oracle_output = instance.get("oracle_output", {})
                gold_candidates = oracle_output.get("feasible_candidates", [])
                gold_tuples = candidates_from_oracle_output(gold_candidates, args.level)
                
                # Calculate metrics
                metrics = calculate_f1(gold_tuples, pred_tuples)
                
                # Store results
                result["metrics"] = metrics
                result["pred"] = [list(t) for t in pred_tuples]  # Convert tuples to lists for JSON
                result["gold"] = [list(t) for t in gold_tuples]
                
                f1_scores.append(metrics["f1"])
                
                # Print progress
                status = "✓" if metrics["exact_match"] else "○"
                print(f"  [{i+1}/{len(instances)}] {instance_id}: F1={metrics['f1']:.3f} {status}")
                
            except Exception as e:
                result["error"] = str(e)
                failed_count += 1
                print(f"  [{i+1}/{len(instances)}] {instance_id}: ERROR - {e}")
            
            # Write result immediately (streaming)
            f_out.write(json.dumps(result, ensure_ascii=False) + "\n")
            f_out.flush()
            
            results.append(result)
    
    # Print summary
    print("-" * 60)
    print("\nEvaluation Summary")
    print("=" * 60)
    print(f"Total Instances: {total_count}")
    print(f"Successful: {total_count - failed_count}")
    print(f"Failed: {failed_count}")
    
    if f1_scores:
        avg_f1 = sum(f1_scores) / len(f1_scores)
        print(f"\nAverage F1 Score: {avg_f1:.4f}")
        
        exact_matches = sum(1 for r in results if r.get("metrics", {}).get("exact_match", False))
        print(f"Exact Matches: {exact_matches}/{len(f1_scores)} ({100*exact_matches/len(f1_scores):.1f}%)")
    else:
        print("\nNo successful evaluations to compute average F1.")
    
    print(f"\nResults saved to: {output_file}")
    print("=" * 60)


def main() -> None:
    """Main entry point."""
    args = parse_args()
    run_evaluation(args)


if __name__ == "__main__":
    main()
