"""Task definition loading and validation for MPCBench v2."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Any

from config import TASKS_DIR


@dataclass
class Task:
    """Represents a single task instance."""
    id: str
    category: str
    task_description: str
    canonical_answer: Optional[Dict[str, Any]]
    metadata: Dict[str, int]
    current_date: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Task":
        """Create a Task from a dictionary."""
        return cls(
            id=data["id"],
            category=data["category"],
            task_description=data["task_description"],
            canonical_answer=data.get("canonical_answer"),
            metadata=data["metadata"],
            current_date=data.get("current_date")
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert Task to dictionary."""
        result = {
            "id": self.id,
            "category": self.category,
            "task_description": self.task_description,
            "canonical_answer": self.canonical_answer,
            "metadata": self.metadata
        }
        if self.current_date:
            result["current_date"] = self.current_date
        return result

    def is_planning(self) -> bool:
        """Check if task is a planning task."""
        return self.category == "planning"

    def is_document(self) -> bool:
        """Check if task is a document task."""
        return self.category == "document"

    def is_email_reply(self) -> bool:
        """Check if task is an email reply task."""
        return self.category == "email_reply"


def load_task(task_path: Path) -> Task:
    """Load a single task from a JSON file."""
    with open(task_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return Task.from_dict(data)


def load_all_tasks() -> List[Task]:
    """Load all tasks from the tasks directory."""
    tasks = []
    for task_file in TASKS_DIR.glob("*.json"):
        try:
            task = load_task(task_file)
            tasks.append(task)
        except Exception as e:
            print(f"Warning: Failed to load {task_file}: {e}")
    return tasks


def validate_task(task: Task) -> List[str]:
    """Validate a task and return list of errors (empty if valid)."""
    errors = []

    # Required fields
    if not task.id:
        errors.append("Task id is required")
    if not task.category:
        errors.append("Task category is required")
    if not task.task_description:
        errors.append("Task description is required")
    if not task.metadata:
        errors.append("Task metadata is required")

    # Category validation
    valid_categories = {"planning", "document", "email_reply"}
    if task.category not in valid_categories:
        errors.append(f"Invalid category: {task.category}. Must be one of {valid_categories}")

    # Metadata validation
    required_metadata_fields = ["min_required_source", "fragmentation_depth", 
                                "indirection_depth", "noise_level"]
    for field in required_metadata_fields:
        if field not in task.metadata:
            errors.append(f"Missing metadata field: {field}")
        elif not isinstance(task.metadata[field], int):
            errors.append(f"Metadata field '{field}' must be an integer, got {type(task.metadata[field]).__name__}")

    # Planning task canonical_answer validation
    if task.is_planning():
        if task.canonical_answer is None:
            errors.append("Planning tasks must have a canonical_answer")
        else:
            if "meeting_slots" not in task.canonical_answer:
                errors.append("Planning canonical_answer must have 'meeting_slots' field")
            else:
                slots = task.canonical_answer["meeting_slots"]
                if not isinstance(slots, list):
                    errors.append("meeting_slots must be a list")
                else:
                    for i, slot in enumerate(slots):
                        if not isinstance(slot, dict):
                            errors.append(f"meeting_slots[{i}] must be a dict")
                        else:
                            if "date" not in slot:
                                errors.append(f"meeting_slots[{i}] must have 'date' field")
                            if "slot" not in slot:
                                errors.append(f"meeting_slots[{i}] must have 'slot' field")
                            # Validate date format (YYYY-MM-DD)
                            if "date" in slot and not isinstance(slot["date"], str):
                                errors.append(f"meeting_slots[{i}].date must be a string")
                            # Validate slot format (HH:MM-HH:MM)
                            if "slot" in slot and not isinstance(slot["slot"], str):
                                errors.append(f"meeting_slots[{i}].slot must be a string")

    return errors


def is_planning(task: Task) -> bool:
    """Helper predicate: is this a planning task?"""
    return task.is_planning()


def is_document(task: Task) -> bool:
    """Helper predicate: is this a document task?"""
    return task.is_document()


def is_email_reply(task: Task) -> bool:
    """Helper predicate: is this an email reply task?"""
    return task.is_email_reply()


def get_planning_meeting_slots(task: Task) -> List[Dict[str, str]]:
    """
    Extract meeting slots from a planning task's canonical_answer.
    
    Args:
        task: The task to extract slots from
        
    Returns:
        List of dicts with "date" and "slot" keys (strings).
        Returns empty list if task is not planning or canonical_answer is None/malformed.
        
    Raises:
        ValueError: If canonical_answer structure is malformed (should be caught by validate_task)
    """
    if task.category != "planning":
        return []
    
    if task.canonical_answer is None:
        return []
    
    if "meeting_slots" not in task.canonical_answer:
        raise ValueError("Planning task canonical_answer must have 'meeting_slots' field")
    
    slots = task.canonical_answer["meeting_slots"]
    if not isinstance(slots, list):
        raise ValueError("meeting_slots must be a list")
    
    result = []
    for slot in slots:
        if not isinstance(slot, dict):
            raise ValueError("Each meeting_slots entry must be a dict")
        if "date" not in slot or "slot" not in slot:
            raise ValueError("Each meeting_slots entry must have 'date' and 'slot' fields")
        result.append({
            "date": str(slot["date"]),
            "slot": str(slot["slot"])
        })
    
    return result

