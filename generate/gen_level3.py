#!/usr/bin/env python3
"""
Level 3 testcase generator for MPCBench.

Generates World (with people_table, rooms_table, room_availability) + Instances (with comm_threads) + Oracle output.
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

from oracle.level3_oracle import process_instance


# =============================================================================
# Fixed Patterns (World)
# =============================================================================

CALENDAR_PATTERNS = {
    "person_001": [
        {"start": "2026-01-19T10:00:00+09:00", "end": "2026-01-19T11:00:00+09:00", "title": "Team Standup"},
        {"start": "2026-01-20T14:00:00+09:00", "end": "2026-01-20T15:30:00+09:00", "title": "Design Review"},
        {"start": "2026-01-22T09:00:00+09:00", "end": "2026-01-22T10:00:00+09:00", "title": "Client Call"},
    ],
    "person_002": [
        {"start": "2026-01-19T13:00:00+09:00", "end": "2026-01-19T14:00:00+09:00", "title": "Lunch Meeting"},
        {"start": "2026-01-20T11:30:00+09:00", "end": "2026-01-20T12:00:00+09:00", "title": "Quick Sync"},
        {"start": "2026-01-21T15:00:00+09:00", "end": "2026-01-21T16:00:00+09:00", "title": "Project Review"},
    ],
    "person_003": [
        {"start": "2026-01-19T15:00:00+09:00", "end": "2026-01-19T16:00:00+09:00", "title": "Code Review"},
        {"start": "2026-01-20T10:00:00+09:00", "end": "2026-01-20T11:00:00+09:00", "title": "Sprint Planning"},
        {"start": "2026-01-21T10:00:00+09:00", "end": "2026-01-21T10:15:00+09:00", "title": "Quick Check"},
        {"start": "2026-01-23T14:00:00+09:00", "end": "2026-01-23T15:00:00+09:00", "title": "Team Retro"},
    ],
    "person_004": [
        {"start": "2026-01-20T09:00:00+09:00", "end": "2026-01-20T10:00:00+09:00", "title": "Morning Sync"},
        {"start": "2026-01-21T13:00:00+09:00", "end": "2026-01-21T14:00:00+09:00", "title": "Lunch Meeting"},
    ],
    "person_005": [
        {"start": "2026-01-19T11:00:00+09:00", "end": "2026-01-19T12:00:00+09:00", "title": "Client Demo"},
        {"start": "2026-01-22T14:00:00+09:00", "end": "2026-01-22T15:00:00+09:00", "title": "Architecture Review"},
        {"start": "2026-01-23T10:00:00+09:00", "end": "2026-01-23T11:00:00+09:00", "title": "Product Review"},
    ],
    "person_006": [
        {"start": "2026-01-19T14:00:00+09:00", "end": "2026-01-19T15:00:00+09:00", "title": "Training Session"},
        {"start": "2026-01-21T11:00:00+09:00", "end": "2026-01-21T12:00:00+09:00", "title": "Workshop"},
    ],
    "person_007": [
        {"start": "2026-01-20T13:00:00+09:00", "end": "2026-01-20T14:00:00+09:00", "title": "Lunch Meeting"},
        {"start": "2026-01-22T11:00:00+09:00", "end": "2026-01-22T12:00:00+09:00", "title": "Team Sync"},
    ],
    "person_008": [
        {"start": "2026-01-19T09:00:00+09:00", "end": "2026-01-19T10:00:00+09:00", "title": "Daily Standup"},
        {"start": "2026-01-21T14:00:00+09:00", "end": "2026-01-21T15:00:00+09:00", "title": "Design Discussion"},
    ],
    "person_009": [
        {"start": "2026-01-20T15:00:00+09:00", "end": "2026-01-20T16:00:00+09:00", "title": "Code Review"},
        {"start": "2026-01-23T13:00:00+09:00", "end": "2026-01-23T14:00:00+09:00", "title": "Lunch Meeting"},
    ],
    "person_010": [
        {"start": "2026-01-19T12:00:00+09:00", "end": "2026-01-19T13:00:00+09:00", "title": "Lunch Meeting"},
        {"start": "2026-01-22T10:00:00+09:00", "end": "2026-01-22T11:00:00+09:00", "title": "Client Call"},
    ],
}

POLICY_TEXT = """COMPANY MEETING POLICY DOCUMENT v3.1 - FINAL DRAFT

