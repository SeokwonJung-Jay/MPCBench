"""Schema validator module."""

import json
from pathlib import Path
from typing import Dict, Any, Tuple, List

try:
    import jsonschema
except ImportError:
    jsonschema = None


def load_json(path: Path) -> Any:
    """
    Load JSON from a file and return the parsed object.
    Raise a clear exception if the file does not exist or JSON is invalid.
    """
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in {path}: {e}")


def validate_json(data: Any, schema: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Validate a Python object against a JSON schema.

    Returns:
        (is_valid, errors)

    - is_valid: True if validation passes, False otherwise.
    - errors: list of human-readable error messages.

    If jsonschema is not available, this function should not crash:
    - In that case, return (True, ["jsonschema library not installed; validation skipped"]).
    """
    if jsonschema is None:
        return (True, ["jsonschema library not installed; validation skipped"])
    
    try:
        # Use Draft7Validator to collect all errors
        validator = jsonschema.Draft7Validator(schema)
        errors = list(validator.iter_errors(data))
        
        if not errors:
            return (True, [])
        
        # Convert errors to readable strings
        error_messages = []
        for error in errors:
            # Format the error path
            path = ".".join(str(p) for p in error.path)
            if path:
                error_msg = f"at {path}: {error.message}"
            else:
                error_msg = f"at root: {error.message}"
            error_messages.append(error_msg)
        
        return (False, error_messages)
    
    except jsonschema.SchemaError as e:
        return (False, [f"Schema error: {e.message}"])
    except Exception as e:
        return (False, [f"Validation error: {str(e)}"])


def validate_company_a() -> Dict[str, Dict[str, Any]]:
    """
    Validate all Company A data files against their schemas.

    Returns a dict mapping logical names to a result dict:

    {
        "world_state": {"is_valid": bool, "errors": [...]},
        "slack": {"is_valid": bool, "errors": [...]},
        "calendar": {"is_valid": bool, "errors": [...]},
        "contacts": {"is_valid": bool, "errors": [...]},
        "gmail": {"is_valid": bool, "errors": [...]},
        "jira": {"is_valid": bool, "errors": [...]},
        "drive": {"is_valid": bool, "errors": [...]}
    }
    """
    # Define mappings: (data_file, schema_file, logical_name)
    # Updated to use scenario-based naming (scenario_A instead of company_A)
    mappings = [
        ("data/scenario_A_world_state.json", "schemas/world_state_schema.json", "world_state"),
        ("data/scenario_A_slack.json", "schemas/slack_schema.json", "slack"),
        ("data/scenario_A_calendar.json", "schemas/calendar_schema.json", "calendar"),
        ("data/scenario_A_contacts.json", "schemas/contacts_schema.json", "contacts"),
        ("data/scenario_A_gmail.json", "schemas/gmail_schema.json", "gmail"),
        ("data/scenario_A_jira.json", "schemas/jira_schema.json", "jira"),
        ("data/scenario_A_drive.json", "schemas/drive_schema.json", "drive"),
    ]
    
    results = {}
    
    for data_path_str, schema_path_str, name in mappings:
        data_path = Path(data_path_str)
        schema_path = Path(schema_path_str)
        
        try:
            # Load data and schema
            data = load_json(data_path)
            schema = load_json(schema_path)
            
            # Validate
            is_valid, errors = validate_json(data, schema)
            
            results[name] = {
                "is_valid": is_valid,
                "errors": errors
            }
        
        except FileNotFoundError as e:
            results[name] = {
                "is_valid": False,
                "errors": [str(e)]
            }
        except ValueError as e:
            results[name] = {
                "is_valid": False,
                "errors": [str(e)]
            }
        except Exception as e:
            results[name] = {
                "is_valid": False,
                "errors": [f"Unexpected error: {str(e)}"]
            }
    
    return results


def main() -> None:
    """CLI entry point for schema validation."""
    results = validate_company_a()
    
    print("Validation results for Company A:")
    for name, res in results.items():
        status = "OK" if res["is_valid"] else "FAIL"
        print(f"  {name}: {status}")
        if res["errors"]:
            for err in res["errors"]:
                print(f"    - {err}")


if __name__ == "__main__":
    main()

