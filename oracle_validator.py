"""Oracle validator for MPCBench v2.

Validates consistency of generated source data against ground answers.
"""

from typing import Dict, Any, List
from pathlib import Path

from task_defs import Task


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

    # TODO: Implement validation logic
    # For planning tasks, check that calendar data contains the slots in canonical_answer
    # For document tasks, check that relevant documents exist
    # For email_reply tasks, check that the email thread exists

    return errors


def validate_planning_data(task: Task, calendar_data: Dict[str, Any]) -> List[str]:
    """Validate calendar data for a planning task."""
    errors = []

    if not task.is_planning() or task.canonical_answer is None:
        return errors

    # TODO: Check that calendar data contains the meeting slots from canonical_answer
    # Verify that the dates and times in canonical_answer are actually free in the calendar

    return errors

