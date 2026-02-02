"""
Apply constraints to filter candidates.
Explicit boundary for constraint application logic.
"""

from datetime import datetime, timedelta
from typing import List, Dict
import sys
from pathlib import Path

# Add repo root to path for imports
repo_root = Path(__file__).parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from oracle.oracle_core import parse_datetime, intervals_overlap, build_daily_interval, dt_in_days_of_week


def apply_constraints(level: int, world: Dict, slots: Dict, candidates: List[Dict[str, str]], instance: Dict = None) -> List[Dict[str, str]]:
    """
    Apply constraints to filter candidates.
    
    Args:
        level: Difficulty level (1, 2, or 3)
        world: World data dict
        slots: Resolved slot requirements
        candidates: List of candidate dicts with "start" and "end" keys
        instance: Instance data dict (required for Level 2)
    
    Returns:
        Filtered list of candidates
    """
    if level == 1:
        return apply_level1_constraints(world, slots, candidates)
    elif level == 2:
        if instance is None:
            raise ValueError("instance parameter required for Level 2")
        return apply_level2_constraints(world, slots, candidates, instance)
    elif level == 3:
        if instance is None:
            raise ValueError("instance parameter required for Level 3")
        return apply_level3_constraints(world, slots, candidates, instance)
    else:
        raise ValueError(f"Unknown level: {level}")


