"""Oracle validator for MPCBench v2.

Validates consistency of generated source data against ground answers.
"""

import json
from typing import Dict, Any, List, Set
from pathlib import Path

from task_defs import Task, get_planning_meeting_slots


def validate_data_consistency(task: Task, source_data: Dict[str, Path]) -> List[str]:
    """
    Validate that generated source data is consistent with the task's ground answer.
    
    Args:
        task: The task definition
        source_data: Dictionary mapping source names to file paths
        
    Returns:
        List of validation errors (empty if valid)
    """
    errors = []

    if task.is_planning():
        # Planning tasks require calendar source
        if "calendar" not in source_data:
            errors.append(f"Missing calendar source for planning task {task.id}")
        else:
            # Load and validate calendar data
            calendar_path = source_data["calendar"]
            try:
                with open(calendar_path, 'r', encoding='utf-8') as f:
                    calendar_data = json.load(f)
                planning_errors = validate_planning_data(task, calendar_data)
                errors.extend(planning_errors)
            except Exception as e:
                errors.append(f"Failed to load calendar data for task {task.id}: {e}")
    elif task.is_document() or task.is_email_reply():
        # TODO: Implement validation for document and email_reply tasks
        pass

    return errors


def validate_planning_data(task: Task, calendar_data: Dict[str, Any]) -> List[str]:
    """
    Validate calendar data for a planning task.
    
    Derives participants from calendar data, not from hard-coded lists.
    """
    errors = []

    if not task.is_planning() or task.canonical_answer is None:
        return errors

    slots = get_planning_meeting_slots(task)
    if not slots:
        return errors

    # Get events from calendar data
    events = calendar_data.get("events", [])
    if not events:
        errors.append("Calendar data has no events")
        return errors

    # Check each canonical slot
    found_valid_slot = False
    for canonical_slot in slots:
        canonical_date = canonical_slot["date"]
        canonical_time = canonical_slot["slot"]
        
        # Find all events matching this canonical (date, slot)
        matching_events = [
            e for e in events
            if e.get("date") == canonical_date and e.get("slot") == canonical_time
        ]
        
        if not matching_events:
            # No events found for this slot
            continue
        
        # Derive participant set from events at this slot
        participant_emails: Set[str] = set()
        for event in matching_events:
            email = event.get("email")
            if email:
                participant_emails.add(email)
        
        if not participant_emails:
            # No participant emails found
            continue
        
        # Check if all participants are free at this slot
        all_free = True
        for email in participant_emails:
            # Find events for this participant at this slot
            participant_events = [
                e for e in matching_events
                if e.get("email") == email
            ]
            
            if not participant_events:
                # No event for this participant - assume not free
                all_free = False
                break
            
            # Check if any event is busy
            if any(e.get("busy", True) for e in participant_events):
                all_free = False
                break
        
        if all_free:
            found_valid_slot = True
            break
    
    if not found_valid_slot:
        errors.append("No canonical meeting slot is jointly free for all participants in calendar data.")

    return errors
