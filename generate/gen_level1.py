#!/usr/bin/env python3
"""
Level 1 testcase generator for MPCBench.

Generates World (fixed patterns) + Instances (slot-filling) + Oracle output.
"""

import argparse
import json
import random
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Add repo root to path
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root))

from oracle.level1_oracle import process_instance


# =============================================================================
# Fixed Patterns (World)
# =============================================================================

CALENDAR_PATTERNS = {
    "person_001": [
        {"start": "2026-01-19T10:00:00", "end": "2026-01-19T11:00:00", "title": "Meeting A"},
        {"start": "2026-01-20T14:00:00", "end": "2026-01-20T15:00:00", "title": "Meeting B"},
        {"start": "2026-01-22T09:00:00", "end": "2026-01-22T10:00:00", "title": "Meeting C"},
    ],
    "person_002": [
        {"start": "2026-01-19T13:00:00", "end": "2026-01-19T14:00:00", "title": "Meeting D"},
        {"start": "2026-01-20T11:30:00", "end": "2026-01-20T12:00:00", "title": "Meeting E"},
        {"start": "2026-01-21T15:00:00", "end": "2026-01-21T16:00:00", "title": "Meeting F"},
    ],
    "person_003": [
        {"start": "2026-01-19T15:00:00", "end": "2026-01-19T16:00:00", "title": "Meeting G"},
        {"start": "2026-01-20T10:00:00", "end": "2026-01-20T11:00:00", "title": "Meeting H"},
        {"start": "2026-01-21T10:00:00", "end": "2026-01-21T10:15:00", "title": "Meeting I"},
        {"start": "2026-01-23T14:00:00", "end": "2026-01-23T15:00:00", "title": "Meeting J"},
    ],
    "person_004": [
        {"start": "2026-01-20T09:00:00", "end": "2026-01-20T10:00:00", "title": "Meeting K"},
        {"start": "2026-01-21T13:00:00", "end": "2026-01-21T14:00:00", "title": "Meeting L"},
    ],
    "person_005": [
        {"start": "2026-01-19T11:00:00", "end": "2026-01-19T12:00:00", "title": "Meeting N"},
        {"start": "2026-01-22T14:00:00", "end": "2026-01-22T15:00:00", "title": "Meeting O"},
        {"start": "2026-01-23T10:00:00", "end": "2026-01-23T11:00:00", "title": "Meeting P"},
    ],
}

POLICY_PATTERNS = {
    "POLICY_1": {
        "rules": [
            {"type": "work_hours", "start": "09:00", "end": "18:00", "days_of_week": [0, 1, 2, 3, 4]}
        ]
    },
    "POLICY_2": {
        "rules": [
            {"type": "lunch_block", "start": "12:00", "end": "13:00", "days_of_week": [0, 1, 2, 3, 4]}
        ]
    },
    "POLICY_3": {
        "rules": [
            {"type": "buffer_min", "minutes": 10}
        ]
    },
    "POLICY_4": {
        "rules": [
            {"type": "ban_dow_time", "day_of_week": 0, "start": "09:00", "end": "12:00"},
            {"type": "ban_dow_time", "day_of_week": 4, "start": "13:00", "end": "18:00"},
        ]
    },
}

# Slot options
PERSON_IDS = ["person_001", "person_002", "person_003", "person_004", "person_005"]
DURATION_OPTIONS = [15, 30, 60]
NUM_OPTIONS_CHOICES = [2, 3]
POLICY_IDS = ["POLICY_1", "POLICY_2", "POLICY_3", "POLICY_4"]
DAYS = ["2026-01-19", "2026-01-20", "2026-01-21", "2026-01-22", "2026-01-23"]


# =============================================================================
# World Generation
# =============================================================================

def generate_world(suffix: str) -> Dict:
    """Generate world data using fixed patterns."""
    return {
        "world_id": f"world_level1_{suffix}",
        "level": 1,
        "timezone": "Asia/Seoul",
        "world_start": "2026-01-19T00:00:00",
        "world_end": "2026-01-23T23:59:59",
        "sources": {
            "calendar_json": CALENDAR_PATTERNS,
            "policy_json": POLICY_PATTERNS,
        }
    }


# =============================================================================
# Instance Generation (Slot-Filling)
# =============================================================================

