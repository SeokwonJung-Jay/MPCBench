#!/usr/bin/env python3
"""
Level 2 testcase generator for MPCBench.

Generates World (with policy_text + policy_tags) + Instances (with comm_threads) + Oracle output.
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

from oracle.level2_oracle import process_instance


# =============================================================================
# Fixed Patterns (World)
# =============================================================================

CALENDAR_PATTERNS = {
    "person_001": [
        {"start": "2026-01-19T10:00:00+09:00", "end": "2026-01-19T11:00:00+09:00", "title": "Meeting A"},
        {"start": "2026-01-20T14:00:00+09:00", "end": "2026-01-20T15:00:00+09:00", "title": "Meeting B"},
        {"start": "2026-01-22T09:00:00+09:00", "end": "2026-01-22T10:00:00+09:00", "title": "Meeting C"},
    ],
    "person_002": [
        {"start": "2026-01-19T13:00:00+09:00", "end": "2026-01-19T14:00:00+09:00", "title": "Meeting D"},
        {"start": "2026-01-20T11:30:00+09:00", "end": "2026-01-20T12:00:00+09:00", "title": "Meeting E"},
        {"start": "2026-01-21T15:00:00+09:00", "end": "2026-01-21T16:00:00+09:00", "title": "Meeting F"},
    ],
    "person_003": [
        {"start": "2026-01-19T15:00:00+09:00", "end": "2026-01-19T16:00:00+09:00", "title": "Meeting G"},
        {"start": "2026-01-20T10:00:00+09:00", "end": "2026-01-20T11:00:00+09:00", "title": "Meeting H"},
        {"start": "2026-01-21T10:00:00+09:00", "end": "2026-01-21T10:15:00+09:00", "title": "Meeting I"},
        {"start": "2026-01-23T14:00:00+09:00", "end": "2026-01-23T15:00:00+09:00", "title": "Meeting J"},
    ],
    "person_004": [
        {"start": "2026-01-20T09:00:00+09:00", "end": "2026-01-20T10:00:00+09:00", "title": "Meeting K"},
        {"start": "2026-01-21T13:00:00+09:00", "end": "2026-01-21T14:00:00+09:00", "title": "Meeting L"},
    ],
    "person_005": [
        {"start": "2026-01-19T11:00:00+09:00", "end": "2026-01-19T12:00:00+09:00", "title": "Meeting N"},
        {"start": "2026-01-22T14:00:00+09:00", "end": "2026-01-22T15:00:00+09:00", "title": "Meeting O"},
        {"start": "2026-01-23T10:00:00+09:00", "end": "2026-01-23T11:00:00+09:00", "title": "Meeting P"},
    ],
}

POLICY_TEXT = """COMPANY MEETING POLICY DOCUMENT v2.3

This document outlines the meeting policies for all employees. Please read carefully and follow these guidelines. Actually, wait, I think there was an update last week. Let me check...

Section 1: Work Hours
Employees should schedule meetings during standard work hours. The standard work hours are 9 AM to 6 PM. Actually, I think it might be 8:30 AM to 5:30 PM in some departments. Let me verify... No wait, it's definitely 9 to 6. Or is it 9:30? Hmm.

Section 2: Lunch Breaks
Lunch breaks are from 12:00 PM to 1:00 PM. Do not schedule meetings during this time. Actually, some teams have lunch from 11:30 to 12:30, but the official policy is 12 to 1. I think.

Section 3: Buffer Times
There should be a buffer between meetings. I think it's 10 minutes. Or maybe 15? Let me check the handbook... Actually, the system says 10 minutes minimum buffer. Yes, 10 minutes.

Section 4: Restricted Times
Monday mornings from 9 AM to 12 PM are restricted. Also Friday afternoons from 1 PM to 6 PM. Wait, is that right? Let me double-check... Yes, Monday 9-12 and Friday 1-6 are restricted.

Note: This policy may be updated. Please refer to the latest version. Actually, I'm not sure if this is the latest version. Someone should update this document.

Also note: Some of the above information might be outdated. Please verify with HR.

