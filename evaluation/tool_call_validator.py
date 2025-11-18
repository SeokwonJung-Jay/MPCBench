"""Tool call validator module."""

import json
from pathlib import Path
from typing import Any, Dict, List


def load_json(path: Path) -> Any:
    """
    Load JSON from a file and return the parsed object.
    Raise a clear exception if the file does not exist or JSON is invalid.
    """
    if not path.exists():
        raise FileNotFoundError(f"JSON file not found: {path}")
    text = path.read_text(encoding="utf-8")
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in {path}: {e}") from e


def load_api_schemas() -> Dict[str, Dict[str, Any]]:
    """
    Return a mapping from tool_name to a simple argument schema.

    For now, we hard-code the tools used in the three tasks.
    Each schema has a dict:
      { "arguments": { arg_name: expected_type } }
    where expected_type is one of: "string", "integer", "array".
    """
    schemas: Dict[str, Dict[str, Any]] = {}

    # Slack
    schemas["Slack.search_messages"] = {
        "arguments": {
            "search_query": "string"
        }
    }

    # Contacts
    schemas["GoogleContacts.SearchContactsByName"] = {
        "arguments": {
            "name": "string",
            "limit": "integer"
        }
    }

    # Calendar
    schemas["GoogleCalendar.FindTimeSlotsWhenEveryoneIsFree"] = {
        "arguments": {
            "email_addresses": "array",
            "start_date": "string",
            "end_date": "string",
            "workday_start_time": "string",
            "workday_end_time": "string",
            "slot_minimum_minutes": "integer"
        }
    }

    schemas["GoogleCalendar.ListEvents"] = {
        "arguments": {
            "min_end_datetime": "string",
            "max_start_datetime": "string",
            "max_results": "integer"
        }
    }

    # Gmail
    schemas["Gmail.SearchThreads"] = {
        "arguments": {
            "subject": "string",
            "sender": "string",
            "date_range": "string",
            "max_results": "integer"
        }
    }

    schemas["Gmail.GetThread"] = {
        "arguments": {
            "thread_id": "string"
        }
    }

    # Drive
    schemas["GoogleDrive.gdrive_search"] = {
        "arguments": {
            "query": "string",
            "limit": "integer"
        }
    }

    schemas["GoogleDrive.gdrive_read_file"] = {
        "arguments": {
            "file_id": "string"
        }
    }

    # Jira
    schemas["Jira.SearchIssuesWithJql"] = {
        "arguments": {
            "jql": "string",
            "limit": "integer"
        }
    }

    return schemas


def _check_type(expected: str, value: Any) -> bool:
    """Check if value matches expected type."""
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int)
    if expected == "array":
        return isinstance(value, list)
    # Fallback: accept anything
    return True


def validate_tool_call(tool_call: Dict[str, Any],
                       api_schemas: Dict[str, Dict[str, Any]]) -> List[str]:
    """
    Validate a single tool_call dict against api_schemas.

    Returns a list of human-readable error messages (empty list if no errors).

    Checks:
    - tool_name exists and is known.
    - arguments is a dict.
    - All required arguments are present.
    - Argument types roughly match the expected primitive types.
    """
    errors: List[str] = []

    tool_name = tool_call.get("tool_name")
    if not isinstance(tool_name, str):
        errors.append("Missing or non-string 'tool_name'.")
        return errors

    if tool_name not in api_schemas:
        errors.append(f"Unknown tool_name: {tool_name}")
        return errors

    expected_args = api_schemas[tool_name].get("arguments", {})
    args = tool_call.get("arguments")
    if not isinstance(args, dict):
        errors.append(f"'arguments' must be an object/dict for tool {tool_name}.")
        return errors

    # Check required arguments exist and types
    for arg_name, expected_type in expected_args.items():
        if arg_name not in args:
            errors.append(f"Missing required argument '{arg_name}' for tool {tool_name}.")
            continue
        value = args[arg_name]
        if not _check_type(expected_type, value):
            errors.append(
                f"Argument '{arg_name}' for tool {tool_name} has wrong type; "
                f"expected {expected_type}, got {type(value).__name__}."
            )

    # Optionally: you can add a warning for unexpected extra keys, but do not treat as error for now.
    # For now, we ignore extra keys.

    return errors


def validate_trace(trace: Dict[str, Any],
                   api_schemas: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """
    Validate an entire trace object.

    Returns a summary dict:

    {
      "task_id": str or None,
      "num_calls": int,
      "num_calls_with_errors": int,
      "call_errors": [
        {
          "index": int,
          "tool_name": str or None,
          "errors": [str, ...]
        },
        ...
      ],
      "top_level_errors": [str, ...]
    }
    """
    summary: Dict[str, Any] = {
        "task_id": trace.get("task_id"),
        "num_calls": 0,
        "num_calls_with_errors": 0,
        "call_errors": [],
        "top_level_errors": [],
    }

    tool_calls = trace.get("tool_calls")
    if not isinstance(tool_calls, list):
        summary["top_level_errors"].append("'tool_calls' must be a list.")
        return summary

    summary["num_calls"] = len(tool_calls)

    for idx, call in enumerate(tool_calls):
        if not isinstance(call, dict):
            summary["num_calls_with_errors"] += 1
            summary["call_errors"].append(
                {
                    "index": idx,
                    "tool_name": None,
                    "errors": ["tool_call must be an object/dict"],
                }
            )
            continue

        tool_name = call.get("tool_name")
        errs = validate_tool_call(call, api_schemas)
        if errs:
            summary["num_calls_with_errors"] += 1
            summary["call_errors"].append(
                {
                    "index": idx,
                    "tool_name": tool_name if isinstance(tool_name, str) else None,
                    "errors": errs,
                }
            )

    return summary


def main() -> None:
    """CLI entry point for tool call validator."""
    api_schemas = load_api_schemas()
    example_path = Path("evaluation/examples/companyA_planning_example_trace.json")
    trace = load_json(example_path)
    summary = validate_trace(trace, api_schemas)

    print(f"Trace task_id: {summary.get('task_id')}")
    print(f"Total tool calls: {summary.get('num_calls')}")
    print(f"Calls with errors: {summary.get('num_calls_with_errors')}")

    top_level = summary.get("top_level_errors") or []
    if top_level:
        print("\nTop-level errors:")
        for err in top_level:
            print(f"  - {err}")

    call_errors = summary.get("call_errors") or []
    if call_errors:
        print("\nPer-call errors:")
        for ce in call_errors:
            idx = ce.get("index")
            tool_name = ce.get("tool_name")
            print(f"  - Call #{idx} ({tool_name}):")
            for err in ce.get("errors", []):
                print(f"      - {err}")
    else:
        if not top_level:
            print("\nNo tool-call errors detected.")


if __name__ == "__main__":
    main()