def generate_instance(world: Dict, idx: int, suffix: str) -> Dict:
    """Generate a single instance using slot-filling."""
    # Random slot values
    participants = random.sample(PERSON_IDS, 2)
    duration_min = random.choice(DURATION_OPTIONS)
    num_options = random.choice(NUM_OPTIONS_CHOICES)
    policy_id = random.choice(POLICY_IDS)
    
    # Random time window
    day = random.choice(DAYS)
    start_hour = random.randint(8, 14)
    window_hours = random.randint(3, 8)
    end_hour = min(start_hour + window_hours, 20)
    
    time_window_start = f"{day}T{start_hour:02d}:00:00"
    time_window_end = f"{day}T{end_hour:02d}:00:00"
    
    # Generate task_text from slots
    task_text = (
        f"Schedule a {duration_min}-minute meeting for {participants[0]} and {participants[1]} "
        f"within {time_window_start} to {time_window_end}. "
        f"You must follow company meeting policy ({policy_id}). "
        f"Provide {num_options} feasible time candidates sorted by earliest start time."
    )
    
    instance_id = f"instance_level1_{suffix}_{idx:03d}"
    
    return {
        "instance_id": instance_id,
        "level": 1,
        "task_text": task_text,
        "slots": {
            "time_window": {
                "start": time_window_start,
                "end": time_window_end,
            },
            "participants": participants,
            "duration_min": duration_min,
            "num_options": num_options,
            "policy_id": policy_id,
        },
        "sources_ref": {
            "world_id": world["world_id"],
        }
    }


# =============================================================================
# Main Generation Loop
# =============================================================================

def run_generation(
    num_instances: int,
    suffix: str,
    seed: Optional[int] = None,
    output_dir: Path = None,
) -> Tuple[int, int]:
    """
    Run the generation pipeline.
    
    Args:
        num_instances: Target number of valid instances.
        suffix: Output file suffix.
        seed: Random seed for reproducibility.
        output_dir: Output directory path.
    
    Returns:
        Tuple of (valid_count, total_attempts).
    """
    if seed is not None:
        random.seed(seed)
    
    if output_dir is None:
        output_dir = Path(__file__).parent / "output"
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. Generate world (fixed patterns)
    world = generate_world(suffix)
    world_path = output_dir / f"world_level1_{suffix}.json"
    with open(world_path, "w", encoding="utf-8") as f:
        json.dump(world, f, indent=2, ensure_ascii=False)
    print(f"[World] Saved to {world_path}")
    
    # 2. Generate instances with Oracle validation loop
    valid_instances: List[Dict] = []
    oracle_results: List[Dict] = []
    max_attempts = num_instances * 5  # Allow more retries
    attempts = 0
    
    print(f"[Instance] Generating {num_instances} instances (max attempts: {max_attempts})...")
    
    while len(valid_instances) < num_instances and attempts < max_attempts:
        # Generate candidate instance
        instance = generate_instance(world, len(valid_instances), suffix)
        
        # Validate with Oracle
        result, debug_info = process_instance(world, instance)
        
        attempts += 1
        
        if result is not None:
            # Valid instance
            valid_instances.append(instance)
            oracle_results.append(result)
            print(f"  [{len(valid_instances)}/{num_instances}] {instance['instance_id']} - OK "
                  f"(candidates: {debug_info['num_after_constraints']})")
        else:
            # Discarded
            print(f"  [X] Discarded: {instance['slots']['policy_id']}, "
                  f"window={instance['slots']['time_window']['start'][-13:-6]}~{instance['slots']['time_window']['end'][-13:-6]}, "
                  f"candidates={debug_info['num_after_constraints']} < {debug_info['num_options']}")
    
    # 3. Save instances
    instances_path = output_dir / f"instances_level1_{suffix}.jsonl"
    with open(instances_path, "w", encoding="utf-8") as f:
        for inst in valid_instances:
            f.write(json.dumps(inst, ensure_ascii=False) + "\n")
    print(f"[Instance] Saved {len(valid_instances)} instances to {instances_path}")
    
    # 4. Save oracle results
    oracle_path = output_dir / f"oracle_level1_{suffix}.jsonl"
    with open(oracle_path, "w", encoding="utf-8") as f:
        for res in oracle_results:
            f.write(json.dumps(res, ensure_ascii=False) + "\n")
    print(f"[Oracle] Saved {len(oracle_results)} results to {oracle_path}")
    
    # Summary
    print(f"\n{'='*60}")
    print(f"Generation Summary")
    print(f"{'='*60}")
    print(f"Target instances:  {num_instances}")
    print(f"Valid instances:   {len(valid_instances)}")
    print(f"Total attempts:    {attempts}")
    print(f"Discard rate:      {(attempts - len(valid_instances)) / attempts * 100:.1f}%")
    print(f"{'='*60}")
    
    if len(valid_instances) < num_instances:
        print(f"WARNING: Could only generate {len(valid_instances)}/{num_instances} valid instances.")
    
    return len(valid_instances), attempts


# =============================================================================
# CLI
# =============================================================================

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate Level 1 testcases for MPCBench."
    )
    parser.add_argument(
        "--num_instances",
        type=int,
        required=True,
        help="Number of valid instances to generate."
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed for reproducibility."
    )
    parser.add_argument(
        "--suffix",
        type=str,
        default=None,
        help="Output file suffix (default: timestamp)."
    )
    return parser.parse_args()


def main():
    args = parse_args()
    
    # Default suffix: timestamp
    if args.suffix is None:
        args.suffix = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    run_generation(
        num_instances=args.num_instances,
        suffix=args.suffix,
        seed=args.seed,
    )


if __name__ == "__main__":
    main()