This is the official meeting policy document. Actually, wait, I think there was a revision last month. Let me check the version history... No, this is definitely the latest. Or is it?

Section 1: Standard Work Hours
All meetings must be scheduled during standard business hours. The standard hours are 9:00 AM to 6:00 PM, Monday through Friday. Actually, I think some departments use 8:30 AM to 5:30 PM, but the official policy is 9 to 6. Or maybe it's 9:30? Let me verify with HR... Actually, the system configuration says 9 AM to 6 PM, so that's what we'll use.

Section 2: Lunch Break Policy
Lunch breaks are from 12:00 PM to 1:00 PM daily. No meetings should be scheduled during this time. Some teams have flexible lunch hours from 11:30 to 12:30, but the corporate standard is 12 to 1. I think.

Section 3: Buffer Requirements
There must be a minimum buffer time between consecutive meetings. The system requires a 10-minute buffer. Or is it 15 minutes? Let me check... Actually, the handbook says 10 minutes minimum. Yes, 10 minutes.

Section 4: Restricted Time Windows
Monday mornings from 9:00 AM to 12:00 PM are restricted for all-hands meetings. Friday afternoons from 1:00 PM to 6:00 PM are also restricted. Wait, is that correct? Let me double-check the calendar... Yes, Monday 9-12 and Friday 1-6 are restricted periods.

Note: This policy supersedes all previous versions. Please refer to the latest update. Actually, I'm not entirely sure if this is the latest version. Someone should verify this with the compliance team.

Additional Note: Some sections may be outdated. Please confirm with your manager before scheduling critical meetings.

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

PEOPLE_TABLE = {
    "primary_key": "person_id",
    "columns": ["person_id", "person_name", "team", "email", "notes"],
    "rows": [
        {"person_id": "person_001", "person_name": "Alice", "team": "Engineering", "email": "alice@company.com", "notes": "Senior Engineer"},
        {"person_id": "person_002", "person_name": "Bob", "team": "Product", "email": "bob@company.com", "notes": "Product Manager"},
        {"person_id": "person_003", "person_name": "Charlie", "team": "Engineering", "email": "charlie@company.com", "notes": "Tech Lead"},
        {"person_id": "person_004", "person_name": "Diana", "team": "Design", "email": "diana@company.com", "notes": "UX Designer"},
        {"person_id": "person_005", "person_name": "Eve", "team": "Engineering", "email": "eve@company.com", "notes": "Backend Engineer"},
        {"person_id": "person_006", "person_name": "Frank", "team": "Marketing", "email": "frank@company.com", "notes": "Marketing Lead"},
        {"person_id": "person_007", "person_name": "Grace", "team": "Sales", "email": "grace@company.com", "notes": "Sales Manager"},
        {"person_id": "person_008", "person_name": "Henry", "team": "Engineering", "email": "henry@company.com", "notes": "Frontend Engineer"},
        {"person_id": "person_009", "person_name": "Iris", "team": "Product", "email": "iris@company.com", "notes": "Product Designer"},
        {"person_id": "person_010", "person_name": "Jack", "team": "Operations", "email": "jack@company.com", "notes": "Ops Manager"},
    ],
    "meta": {"version": "1.0", "last_updated": "2026-01-01"}
}

ROOMS_TABLE = {
    "primary_key": "room_id",
    "columns": ["room_id", "capacity", "floor", "equipment", "notes"],
    "rows": [
        {"room_id": "room_001", "capacity": 2, "floor": "1", "equipment": "whiteboard", "notes": "Small meeting room"},
        {"room_id": "room_002", "capacity": 4, "floor": "1", "equipment": "projector", "notes": "Medium room"},
        {"room_id": "room_003", "capacity": 6, "floor": "2", "equipment": "whiteboard,projector", "notes": "Large room"},
        {"room_id": "room_004", "capacity": 8, "floor": "2", "equipment": "video_conference", "notes": "Conference room"},
        {"room_id": "room_005", "capacity": 10, "floor": "3", "equipment": "projector,video_conference", "notes": "Executive room"},
        {"room_id": "room_006", "capacity": 12, "floor": "3", "equipment": "whiteboard,projector,video_conference", "notes": "Boardroom"},
    ],
    "meta": {"version": "1.0", "last_updated": "2026-01-01"}
}