def apply_level1_constraints(world: Dict, slots: Dict, candidates: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """Apply Level 1 policy constraints."""
    policy_id = slots["policy_id"]
    policy_rules = world["sources"]["policy_json"][policy_id]["rules"]
    tz_str = world.get("timezone", "Asia/Seoul")
    
    filtered = candidates
    
    for rule in policy_rules:
        rule_type = rule["type"]
        
        if rule_type == "work_hours":
            filtered = filter_work_hours(filtered, rule, tz_str)
        elif rule_type == "lunch_block":
            filtered = filter_lunch_block(filtered, rule, tz_str)
        elif rule_type == "buffer_min":
            filtered = filter_buffer_min(filtered, rule, world, slots)
        elif rule_type == "ban_dow_time":
            filtered = filter_ban_dow_time(filtered, rule, tz_str)
        else:
            raise ValueError(f"Unknown rule type: {rule_type}")
    
    return filtered


def filter_work_hours(candidates: List[Dict[str, str]], rule: Dict, tz_str: str) -> List[Dict[str, str]]:
    """Filter candidates to only include work hours, optionally restricted to specific weekdays."""
    work_start_str = rule["start"]  # e.g., "09:00"
    work_end_str = rule["end"]      # e.g., "18:00"
    days_of_week = rule.get("days_of_week")  # Optional: [0,1,2,3,4] for Mon-Fri
    
    filtered = []
    for candidate in candidates:
        # Parse with timezone awareness (explicit tz_str)
        start_dt = parse_datetime(candidate["start"], tz_str)
        end_dt = parse_datetime(candidate["end"], tz_str)
        
        # Check weekday restriction if specified
        if days_of_week is not None:
            if not dt_in_days_of_week(start_dt, days_of_week):
                continue  # Skip candidates not on allowed weekdays
        
        # Build work interval on candidate's start date
        work_start_dt, work_end_dt = build_daily_interval(start_dt, work_start_str, work_end_str, tz_str)
        
        # Keep candidate ONLY if fully contained in work interval
        if start_dt >= work_start_dt and end_dt <= work_end_dt:
            filtered.append(candidate)
    
    return filtered


def filter_lunch_block(candidates: List[Dict[str, str]], rule: Dict, tz_str: str) -> List[Dict[str, str]]:
    """Filter out candidates that overlap lunch block, optionally restricted to specific weekdays."""
    lunch_start_str = rule["start"]  # e.g., "12:00"
    lunch_end_str = rule["end"]      # e.g., "13:00"
    days_of_week = rule.get("days_of_week")  # Optional: [0,1,2,3,4] for Mon-Fri
    
    filtered = []
    for candidate in candidates:
        # Parse with timezone awareness (explicit tz_str)
        start_dt = parse_datetime(candidate["start"], tz_str)
        end_dt = parse_datetime(candidate["end"], tz_str)
        
        # Check weekday restriction if specified
        if days_of_week is not None:
            if not dt_in_days_of_week(start_dt, days_of_week):
                # If not on restricted weekday, allow candidate (lunch block doesn't apply)
                filtered.append(candidate)
                continue
        
        # Build lunch interval on candidate's start date
        lunch_start_dt, lunch_end_dt = build_daily_interval(start_dt, lunch_start_str, lunch_end_str, tz_str)
        
        # Discard candidate if it overlaps lunch interval
        if intervals_overlap(start_dt, end_dt, lunch_start_dt, lunch_end_dt):
            continue  # Skip this candidate
        
        filtered.append(candidate)
    
    return filtered


def filter_buffer_min(candidates: List[Dict[str, str]], rule: Dict, world: Dict, slots: Dict) -> List[Dict[str, str]]:
    """
    Filter candidates that violate buffer_min constraint.
    Buffer is enforced against ANY busy event: expand ALL busy intervals by ±buffer_minutes
    and filter out candidates that overlap any expanded busy interval.
    """
    buffer_minutes = rule["minutes"]
    participants = slots["participants"]
    tz_str = world.get("timezone", "Asia/Seoul")
    
    # Collect all busy intervals for participants, expanded by buffer
    expanded_busy = []
    calendar_json = world["sources"]["calendar_json"]
    
    for person_id in participants:
        if person_id not in calendar_json:
            continue
        
        for event in calendar_json[person_id]:
            busy_start = parse_datetime(event["start"], tz_str)
            busy_end = parse_datetime(event["end"], tz_str)
            
            # Expand by buffer
            expanded_start = busy_start - timedelta(minutes=buffer_minutes)
            expanded_end = busy_end + timedelta(minutes=buffer_minutes)
            
            expanded_busy.append((expanded_start, expanded_end))
    
    # Filter candidates that don't overlap expanded busy intervals
    filtered = []
    for candidate in candidates:
        candidate_start = parse_datetime(candidate["start"], tz_str)
        candidate_end = parse_datetime(candidate["end"], tz_str)
        
        # Check if candidate overlaps any expanded busy interval
        overlaps = False
        for busy_start, busy_end in expanded_busy:
            if intervals_overlap(candidate_start, candidate_end, busy_start, busy_end):
                overlaps = True
                break
        
        if not overlaps:
            filtered.append(candidate)
    
    return filtered


def filter_ban_dow_time(candidates: List[Dict[str, str]], rule: Dict, tz_str: str) -> List[Dict[str, str]]:
    """Filter out candidates that fall within banned day-of-week time windows."""
    day_of_week = rule["day_of_week"]  # 0=Monday, 4=Friday
    ban_start_str = rule["start"]       # e.g., "09:00"
    ban_end_str = rule["end"]           # e.g., "12:00"
    
    filtered = []
    for candidate in candidates:
        # Parse with timezone awareness (explicit tz_str)
        start_dt = parse_datetime(candidate["start"], tz_str)
        end_dt = parse_datetime(candidate["end"], tz_str)
        
        # Check if candidate falls on the banned day
        if start_dt.weekday() == day_of_week:
            # Build ban interval on candidate's start date
            ban_start_dt, ban_end_dt = build_daily_interval(start_dt, ban_start_str, ban_end_str, tz_str)
            
            # Discard candidate if it overlaps ban window
            if intervals_overlap(start_dt, end_dt, ban_start_dt, ban_end_dt):
                continue  # Skip this candidate
        
        filtered.append(candidate)
    
    return filtered


def apply_level2_constraints(world: Dict, slots: Dict, candidates: List[Dict[str, str]], instance: Dict) -> List[Dict[str, str]]:
    """Apply Level 2 policy and communication constraints."""
    tz_str = world.get("timezone", "Asia/Seoul")
    
    filtered = candidates
    
    # Step 1: Apply policy constraints from policy_tags
    # Structure: world.sources.policy_tags[policy_id].rules = [...]
    policy_id = slots["policy_id"]
    instance_id = instance.get("instance_id", "unknown")
    
    if "policy_tags" not in world["sources"]:
        raise ValueError(f"Level 2 requires world.sources.policy_tags, but it is missing for instance {instance_id}")
    
    policy_tags = world["sources"]["policy_tags"]
    
    if policy_id not in policy_tags:
        raise ValueError(f"Level 2 requires policy_id '{policy_id}' in world.sources.policy_tags, but it is missing for instance {instance_id}")
    
    policy_rules = policy_tags[policy_id]["rules"]
    
    # Apply policy rules (same types as Level 1)
    for rule in policy_rules:
        rule_type = rule["type"]
        
        if rule_type == "work_hours":
            filtered = filter_work_hours(filtered, rule, tz_str)
        elif rule_type == "lunch_block":
            filtered = filter_lunch_block(filtered, rule, tz_str)
        elif rule_type == "buffer_min":
            filtered = filter_buffer_min(filtered, rule, world, slots)
        elif rule_type == "ban_dow_time":
            filtered = filter_ban_dow_time(filtered, rule, tz_str)
        else:
            raise ValueError(f"Unknown rule type: {rule_type}")
    
    # Step 2: Apply communication constraints from comm_tags
    # Must read from instance.sources.comm_tags (strict path)
    if "sources" not in instance:
        raise ValueError(f"Level 2 requires instance.sources, but it is missing for instance {instance_id}")
    
    if "comm_tags" not in instance["sources"]:
        raise ValueError(f"Level 2 requires instance.sources.comm_tags, but it is missing for instance {instance_id}")
    
    comm_tags = instance["sources"]["comm_tags"]
    
    if "deadline" in comm_tags:
        filtered = filter_deadline(filtered, comm_tags["deadline"], tz_str)
    
    if "ban_windows" in comm_tags:
        ban_windows = comm_tags["ban_windows"]
        if not isinstance(ban_windows, list):
            raise ValueError(f"Level 2 comm_tags.ban_windows must be a list for instance {instance_id}")
        filtered = filter_ban_windows(filtered, ban_windows, tz_str)
    
    if "required_windows" in comm_tags:
        required_windows = comm_tags["required_windows"]
        if not isinstance(required_windows, list):
            raise ValueError(f"Level 2 comm_tags.required_windows must be a list for instance {instance_id}")
        filtered = filter_required_windows(filtered, required_windows, tz_str)
    
    return filtered


def filter_deadline(candidates: List[Dict[str, str]], deadline_str: str, tz_str: str) -> List[Dict[str, str]]:
    """Filter candidates: start must be <= deadline."""
    deadline_dt = parse_datetime(deadline_str, tz_str)
    
    filtered = []
    for candidate in candidates:
        start_dt = parse_datetime(candidate["start"], tz_str)
        if start_dt <= deadline_dt:
            filtered.append(candidate)
    
    return filtered


def filter_ban_windows(candidates: List[Dict[str, str]], ban_windows: List[Dict], tz_str: str) -> List[Dict[str, str]]:
    """Filter out candidates that overlap any ban window."""
    # ban_windows is a list of {"start": "...", "end": "..."} dicts
    ban_intervals = []
    for ban_window in ban_windows:
        ban_start = parse_datetime(ban_window["start"], tz_str)
        ban_end = parse_datetime(ban_window["end"], tz_str)
        ban_intervals.append((ban_start, ban_end))
    
    filtered = []
    for candidate in candidates:
        candidate_start = parse_datetime(candidate["start"], tz_str)
        candidate_end = parse_datetime(candidate["end"], tz_str)
        
        # Check if candidate overlaps any ban window
        overlaps_any = False
        for ban_start, ban_end in ban_intervals:
            if intervals_overlap(candidate_start, candidate_end, ban_start, ban_end):
                overlaps_any = True
                break
        
        if not overlaps_any:
            filtered.append(candidate)
    
    return filtered


def filter_required_windows(candidates: List[Dict[str, str]], required_windows: List[Dict], tz_str: str) -> List[Dict[str, str]]:
    """
    Filter candidates: candidate must be fully contained in at least one required window.
    OR logic: candidate must be contained in one of the windows.
    """
    # required_windows is a list of {"start": "...", "end": "..."} dicts
    required_intervals = []
    for req_window in required_windows:
        req_start = parse_datetime(req_window["start"], tz_str)
        req_end = parse_datetime(req_window["end"], tz_str)
        required_intervals.append((req_start, req_end))
    
    filtered = []
    for candidate in candidates:
        candidate_start = parse_datetime(candidate["start"], tz_str)
        candidate_end = parse_datetime(candidate["end"], tz_str)
        
        # Check if candidate is fully contained in at least one required window
        contained_in_any = False
        for req_start, req_end in required_intervals:
            if candidate_start >= req_start and candidate_end <= req_end:
                contained_in_any = True
                break
        
        if contained_in_any:
            filtered.append(candidate)
    
    return filtered


def apply_level3_constraints(world: Dict, slots: Dict, candidates: List[Dict[str, str]], instance: Dict) -> List[Dict[str, str]]:
    """
    Apply Level 3 policy and communication constraints.
    Note: Room join is handled separately in level3_oracle.py after constraints.
    """
    tz_str = world.get("timezone", "Asia/Seoul")
    
    filtered = candidates
    
    # Step 1: Apply policy constraints from policy_tags (same as Level 2)
    policy_id = slots["policy_id"]
    instance_id = instance.get("instance_id", "unknown")
    
    if "policy_tags" not in world["sources"]:
        raise ValueError(f"Level 3 requires world.sources.policy_tags, but it is missing for instance {instance_id}")
    
    policy_tags = world["sources"]["policy_tags"]
    
    if policy_id not in policy_tags:
        raise ValueError(f"Level 3 requires policy_id '{policy_id}' in world.sources.policy_tags, but it is missing for instance {instance_id}")
    
    policy_rules = policy_tags[policy_id]["rules"]
    
    # Apply policy rules (same types as Level 1/2)
    for rule in policy_rules:
        rule_type = rule["type"]
        
        if rule_type == "work_hours":
            filtered = filter_work_hours(filtered, rule, tz_str)
        elif rule_type == "lunch_block":
            filtered = filter_lunch_block(filtered, rule, tz_str)
        elif rule_type == "buffer_min":
            filtered = filter_buffer_min(filtered, rule, world, slots)
        elif rule_type == "ban_dow_time":
            filtered = filter_ban_dow_time(filtered, rule, tz_str)
        else:
            raise ValueError(f"Unknown rule type: {rule_type}")
    
    # Step 2: Apply communication constraints from comm_threads[*].thread_tags
    # Level 3 uses comm_threads list, not comm_tags
    if "sources" not in instance:
        raise ValueError(f"Level 3 requires instance.sources, but it is missing for instance {instance_id}")
    
    if "comm_threads" not in instance["sources"]:
        # Comm constraints are optional for Level 3
        return filtered
    
    comm_threads = instance["sources"]["comm_threads"]
    
    # Apply constraints from all threads' thread_tags
    for thread in comm_threads:
        if "thread_tags" not in thread:
            continue
        
        thread_tags = thread["thread_tags"]
        
        # Apply deadline if present
        if "deadline" in thread_tags:
            filtered = filter_deadline(filtered, thread_tags["deadline"], tz_str)
        
        # Apply ban_windows if present
        if "ban_windows" in thread_tags:
            ban_windows = thread_tags["ban_windows"]
            if isinstance(ban_windows, list):
                filtered = filter_ban_windows(filtered, ban_windows, tz_str)
        
        # Apply required_windows if present
        if "required_windows" in thread_tags:
            required_windows = thread_tags["required_windows"]
            if isinstance(required_windows, list):
                filtered = filter_required_windows(filtered, required_windows, tz_str)
    
    return filtered
