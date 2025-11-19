"""Utilities for logging LLM conversations to files."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict


def log_llm_run(log_dir: Path, file_name: str, payload: Dict[str, Any]) -> None:
    """
    Log an LLM run to a JSON file.
    
    Creates the directory if needed and writes the payload as pretty-printed UTF-8 JSON.
    Best-effort: if logging fails, the error is silently ignored to not break the run.
    
    Args:
        log_dir: Directory where the log file should be written
        file_name: Name of the log file (should include .json extension)
        payload: Dictionary to write as JSON
    """
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / file_name
        
        with open(log_path, 'w', encoding='utf-8') as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
    except Exception as e:
        # Silently ignore logging errors to not break the run
        import sys
        print(f"[log_llm_run] Warning: Failed to log LLM run to {log_dir / file_name}: {e}", file=sys.stderr)


def build_llm_log_payload(
    model: str,
    component: str,
    messages: list,
    response: Any,
    scenario_id: str = None,
    task_id: str = None,
    step_index: int = None,
    tools: list = None,
    tool_choice: str = None,
    extra_params: Dict[str, Any] = None,
) -> Dict[str, Any]:
    """
    Build a standardized payload for LLM logging.
    
    Args:
        model: Model name used
        component: Component name (e.g., "agent", "judge", "world_state_generator")
        messages: Full messages list passed to the LLM
        response: Response object from OpenAI API
        scenario_id: Scenario ID if available
        task_id: Task ID if available
        step_index: Step index for multi-step runs (e.g., agent with tool calls)
        tools: Tools list if any
        tool_choice: Tool choice parameter if any
        extra_params: Additional parameters (temperature, etc.)
        
    Returns:
        Dictionary ready to be logged
    """
    # Extract response data
    response_data = {}
    if hasattr(response, 'choices') and len(response.choices) > 0:
        msg = response.choices[0].message
        # Convert message to dict format
        response_data["raw_message"] = {
            "role": msg.role if hasattr(msg, 'role') else None,
            "content": msg.content if hasattr(msg, 'content') else None,
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": tc.type,
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments
                    }
                } for tc in (msg.tool_calls or [])
            ] if hasattr(msg, 'tool_calls') and msg.tool_calls else None,
        }
    
    if hasattr(response, 'usage'):
        response_data["usage"] = {
            "prompt_tokens": response.usage.prompt_tokens if hasattr(response.usage, 'prompt_tokens') else None,
            "completion_tokens": response.usage.completion_tokens if hasattr(response.usage, 'completion_tokens') else None,
            "total_tokens": response.usage.total_tokens if hasattr(response.usage, 'total_tokens') else None,
        }
    
    # Build context
    context: Dict[str, Any] = {
        "component": component,
        "timestamp": datetime.now().isoformat(),
    }
    if scenario_id:
        context["scenario_id"] = scenario_id
    if task_id:
        context["task_id"] = task_id
    if step_index is not None:
        context["step_index"] = step_index
    
    # Build request
    request: Dict[str, Any] = {
        "messages": messages,
    }
    if tools:
        request["tools"] = tools
    if tool_choice:
        request["tool_choice"] = tool_choice
    if extra_params:
        request["extra_params"] = extra_params
    
    payload = {
        "model": model,
        "context": context,
        "request": request,
        "response": response_data,
    }
    
    return payload

