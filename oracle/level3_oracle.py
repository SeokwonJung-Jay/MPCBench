"""
Level-3 oracle implementation.
Orchestrates the oracle pipeline for Level 3 instances.
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple

# Add repo root to path for imports
repo_root = Path(__file__).parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from oracle.oracle_core import (
    parse_datetime,
    compute_common_free_windows,
    enumerate_candidates,
    intervals_overlap
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


def map_participant_names_to_ids(world: Dict, participants: List[str], instance_id: str) -> List[str]:
    """
    Map participant names to person_ids using people_table.
    
    Args:
        world: World data dict
        participants: List of participant names or person_ids
        instance_id: Instance ID for error messages
    
    Returns:
        List of person_ids
    """
    if "people_table" not in world["sources"]:
        raise ValueError(f"Level 3 requires world.sources.people_table, but it is missing for instance {instance_id}")
    
    people_table = world["sources"]["people_table"]
    
    # Handle columnar table format
    if "columns" in people_table and "rows" in people_table:
        # Columnar format: {columns: [...], rows: [{...}], primary_key: "person_id"}
        primary_key = people_table.get("primary_key", "person_id")
        name_col = "person_name"
        id_col = primary_key
        
        # Build name -> id mapping
        name_to_id = {}
        for row in people_table["rows"]:
            if name_col in row and id_col in row:
                name_to_id[row[name_col]] = row[id_col]
    else:
        # Assume array of {person_name, person_id} objects
        name_to_id = {}
        for person in people_table:
            if "person_name" in person and "person_id" in person:
                name_to_id[person["person_name"]] = person["person_id"]
    
    # Map participants
    person_ids = []
    for participant in participants:
        # If already a person_id (starts with "person_"), use directly
        if participant.startswith("person_"):
            person_ids.append(participant)
        else:
            # Try to map from name
            if participant in name_to_id:
                person_ids.append(name_to_id[participant])
            else:
                raise ValueError(f"Level 3: participant '{participant}' not found in people_table for instance {instance_id}")
    
    return person_ids


def gather_busy_intervals(world: Dict, person_ids: List[str], tz_str: str) -> List[Tuple]:
    """
    Gather all busy intervals for given person_ids.
    
    Args:
        world: World data dict
        person_ids: List of person IDs
        tz_str: Timezone string for parsing datetimes
    
    Returns:
        List of (start_datetime, end_datetime) tuples
    """
    busy_intervals = []
    calendar_json = world["sources"]["calendar_json"]
    
    for person_id in person_ids:
        if person_id not in calendar_json:
            continue
        
        for event in calendar_json[person_id]:
            start_dt = parse_datetime(event["start"], tz_str)
            end_dt = parse_datetime(event["end"], tz_str)
            busy_intervals.append((start_dt, end_dt))
    
    return busy_intervals


def filter_rooms_by_capacity(world: Dict, min_capacity: int, instance_id: str) -> List[str]:
    """
    Filter rooms by minimum capacity requirement.
    
    Args:
        world: World data dict
        min_capacity: Minimum required capacity
        instance_id: Instance ID for error messages
    
    Returns:
        List of room_ids that meet capacity requirement
    """
    if "rooms_table" not in world["sources"]:
        raise ValueError(f"Level 3 requires world.sources.rooms_table, but it is missing for instance {instance_id}")
    
    rooms_table = world["sources"]["rooms_table"]
    valid_room_ids = []
    
    # Handle columnar table format
    if "columns" in rooms_table and "rows" in rooms_table:
        # Columnar format: {columns: [...], rows: [{...}], primary_key: "room_id"}
        primary_key = rooms_table.get("primary_key", "room_id")
        capacity_col = "capacity"
        
        for row in rooms_table["rows"]:
            if primary_key not in row:
                continue
            if capacity_col not in row:
                raise ValueError(f"Level 3: room '{row.get(primary_key, 'unknown')}' missing capacity field for instance {instance_id}")
            
            capacity = row[capacity_col]
            if not isinstance(capacity, int):
                try:
                    capacity = int(capacity)
                except (ValueError, TypeError):
                    raise ValueError(f"Level 3: room '{row[primary_key]}' has invalid capacity '{capacity}' for instance {instance_id}")
            
            if capacity >= min_capacity:
                valid_room_ids.append(row[primary_key])
    else:
        # Assume array of {room_id, capacity, ...} objects
        for room in rooms_table:
            if "room_id" not in room:
                continue
            if "capacity" not in room:
                raise ValueError(f"Level 3: room '{room.get('room_id', 'unknown')}' missing capacity field for instance {instance_id}")
            
            capacity = room["capacity"]
            if not isinstance(capacity, int):
                try:
                    capacity = int(capacity)
                except (ValueError, TypeError):
                    raise ValueError(f"Level 3: room '{room['room_id']}' has invalid capacity '{capacity}' for instance {instance_id}")
            
            if capacity >= min_capacity:
                valid_room_ids.append(room["room_id"])
    
    return valid_room_ids


def join_room_availability(world: Dict, candidates: List[Dict[str, str]], valid_room_ids: List[str], tz_str: str, instance_id: str) -> List[Dict[str, str]]:
    """
    Join candidates with room availability to produce (start, end, room_id) candidates.
    
    Args:
        world: World data dict
        candidates: List of (start, end) candidate dicts
        valid_room_ids: List of room_ids that meet capacity requirement
        tz_str: Timezone string for parsing datetimes
        instance_id: Instance ID for error messages
    
    Returns:
        List of (start, end, room_id) candidate dicts
    """
    if "room_availability_json" not in world["sources"]:
        raise ValueError(f"Level 3 requires world.sources.room_availability_json, but it is missing for instance {instance_id}")
    
    room_availability = world["sources"]["room_availability_json"]
    
    room_candidates = []
    
    for candidate in candidates:
        candidate_start = parse_datetime(candidate["start"], tz_str)
        candidate_end = parse_datetime(candidate["end"], tz_str)
        
        for room_id in valid_room_ids:
            # Get busy intervals for this room
            room_busy = []
            if room_id in room_availability:
                for event in room_availability[room_id]:
                    busy_start = parse_datetime(event["start"], tz_str)
                    busy_end = parse_datetime(event["end"], tz_str)
                    room_busy.append((busy_start, busy_end))
            
            # Check if candidate overlaps any busy interval
            overlaps = False
            for busy_start, busy_end in room_busy:
                if intervals_overlap(candidate_start, candidate_end, busy_start, busy_end):
                    overlaps = True
                    break
            
            # If no overlap, this (candidate, room) is feasible
            if not overlaps:
                room_candidates.append({
                    "start": candidate["start"],
                    "end": candidate["end"],
                    "room_id": room_id
                })
    
    return room_candidates


def get_sort_spec(instance: Dict, instance_id: str) -> List[str]:
    """
    Extract sort_spec from task thread's thread_tags.
    
    Args:
        instance: Instance data dict
        instance_id: Instance ID for error messages
    
    Returns:
        List of sort keys (e.g., ["start", "end", "room_id"])
    """
    if "sources" not in instance or "comm_threads" not in instance["sources"]:
        # Default sort spec
        return ["start", "end", "room_id"]
    
    comm_threads = instance["sources"]["comm_threads"]
    
    # Find task thread (one with sort_spec in thread_tags)
    for thread in comm_threads:
        if "thread_tags" in thread and "sort_spec" in thread["thread_tags"]:
            sort_spec = thread["thread_tags"]["sort_spec"]
            if "keys" in sort_spec:
                return sort_spec["keys"]
    
    # Default if not found
    return ["start", "end", "room_id"]


def sort_candidates_level3(candidates: List[Dict[str, str]], sort_keys: List[str], tz_str: str) -> List[Dict[str, str]]:
    """
    Sort Level 3 candidates according to sort_spec.
    
    Args:
        candidates: List of candidate dicts with start, end, room_id
        sort_keys: List of keys to sort by (e.g., ["start", "end", "room_id"])
        tz_str: Timezone string for parsing datetimes
    
    Returns:
        Sorted list of candidates
    """
    def sort_key(candidate: Dict[str, str]) -> Tuple:
        key_parts = []
        for key in sort_keys:
            if key == "start" or key == "end":
                # Parse datetime for proper comparison
                dt = parse_datetime(candidate[key], tz_str)
                key_parts.append(dt)
            else:
                # Use string value directly (e.g., room_id)
                key_parts.append(candidate.get(key, ""))
        
        # Ensure deterministic total order: if all keys are equal, use full candidate as tie-break
        if len(key_parts) < len(sort_keys):
            # Pad with empty strings for missing keys
            while len(key_parts) < len(sort_keys):
                key_parts.append("")
        
        # Add full candidate dict as final tie-break for determinism
        return tuple(key_parts) + (candidate.get("start", ""), candidate.get("end", ""), candidate.get("room_id", ""))
    
    return sorted(candidates, key=sort_key)


def process_instance(world: Dict, instance: Dict, debug: bool = False) -> Tuple:
    """
    Process a single Level 3 instance and return oracle result.
    
    Args:
        world: World data dict
        instance: Instance data dict
        debug: If True, return debug info
    
    Returns:
        Tuple of (result_dict, debug_info) where:
        - result_dict: Dict with instance_id, feasible_candidates, explanation_keys, meta
          or None if instance should be discarded
        - debug_info: Dict with debug counts
    """
    instance_id = instance.get("instance_id", "unknown")
    tz_str = world.get("timezone", "Asia/Seoul")
    
    # Resolve slots
    slots = resolve_slots(3, world, instance)
    
    # Map participant names to person_ids if needed
    participants = slots["participants"]
    person_ids = map_participant_names_to_ids(world, participants, instance_id)
    
    # Create slots copy with person_ids for constraints (calendar_json keys are person_id)
    slots_for_constraints = dict(slots)
    slots_for_constraints["participants"] = person_ids
    
    # Gather busy intervals
    busy_intervals = gather_busy_intervals(world, person_ids, tz_str)
    
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
    
    # Apply constraints (policy + comm) - use slots_for_constraints with person_ids
    filtered_candidates = apply_constraints(3, world, slots_for_constraints, base_candidates, instance=instance)
    
    num_after_constraints = len(filtered_candidates)
    
    # Room join
    min_capacity = len(person_ids)
    valid_room_ids = filter_rooms_by_capacity(world, min_capacity, instance_id)
    
    room_candidates = join_room_availability(world, filtered_candidates, valid_room_ids, tz_str, instance_id)
    
    num_after_room_join = len(room_candidates)
    
    # Check if we have enough candidates
    num_options = slots["num_options"]  # Fixed to 3 for Level 3
    discarded = num_after_room_join < num_options
    
    debug_info = {
        "num_generated": num_generated,
        "num_after_constraints": num_after_constraints,
        "num_after_room_join": num_after_room_join,
        "num_options": num_options,
        "discarded": discarded
    }
    
    if discarded:
        return (None, debug_info)
    
    # Get sort spec
    sort_keys = get_sort_spec(instance, instance_id)
    
    # Sort candidates
    sorted_candidates = sort_candidates_level3(room_candidates, sort_keys, tz_str)
    
    # Select top N (fixed to 3 for Level 3)
    final_candidates = sorted_candidates[:num_options]
    
    # Build explanation_keys
    explanation_keys = [
        {"source": "calendar_json", "key": person_id}
        for person_id in person_ids
    ]
    explanation_keys.append({
        "source": "policy_tags",
        "key": slots["policy_id"]
    })
    
    # Add comm_thread_tags reference
    if "sources" in instance and "comm_threads" in instance["sources"]:
        for thread in instance["sources"]["comm_threads"]:
            if "thread_id" in thread and "thread_tags" in thread:
                explanation_keys.append({
                    "source": "comm_threads",
                    "key": thread["thread_id"]
                })
    
    explanation_keys.append({
        "source": "people_table",
        "key": "people_table"
    })
    explanation_keys.append({
        "source": "rooms_table",
        "key": "rooms_table"
    })
    explanation_keys.append({
        "source": "room_availability_json",
        "key": "room_availability_json"
    })
    explanation_keys.append({
        "source": "slots",
        "key": "time_window"
    })
    
    result = {
        "instance_id": instance_id,
        "feasible_candidates": final_candidates,
        "explanation_keys": explanation_keys,
        "meta": {
            "num_generated": num_generated,
            "num_after_constraints": num_after_constraints,
            "num_after_room_join": num_after_room_join,
            "num_options": num_options
        }
    }
    
    return (result, debug_info)


def run_level3_oracle(world_path: str, instances_path: str, output_path: str, debug: bool = False):
    """
    Run Level-3 oracle on test inputs.
    
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
            policy_id = instance.get("slots", {}).get("policy_id", "N/A")
            status = "DISCARDED" if debug_info["discarded"] else "OK"
            discard_reason = ""
            if debug_info["discarded"]:
                discard_reason = f" (discard: after_room_join={debug_info['num_after_room_join']} < num_options={debug_info['num_options']})"
            print(f"{instance['instance_id']} | Level 3 | {policy_id} | "
                  f"generated={debug_info['num_generated']} "
                  f"after_constraints={debug_info['num_after_constraints']} "
                  f"after_room_join={debug_info['num_after_room_join']} "
                  f"num_options={debug_info['num_options']} | {status}{discard_reason}")
        
        if result is not None:
            results.append(result)
    
    # Write output
    with open(output_path, 'w') as f:
        for result in results:
            f.write(json.dumps(result) + '\n')
    
    print(f"Processed {len(instances)} instances, wrote {len(results)} results to {output_path}")
