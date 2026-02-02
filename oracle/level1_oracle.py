"""
Level-1 oracle implementation.
Orchestrates the oracle pipeline for Level 1 instances.
"""

import json
import sys
from pathlib import Path
from typing import Dict, List

# Add repo root to path for imports
repo_root = Path(__file__).parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from oracle.oracle_core import (
    parse_datetime,
    compute_common_free_windows,
    enumerate_candidates,
    select_top_n
)
from oracle.slot_resolver import resolve_slots
from oracle.constraints import apply_constraints


def load_world(world_path: str) -> Dict:
    """Load world JSON file."""
    with open(world_path, 'r') as f:
        return json.load(f)


def load_instances(instances_path: str) -> List[Dict]:
    """Load instances JSONL file."""
    instances = []
    with open(instances_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line:
                instances.append(json.loads(line))
    return instances


def gather_busy_intervals(world: Dict, participants: List[str], tz_str: str) -> List[tuple]:
    """
    Gather all busy intervals for given participants.
    
    Args:
        world: World data dict
        participants: List of participant IDs
        tz_str: Timezone string for parsing datetimes
    
    Returns:
        List of (start_datetime, end_datetime) tuples
    """
    busy_intervals = []
    calendar_json = world["sources"]["calendar_json"]
    
    for person_id in participants:
        if person_id not in calendar_json:
            continue
        
        for event in calendar_json[person_id]:
            start_dt = parse_datetime(event["start"], tz_str)
            end_dt = parse_datetime(event["end"], tz_str)
            busy_intervals.append((start_dt, end_dt))
    
    return busy_intervals


def process_instance(world: Dict, instance: Dict, debug: bool = False) -> tuple:
    """
    Process a single instance and return oracle result.
    
    Args:
        world: World data dict
        instance: Instance data dict
        debug: If True, return debug info
    
    Returns:
        Tuple of (result_dict, debug_info) where:
        - result_dict: Dict with instance_id, feasible_candidates, explanation_keys, meta
          or None if instance should be discarded
        - debug_info: Dict with debug counts (num_generated, num_after_constraints, discarded)
    """
    # Resolve slots
    slots = resolve_slots(1, world, instance)
    
    # Get timezone from world
    tz_str = world.get("timezone", "Asia/Seoul")
    
    # Gather busy intervals
    busy_intervals = gather_busy_intervals(world, slots["participants"], tz_str)
    
    # Parse time window
    time_window_start = parse_datetime(slots["time_window"]["start"], tz_str)
    time_window_end = parse_datetime(slots["time_window"]["end"], tz_str)
    
    # Compute common free windows
    free_intervals = compute_common_free_windows(busy_intervals, time_window_start, time_window_end)
    
    # Enumerate candidates on 15-minute grid
    base_candidates = enumerate_candidates(
        free_intervals,
        slots["duration_min"],
        time_window_start,
        time_window_end,
        tz_str,
        grid_minutes=15
    )
    
    num_generated = len(base_candidates)
    
    # Apply constraints
    filtered_candidates = apply_constraints(1, world, slots, base_candidates)
    
    num_after_constraints = len(filtered_candidates)
    
    # Check if we have enough candidates
    num_options = slots["num_options"]
    discarded = num_after_constraints < num_options
    
    debug_info = {
        "num_generated": num_generated,
        "num_after_constraints": num_after_constraints,
        "num_options": num_options,
        "discarded": discarded
    }
    
    if discarded:
        return (None, debug_info)
    
    # Select top N
    final_candidates = select_top_n(filtered_candidates, num_options)
    
    # Build explanation_keys
    explanation_keys = [
        {"source": "calendar_json", "key": person_id}
        for person_id in slots["participants"]
    ]
    explanation_keys.append({
        "source": "policy_json",
        "key": slots["policy_id"]
    })
    explanation_keys.append({
        "source": "slots",
        "key": "time_window"
    })
    
    result = {
        "instance_id": instance["instance_id"],
        "feasible_candidates": final_candidates,
        "explanation_keys": explanation_keys,
        "meta": {
            "num_generated": num_generated,
            "num_after_constraints": num_after_constraints,
            "num_options": num_options
        }
    }
    
    return (result, debug_info)


def run_level1_oracle(world_path: str, instances_path: str, output_path: str, debug: bool = False):
    """
    Run Level-1 oracle on test inputs.
    
    Args:
        world_path: Path to world JSON file
        instances_path: Path to instances JSONL file
        output_path: Path to output JSONL file
        debug: If True, print debug summaries for each instance
    """
    # Load data
    world = load_world(world_path)
    instances = load_instances(instances_path)
    
    # Process each instance
    results = []
    for instance in instances:
        result, debug_info = process_instance(world, instance, debug=debug)
        
        if debug:
            policy_id = instance["slots"]["policy_id"]
            status = "DISCARDED" if debug_info["discarded"] else "OK"
            discard_reason = ""
            if debug_info["discarded"]:
                discard_reason = f" (discard: after_constraints={debug_info['num_after_constraints']} < num_options={debug_info['num_options']})"
            print(f"{instance['instance_id']} | {policy_id} | "
                  f"generated={debug_info['num_generated']} "
                  f"after_constraints={debug_info['num_after_constraints']} "
                  f"num_options={debug_info['num_options']} | {status}{discard_reason}")
        
        if result is not None:
            results.append(result)
    
    # Write output
    with open(output_path, 'w') as f:
        for result in results:
            f.write(json.dumps(result) + '\n')
    
    print(f"Processed {len(instances)} instances, wrote {len(results)} results to {output_path}")
