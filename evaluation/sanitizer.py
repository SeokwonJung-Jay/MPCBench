"""
Sanitizer module for MPCBench evaluation.

Removes oracle-only hint fields (_tags) from world/instance data
before passing to agents.
"""

import copy
import json
from typing import Any


def sanitize(data: dict) -> dict:
    """
    Remove all fields containing '_tags' in their key name from the input dict.
    
    Args:
        data: A world or instance dict that may contain oracle-only _tags fields.
        
    Returns:
        A deep copy of the input with all _tags fields removed recursively.
    """
    result = copy.deepcopy(data)
    _remove_tags_recursive(result)
    _validate_no_tags_remain(result)
    return result


def _remove_tags_recursive(obj: Any) -> None:
    """
    Recursively traverse and remove keys containing '_tags' from dicts.
    Modifies the object in place.
    """
    if isinstance(obj, dict):
        # Collect keys to remove (can't modify dict during iteration)
        keys_to_remove = [k for k in obj.keys() if '_tags' in k]
        for key in keys_to_remove:
            del obj[key]
        
        # Recurse into remaining values
        for value in obj.values():
            _remove_tags_recursive(value)
    
    elif isinstance(obj, list):
        # Recurse into list items
        for item in obj:
            _remove_tags_recursive(item)


def _validate_no_tags_remain(obj: dict) -> None:
    """
    Validate that the sanitized output does not contain 'tags' in any key name.
    
    Raises:
        AssertionError: If 'tags' is found in the JSON string dump.
    """
    json_str = json.dumps(obj)
    # Check for any key that looks like it contains 'tags'
    # We check for common patterns: "_tags", "tags":
    assert '"_tags"' not in json_str.lower(), \
        "Sanitization failed: '_tags' field still present in output"
    
    # Also check for standalone 'tags' keys (e.g., "thread_tags", "policy_tags")
    # by looking for the pattern "tags":
    _check_tags_keys_recursive(obj)


def _check_tags_keys_recursive(obj: Any) -> None:
    """
    Recursively check that no key contains 'tags' substring.
    
    Raises:
        AssertionError: If any key contains 'tags'.
    """
    if isinstance(obj, dict):
        for key in obj.keys():
            if 'tags' in key.lower():
                raise AssertionError(
                    f"Sanitization failed: key '{key}' contains 'tags'"
                )
        for value in obj.values():
            _check_tags_keys_recursive(value)
    
    elif isinstance(obj, list):
        for item in obj:
            _check_tags_keys_recursive(item)


def sanitize_world(world: dict) -> dict:
    """
    Sanitize a world dict by removing oracle-only _tags fields.
    
    Specifically removes:
    - policy_tags (Level 2/3)
    - Any other *_tags fields
    
    Args:
        world: The world dict from world_level*.json
        
    Returns:
        Sanitized world dict safe for agent consumption.
    """
    return sanitize(world)


def sanitize_instance(instance: dict) -> dict:
    """
    Sanitize an instance dict by removing oracle-only _tags fields.
    
    Specifically removes:
    - comm_tags (Level 2)
    - thread_tags within comm_threads (Level 3)
    - Any other *_tags fields
    
    Args:
        instance: The instance dict from instances_level*.jsonl
        
    Returns:
        Sanitized instance dict safe for agent consumption.
    """
    return sanitize(instance)
