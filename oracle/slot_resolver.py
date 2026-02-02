"""
Resolve problem slots from world and instance data.
Explicit boundary for extracting slot requirements.
"""

from typing import Dict


def resolve_slots(level: int, world: Dict, instance: Dict) -> Dict:
    """
    Extract slot requirements from world and instance.
    
    Args:
        level: Difficulty level (1, 2, or 3)
        world: World data dict
        instance: Instance data dict
    
    Returns:
        Dict with slot requirements (participants, time_window, duration_min, etc.)
    """
    if level == 1:
        slots = instance["slots"]
        return {
            "participants": slots["participants"],
            "time_window": slots["time_window"],
            "duration_min": slots["duration_min"],
            "num_options": slots["num_options"],
            "policy_id": slots["policy_id"]
        }
    elif level == 2:
        # Level 2 uses instance.slots directly (same as Level 1)
        # Comm constraints come from instance.sources.comm_tags, not from slots
        slots = instance["slots"]
        policy_id = slots.get("policy_id")
        
        # policy_id is REQUIRED for Level 2
        if not policy_id:
            instance_id = instance.get("instance_id", "unknown")
            raise ValueError(f"Level 2 requires policy_id in slots, but it is missing or empty for instance {instance_id}")
        
        return {
            "participants": slots["participants"],
            "time_window": slots["time_window"],
            "duration_min": slots["duration_min"],
            "num_options": slots["num_options"],
            "policy_id": policy_id
        }
    elif level == 3:
        # Level 3 uses instance.slots similar to Level 2
        # num_options is fixed to 3 for Level 3
        slots = instance["slots"]
        policy_id = slots.get("policy_id")
        
        # policy_id is REQUIRED for Level 3
        if not policy_id:
            instance_id = instance.get("instance_id", "unknown")
            raise ValueError(f"Level 3 requires policy_id in slots, but it is missing or empty for instance {instance_id}")
        
        return {
            "participants": slots["participants"],  # May be names or person_ids
            "time_window": slots["time_window"],
            "duration_min": slots["duration_min"],
            "num_options": 3,  # Fixed to 3 for Level 3
            "policy_id": policy_id
        }
    else:
        raise ValueError(f"Unknown level: {level}")