ROOM_AVAILABILITY = {
    "room_001": [
        {"start": "2026-01-19T10:00:00+09:00", "end": "2026-01-19T11:00:00+09:00", "title": "Booked"},
        {"start": "2026-01-20T14:00:00+09:00", "end": "2026-01-20T15:00:00+09:00", "title": "Booked"},
    ],
    "room_002": [
        {"start": "2026-01-19T13:00:00+09:00", "end": "2026-01-19T14:00:00+09:00", "title": "Booked"},
        {"start": "2026-01-21T15:00:00+09:00", "end": "2026-01-21T16:00:00+09:00", "title": "Booked"},
    ],
    "room_003": [
        {"start": "2026-01-19T09:00:00+09:00", "end": "2026-01-19T10:00:00+09:00", "title": "Booked"},
        {"start": "2026-01-20T11:00:00+09:00", "end": "2026-01-20T12:00:00+09:00", "title": "Booked"},
        {"start": "2026-01-22T09:00:00+09:00", "end": "2026-01-22T10:00:00+09:00", "title": "Booked"},
    ],
    "room_004": [
        {"start": "2026-01-19T11:00:00+09:00", "end": "2026-01-19T12:00:00+09:00", "title": "Booked"},
        {"start": "2026-01-21T10:00:00+09:00", "end": "2026-01-21T11:00:00+09:00", "title": "Booked"},
        {"start": "2026-01-23T14:00:00+09:00", "end": "2026-01-23T15:00:00+09:00", "title": "Booked"},
    ],
    "room_005": [
        {"start": "2026-01-20T10:00:00+09:00", "end": "2026-01-20T11:00:00+09:00", "title": "Booked"},
        {"start": "2026-01-22T14:00:00+09:00", "end": "2026-01-22T15:00:00+09:00", "title": "Booked"},
    ],
    "room_006": [
        {"start": "2026-01-19T14:00:00+09:00", "end": "2026-01-19T15:00:00+09:00", "title": "Booked"},
        {"start": "2026-01-21T13:00:00+09:00", "end": "2026-01-21T14:00:00+09:00", "title": "Booked"},
        {"start": "2026-01-23T10:00:00+09:00", "end": "2026-01-23T11:00:00+09:00", "title": "Booked"},
    ],
}

# Slot options
PERSON_NAMES = ["Alice", "Bob", "Charlie", "Diana", "Eve", "Frank", "Grace", "Henry", "Iris", "Jack"]
DURATION_OPTIONS = [30, 60]
NUM_OPTIONS = 3  # Fixed for Level 3
POLICY_IDS = ["POLICY_1", "POLICY_2", "POLICY_3", "POLICY_4"]
DAYS = ["2026-01-19", "2026-01-20", "2026-01-21", "2026-01-22", "2026-01-23"]


# =============================================================================
# World Generation
# =============================================================================

def generate_world(suffix: str) -> Dict:
    """Generate world data with people_table, rooms_table, and room_availability."""
    return {
        "world_id": f"world_level3_{suffix}",
        "level": 3,
        "timezone": "Asia/Seoul",
        "world_start": "2026-01-19T00:00:00+09:00",
        "world_end": "2026-01-23T23:59:59+09:00",
        "sources": {
            "calendar_json": CALENDAR_PATTERNS,
            "policy_text": POLICY_TEXT,
            "policy_tags": POLICY_TAGS,
            "people_table": PEOPLE_TABLE,
            "rooms_table": ROOMS_TABLE,
            "room_availability_json": ROOM_AVAILABILITY,
        }
    }


# =============================================================================
# Communication Thread Generation
# =============================================================================

