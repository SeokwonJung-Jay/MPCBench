"""Agent runner for MPCBench v2.

Runs a single task by calling the LLM with tools and getting an answer.
"""

from typing import Dict, Any, Optional
from pathlib import Path
import json

from task_defs import Task
from tool_backend import ToolBackend


def run_task(
    task: Task,
    source_data: Dict[str, Path],
    agent_model: str = "gpt-4o-mini",
    output_path: Optional[Path] = None
) -> Dict[str, Any]:
    """
    Run a single task with an agent.
    
    Args:
        task: The task definition
        source_data: Dictionary mapping source names to file paths
        agent_model: Model name to use for the agent
        output_path: Optional path to save the run log
        
    Returns:
        Dictionary containing:
        - task_id: Task identifier
        - final_answer: Agent's final answer
        - rationale: Agent's explanation
        - tool_calls: List of tool calls made
    """
    # Initialize tool backend
    backend = ToolBackend(source_data)

    # TODO: Implement actual agent execution
    # 1. Load system prompt from prompt_config.json
    # 2. Call LLM with task_description and available tools
    # 3. Handle tool calls through backend
    # 4. Collect final answer and rationale
    # 5. Return structured result

    result = {
        "task_id": task.id,
        "final_answer": "",
        "rationale": "",
        "tool_calls": []
    }

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2)

    return result