END OF POLICY DOCUMENT"""

POLICY_TAGS = {
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

# Communication thread templates (with noise)
COMM_THREAD_TEMPLATES = {
    "deadline": [
        "Hey team, we need to schedule a meeting. The deadline is {deadline_text}. Actually, wait, maybe it's later? No, I think that's right. Let me check... Yes, {deadline_text}.",
        "We need to meet before {deadline_text}. I'm not 100% sure about the exact time, but I think that's the deadline. Or was it earlier? Anyway, let's aim for that.",
        "Quick reminder - the meeting needs to happen by {deadline_text}. Someone told me it might be flexible, but let's stick with that deadline.",
    ],
    "ban_windows": [
        "Some time slots are blocked. I heard {ban_text} is not available. Or was it a different time? The calendar should have the exact info.",
        "We can't meet during {ban_text}. That time is reserved for something else. At least I think so. Check the internal records.",
        "Avoid scheduling during {ban_text}. Those slots are blocked. I'm pretty sure that's correct.",
    ],
    "required_windows": [
        "The meeting must happen within {required_text}. That's the only available window. Or maybe there's another option? Let me check...",
        "We're limited to {required_text} for this meeting. I think those are the only times that work for everyone.",
        "Please schedule within {required_text}. Those are the approved time slots.",
    ],
    "combined": [
        "This is complicated. The deadline is {deadline_text}. Also, {ban_text} is blocked. We need to meet within {required_text}. I think. Let me verify... Actually, I'm not 100% sure about all of this.",
        "Multiple constraints here: deadline {deadline_text}, avoid {ban_text}, and stick to {required_text}. The system should have more details.",
    ],
}


# =============================================================================
# World Generation
# =============================================================================

def generate_world(suffix: str) -> Dict:
    """Generate world data with policy_text and policy_tags."""
    return {
        "world_id": f"world_level2_{suffix}",
        "level": 2,
        "timezone": "Asia/Seoul",
        "world_start": "2026-01-19T00:00:00+09:00",
        "world_end": "2026-01-23T23:59:59+09:00",
        "sources": {
            "calendar_json": CALENDAR_PATTERNS,
            "policy_text": POLICY_TEXT,
            "policy_tags": POLICY_TAGS,
        }
    }


# =============================================================================
# Communication Thread Generation
# =============================================================================

def format_time_window(start: str, end: str) -> str:
    """Format a time window for natural language."""
    start_time = start.split("T")[1][:5]
    end_time = end.split("T")[1][:5]
    return f"{start_time} to {end_time}"


def generate_comm_thread(day: str, constraint_type: str) -> Tuple[str, Dict]:
    """
    Generate communication thread text and tags.
    
    Args:
        day: The day string (e.g., "2026-01-19")
        constraint_type: One of "deadline", "ban_windows", "required_windows", "combined"
    
    Returns:
        Tuple of (comm_thread_text, comm_tags)
    """
    comm_tags = {}
    template_vars = {}
    
    if constraint_type == "deadline":
        # Generate a deadline
        deadline_hour = random.randint(12, 17)
        deadline = f"{day}T{deadline_hour:02d}:00:00+09:00"
        comm_tags["deadline"] = deadline
        template_vars["deadline_text"] = f"{deadline_hour}:00"
        template = random.choice(COMM_THREAD_TEMPLATES["deadline"])
        
    elif constraint_type == "ban_windows":
        # Generate 1-2 ban windows
        num_bans = random.randint(1, 2)
        ban_windows = []
        ban_texts = []
        used_hours = set()
        
        for _ in range(num_bans):
            start_hour = random.choice([h for h in [9, 10, 11, 14, 15, 16] if h not in used_hours])
            used_hours.add(start_hour)
            ban_start = f"{day}T{start_hour:02d}:00:00+09:00"
            ban_end = f"{day}T{start_hour + 1:02d}:00:00+09:00"
            ban_windows.append({"start": ban_start, "end": ban_end})
            ban_texts.append(f"{start_hour}:00-{start_hour + 1}:00")
        
        comm_tags["ban_windows"] = ban_windows
        template_vars["ban_text"] = " and ".join(ban_texts)
        template = random.choice(COMM_THREAD_TEMPLATES["ban_windows"])
        
    elif constraint_type == "required_windows":
        # Generate 1-2 required windows
        num_required = random.randint(1, 2)
        required_windows = []
        required_texts = []
        
        # Morning window
        if num_required >= 1:
            start_hour = random.choice([9, 10])
            end_hour = start_hour + 2
            req_start = f"{day}T{start_hour:02d}:00:00+09:00"
            req_end = f"{day}T{end_hour:02d}:00:00+09:00"
            required_windows.append({"start": req_start, "end": req_end})
            required_texts.append(f"{start_hour}:00-{end_hour}:00")
        
        # Afternoon window
        if num_required >= 2:
            start_hour = random.choice([14, 15])
            end_hour = start_hour + 2
            req_start = f"{day}T{start_hour:02d}:00:00+09:00"
            req_end = f"{day}T{end_hour:02d}:00:00+09:00"
            required_windows.append({"start": req_start, "end": req_end})
            required_texts.append(f"{start_hour}:00-{end_hour}:00")
        
        comm_tags["required_windows"] = required_windows
        template_vars["required_text"] = " or ".join(required_texts)
        template = random.choice(COMM_THREAD_TEMPLATES["required_windows"])
        
    else:  # combined
        # Deadline
        deadline_hour = random.randint(14, 17)
        deadline = f"{day}T{deadline_hour:02d}:00:00+09:00"
        comm_tags["deadline"] = deadline
        template_vars["deadline_text"] = f"{deadline_hour}:00"
        
        # Ban window
        ban_hour = random.choice([10, 11])
        ban_start = f"{day}T{ban_hour:02d}:00:00+09:00"
        ban_end = f"{day}T{ban_hour + 1:02d}:00:00+09:00"
        comm_tags["ban_windows"] = [{"start": ban_start, "end": ban_end}]
        template_vars["ban_text"] = f"{ban_hour}:00-{ban_hour + 1}:00"
        
        # Required window
        req_start_hour = random.choice([9, 14])
        req_end_hour = req_start_hour + 2
        req_start = f"{day}T{req_start_hour:02d}:00:00+09:00"
        req_end = f"{day}T{req_end_hour:02d}:00:00+09:00"
        comm_tags["required_windows"] = [{"start": req_start, "end": req_end}]
        template_vars["required_text"] = f"{req_start_hour}:00-{req_end_hour}:00"
        
        template = random.choice(COMM_THREAD_TEMPLATES["combined"])
    
    comm_text = template.format(**template_vars)
    return comm_text, comm_tags


# =============================================================================
# Instance Generation (Slot-Filling)
# =============================================================================

def generate_instance(world: Dict, idx: int, suffix: str) -> Dict:
    """Generate a single Level 2 instance using slot-filling."""
    # Random slot values (3 participants for L2)
    participants = random.sample(PERSON_IDS, 3)
    duration_min = random.choice(DURATION_OPTIONS)
    num_options = random.choice(NUM_OPTIONS_CHOICES)
    policy_id = random.choice(POLICY_IDS)
    
    # Random time window
    day = random.choice(DAYS)
    start_hour = random.randint(9, 12)
    window_hours = random.randint(4, 8)
    end_hour = min(start_hour + window_hours, 18)
    
    time_window_start = f"{day}T{start_hour:02d}:00:00+09:00"
    time_window_end = f"{day}T{end_hour:02d}:00:00+09:00"
    
    # Generate communication thread
    constraint_type = random.choice(["deadline", "ban_windows", "required_windows", "combined"])
    comm_text, comm_tags = generate_comm_thread(day, constraint_type)
    
    # Generate task_text (Level 2: vague, doesn't name sources explicitly)
    task_templates = [
        "Schedule a meeting for three participants across internal sources. Find feasible time slots that meet all requirements.",
        "Find meeting times for three team members. Check all internal sources to identify available slots.",
        "Coordinate a meeting with multiple constraints. Review internal sources to find feasible options.",
        "Schedule a meeting that satisfies all policy and communication constraints.",
    ]
    task_text = random.choice(task_templates)
    
    instance_id = f"instance_level2_{suffix}_{idx:03d}"
    
    return {
        "instance_id": instance_id,
        "level": 2,
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
        },
        "sources": {
            "comm_thread_text": comm_text,
            "comm_tags": comm_tags,
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
    
    # 1. Generate world
    world = generate_world(suffix)
    world_path = output_dir / f"world_level2_{suffix}.json"
    with open(world_path, "w", encoding="utf-8") as f:
        json.dump(world, f, indent=2, ensure_ascii=False)
    print(f"[World] Saved to {world_path}")
    
    # 2. Generate instances with Oracle validation loop
    valid_instances: List[Dict] = []
    oracle_results: List[Dict] = []
    max_attempts = num_instances * 5
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
            constraint_type = "deadline" if "deadline" in instance["sources"]["comm_tags"] else \
                              "ban" if "ban_windows" in instance["sources"]["comm_tags"] else \
                              "required" if "required_windows" in instance["sources"]["comm_tags"] else "none"
            print(f"  [{len(valid_instances)}/{num_instances}] {instance['instance_id']} - OK "
                  f"(candidates: {debug_info['num_after_constraints']}, type: {constraint_type})")
        else:
            # Discarded
            print(f"  [X] Discarded: {instance['slots']['policy_id']}, "
                  f"candidates={debug_info['num_after_constraints']} < {debug_info['num_options']}")
    
    # 3. Save instances
    instances_path = output_dir / f"instances_level2_{suffix}.jsonl"
    with open(instances_path, "w", encoding="utf-8") as f:
        for inst in valid_instances:
            f.write(json.dumps(inst, ensure_ascii=False) + "\n")
    print(f"[Instance] Saved {len(valid_instances)} instances to {instances_path}")
    
    # 4. Save oracle results
    oracle_path = output_dir / f"oracle_level2_{suffix}.jsonl"
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
    print(f"Discard rate:      {(attempts - len(valid_instances)) / max(attempts, 1) * 100:.1f}%")
    print(f"{'='*60}")
    
    if len(valid_instances) < num_instances:
        print(f"WARNING: Could only generate {len(valid_instances)}/{num_instances} valid instances.")
    
    return len(valid_instances), attempts


# =============================================================================
# CLI
# =============================================================================

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate Level 2 testcases for MPCBench."
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