def generate_comm_threads(participants: List[str], duration_min: int, num_options: int, 
                          time_window_start: str, time_window_end: str, policy_id: str) -> List[Dict]:
    """
    Generate communication threads for Level 3.
    
    Returns:
        List of thread dicts with thread_id, thread_text, and thread_tags.
    """
    # Context thread (noise)
    context_templates = [
        "Hey, just wanted to check on the project status. How's everything going? We might need some updates.",
        "Quick question about the meeting. I think we need enough time between meetings. Someone mentioned buffer times.",
        "I heard there might be some scheduling conflicts. Some spaces might be booked, but I'm not sure which ones.",
        "This might be tricky. The time window is narrow and we have several people. Let's see what works.",
    ]
    
    # Task thread (contains actual requirements in thread_tags)
    participants_str = ", ".join(participants)
    task_text = (
        f"Please schedule a meeting. Participants are {participants_str}. "
        f"The time window is from {time_window_start} to {time_window_end}. "
        f"Meeting duration is {duration_min} minutes, and we must follow organizational rules {policy_id}. "
        f"Please provide {num_options} options. Each option is a unique (time_slot, room) combination. "
        f"Find the best available time slot first, then provide {num_options} different rooms for that slot. "
        f"Sort by earliest start → earliest end → smallest room_id."
    )
    
    return [
        {
            "thread_id": f"thread_context_{random.randint(100, 999)}",
            "thread_text": random.choice(context_templates),
            "thread_tags": {}
        },
        {
            "thread_id": f"thread_task_{random.randint(100, 999)}",
            "thread_text": task_text,
            "thread_tags": {
                "sort_spec": {"keys": ["start", "end", "room_id"]}
            }
        }
    ]


# =============================================================================
# Instance Generation (Slot-Filling)
# =============================================================================

def generate_instance(world: Dict, idx: int, suffix: str) -> Dict:
    """Generate a single Level 3 instance using slot-filling."""
    # Random slot values (3-6 participants for L3, using names)
    num_participants = random.randint(3, 6)
    participants = random.sample(PERSON_NAMES, num_participants)
    duration_min = random.choice(DURATION_OPTIONS)
    policy_id = random.choice(POLICY_IDS)
    
    # Random time window
    day = random.choice(DAYS)
    start_hour = random.randint(9, 12)
    window_hours = random.randint(4, 8)
    end_hour = min(start_hour + window_hours, 18)
    
    time_window_start = f"{day}T{start_hour:02d}:00:00+09:00"
    time_window_end = f"{day}T{end_hour:02d}:00:00+09:00"
    
    # Generate communication threads
    comm_threads = generate_comm_threads(
        participants, duration_min, NUM_OPTIONS,
        time_window_start, time_window_end, policy_id
    )
    
    # Generate task_text (Level 3: vague, doesn't name sources explicitly)
    task_text = (
        "Propose meeting candidates discussed in the communication threads. "
        "The requirements are scattered across different internal records, and you must satisfy "
        "participant/time constraints, organizational rules, and space constraints."
    )
    
    instance_id = f"instance_level3_{suffix}_{idx:03d}"
    
    return {
        "instance_id": instance_id,
        "level": 3,
        "task_text": task_text,
        "slots": {
            "time_window": {
                "start": time_window_start,
                "end": time_window_end,
            },
            "participants": participants,
            "duration_min": duration_min,
            "num_options": NUM_OPTIONS,
            "policy_id": policy_id,
        },
        "sources_ref": {
            "world_id": world["world_id"],
        },
        "sources": {
            "comm_threads": comm_threads,
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
    world_path = output_dir / f"world_level3_{suffix}.json"
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
            print(f"  [{len(valid_instances)}/{num_instances}] {instance['instance_id']} - OK "
                  f"(room_candidates: {debug_info['num_after_room_join']}, participants: {len(instance['slots']['participants'])})")
        else:
            # Discarded
            print(f"  [X] Discarded: {instance['slots']['policy_id']}, "
                  f"participants={len(instance['slots']['participants'])}, "
                  f"room_candidates={debug_info['num_after_room_join']} < {debug_info['num_options']}")
    
    # 3. Save instances
    instances_path = output_dir / f"instances_level3_{suffix}.jsonl"
    with open(instances_path, "w", encoding="utf-8") as f:
        for inst in valid_instances:
            f.write(json.dumps(inst, ensure_ascii=False) + "\n")
    print(f"[Instance] Saved {len(valid_instances)} instances to {instances_path}")
    
    # 4. Save oracle results
    oracle_path = output_dir / f"oracle_level3_{suffix}.jsonl"
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
        description="Generate Level 3 testcases for MPCBench."
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
