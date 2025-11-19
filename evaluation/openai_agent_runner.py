"""OpenAI agent runner for tool-using tasks."""

import json
import os
from pathlib import Path
from typing import Any, Dict, List

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

from evaluation.tool_backend import ToolBackend


def load_env_file(env_path: Path = None) -> None:
    """
    Load environment variables from .env file.
    
    Args:
        env_path: Path to .env file. If None, looks for .env in project root.
    """
    if env_path is None:
        # Find project root (parent of evaluation directory)
        project_root = Path(__file__).resolve().parent.parent
        env_path = project_root / ".env"
    
    if not env_path.exists():
        return
    
    with open(env_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            # Skip empty lines and comments
            if not line or line.startswith('#'):
                continue
            
            # Parse KEY=VALUE format
            if '=' in line:
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip()
                # Remove quotes if present
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]
                elif value.startswith("'") and value.endswith("'"):
                    value = value[1:-1]
                
                # Only set if not already in environment
                if key and key not in os.environ:
                    os.environ[key] = value


def read_text_if_exists(path: Path) -> str:
    """
    Read text file if it exists, otherwise return empty string.
    
    Args:
        path: Path to the text file
        
    Returns:
        File contents as string, or empty string if file doesn't exist
    """
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def build_all_tools_spec() -> List[Dict[str, Any]]:
    """
    Return a unified list of all function tools the agent can use.
    
    Returns:
        List of function tool definitions in OpenAI Chat Completions format
    """
    tools: List[Dict[str, Any]] = []
    
    # 1) Slack.search_messages
    tools.append(
        {
            "type": "function",
            "function": {
                "name": "Slack_search_messages",
                "description": "Search Slack messages in the company workspace.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "search_query": {
                            "type": "string",
                            "description": "Search query string used to find relevant messages.",
                        }
                    },
                    "required": ["search_query"],
                },
            },
        }
    )
    
    # 2) GoogleContacts.SearchContactsByName
    tools.append(
        {
            "type": "function",
            "function": {
                "name": "GoogleContacts_SearchContactsByName",
                "description": "Search contacts by name.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Full name or partial name of the contact.",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of contacts to return.",
                        },
                    },
                    "required": ["name"],
                },
            },
        }
    )
    
    # 3) GoogleCalendar.FindTimeSlotsWhenEveryoneIsFree
    tools.append(
        {
            "type": "function",
            "function": {
                "name": "GoogleCalendar_FindTimeSlotsWhenEveryoneIsFree",
                "description": "Find time slots when everyone is free within a date range and workday hours.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "email_addresses": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Email addresses of participants.",
                        },
                        "start_date": {"type": "string"},
                        "end_date": {"type": "string"},
                        "workday_start_time": {"type": "string"},
                        "workday_end_time": {"type": "string"},
                        "slot_minimum_minutes": {"type": "integer"},
                    },
                    "required": ["email_addresses"],
                },
            },
        }
    )
    
    # 4) GoogleCalendar.ListEvents
    tools.append(
        {
            "type": "function",
            "function": {
                "name": "GoogleCalendar_ListEvents",
                "description": "List calendar events within a time window for weekly reporting or summaries.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "min_end_datetime": {
                            "type": "string",
                            "description": "Minimum event end datetime (ISO string), inclusive or null.",
                        },
                        "max_start_datetime": {
                            "type": "string",
                            "description": "Maximum event start datetime (ISO string), exclusive or null.",
                        },
                        "max_results": {
                            "type": "integer",
                            "description": "Maximum number of events to return.",
                        },
                    },
                    "required": [],
                },
            },
        }
    )
    
    # 5) Gmail.SearchThreads
    tools.append(
        {
            "type": "function",
            "function": {
                "name": "Gmail_SearchThreads",
                "description": "Search Gmail threads by subject, sender, and date range.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "subject": {"type": "string"},
                        "sender": {"type": "string"},
                        "date_range": {"type": "string"},
                        "max_results": {"type": "integer"},
                    },
                    "required": [],
                },
            },
        }
    )
    
    # 6) Gmail.GetThread
    tools.append(
        {
            "type": "function",
            "function": {
                "name": "Gmail_GetThread",
                "description": "Get a full Gmail thread by thread ID.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "thread_id": {"type": "string"},
                    },
                    "required": ["thread_id"],
                },
            },
        }
    )
    
    # 7) GoogleDrive.gdrive_search
    tools.append(
        {
            "type": "function",
            "function": {
                "name": "GoogleDrive_gdrive_search",
                "description": "Search Google Drive files by name or keywords.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "limit": {"type": "integer"},
                    },
                    "required": ["query"],
                },
            },
        }
    )
    
    # 8) GoogleDrive.gdrive_read_file
    tools.append(
        {
            "type": "function",
            "function": {
                "name": "GoogleDrive_gdrive_read_file",
                "description": "Read the content of a Google Drive file by file ID.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_id": {"type": "string"},
                    },
                    "required": ["file_id"],
                },
            },
        }
    )
    
    # 9) Jira.SearchIssuesWithJql
    tools.append(
        {
            "type": "function",
            "function": {
                "name": "Jira_SearchIssuesWithJql",
                "description": "Search Jira issues using JQL (Jira Query Language).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "jql": {"type": "string"},
                        "limit": {"type": "integer"},
                    },
                    "required": ["jql"],
                },
            },
        }
    )
    
    return tools


def map_function_name_to_backend_tool_name(function_name: str) -> str:
    """
    Map OpenAI function name to backend tool name.
    
    Args:
        function_name: Function name from OpenAI tool call
        
    Returns:
        Backend tool name string
        
    Raises:
        ValueError: If function_name is not recognized
    """
    mapping = {
        "Slack_search_messages": "Slack.search_messages",
        "GoogleContacts_SearchContactsByName": "GoogleContacts.SearchContactsByName",
        "GoogleCalendar_FindTimeSlotsWhenEveryoneIsFree": "GoogleCalendar.FindTimeSlotsWhenEveryoneIsFree",
        "GoogleCalendar_ListEvents": "GoogleCalendar.ListEvents",
        "Gmail_SearchThreads": "Gmail.SearchThreads",
        "Gmail_GetThread": "Gmail.GetThread",
        "GoogleDrive_gdrive_search": "GoogleDrive.gdrive_search",
        "GoogleDrive_gdrive_read_file": "GoogleDrive.gdrive_read_file",
        "Jira_SearchIssuesWithJql": "Jira.SearchIssuesWithJql",
    }
    
    if function_name not in mapping:
        raise ValueError(f"Unknown function name: {function_name}")
    
    return mapping[function_name]


def run_task_with_openai(
    task: Dict[str, Any],
    data_root: str,
    model: str = "gpt-4o-mini",
    max_tool_rounds: int = 4,
) -> Dict[str, Any]:
    """
    Run a task using OpenAI with tool calling.
    
    Uses a unified tool set and generic system prompt for all task types.
    
    Args:
        task: Task dictionary with task_id and user_prompt
        data_root: Path to data directory (default: "data", uses scenario_A by default)
        model: OpenAI model name (default: "gpt-4o-mini")
        max_tool_rounds: Maximum number of tool-calling rounds (default: 4)
        
    Returns:
        Dictionary with task_id, user_prompt, tool_trace_steps, raw_tool_calls,
        final_answer, and rationale
        
    Raises:
        ImportError: If OpenAI library is not installed
        ValueError: If OpenAI API key is not set
    """
    if OpenAI is None:
        raise ImportError("OpenAI library is not installed. Install it with: pip install openai")
    
    # Load environment variables from .env file
    load_env_file()
    
    # Initialize OpenAI client and tool backend
    client = OpenAI()
    # Extract scenario_id from data_root if it's in path format, otherwise default to scenario_A
    if "/" in data_root:
        scenario_id = Path(data_root).name.replace("company_", "scenario_")
    else:
        scenario_id = "scenario_A"
        data_root = "data"
    backend = ToolBackend(data_root=data_root, scenario_id=scenario_id)
    tools = build_all_tools_spec()
    
    task_id = task["task_id"]
    user_prompt = task["user_prompt"]
    task_type = task.get("task_type", "")
    
    # Log start of agent run
    print(f"[openai_agent_runner] Start: task_id={task_id}, task_type={task_type}, model={model}, data_root={data_root}")
    
    # Load context files from llm_context
    base_dir = Path(__file__).resolve().parent.parent / "llm_context"
    instructions_text = read_text_if_exists(base_dir / "instructions_about_sources.md")
    api_guidelines_text = read_text_if_exists(base_dir / "api_usage_guidelines.md")
    examples_text = read_text_if_exists(base_dir / "examples_of_tool_calls.md")
    
    # Load prompt config
    repo_root = Path(__file__).resolve().parent.parent
    config_path = repo_root / "prompt_config.json"
    with open(config_path, 'r', encoding='utf-8') as f:
        prompt_config = json.load(f)
    
    # Build system message from prompt_config
    system_message = prompt_config["evaluation"]["agent"]["system_message"]
    
    # Build developer message with context
    developer_content_parts = []
    if instructions_text:
        developer_content_parts.append(instructions_text)
    if api_guidelines_text:
        developer_content_parts.append(api_guidelines_text)
    if examples_text:
        developer_content_parts.append(examples_text)
    
    developer_message = "\n\n".join(developer_content_parts)
    
    # Initialize messages
    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": system_message},
        {"role": "developer", "content": developer_message},
        {"role": "user", "content": user_prompt}
    ]
    
    # Initialize logging containers
    tool_trace_steps: List[str] = []
    raw_tool_calls: List[Dict[str, Any]] = []
    final_answer = ""
    rationale = ""
    
    # Agent loop
    step_count = 0
    for round_idx in range(max_tool_rounds):
        step_count += 1
        print(f"[openai_agent_runner] Step {step_count}: calling model...")
        
        # Call the model with tools
        completion = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=tools,
            tool_choice="auto",
            temperature=0.0,
        )
        
        msg = completion.choices[0].message
        
        # Check if model wants to call tools
        if msg.tool_calls and len(msg.tool_calls) > 0:
            tool_calls_count = len(msg.tool_calls)
            print(f"[openai_agent_runner] Step {step_count}: model returned {tool_calls_count} tool call(s)")
            # Append assistant message with tool_calls to messages
            assistant_msg: Dict[str, Any] = {
                "role": "assistant",
            }
            if msg.content:
                assistant_msg["content"] = msg.content
            # Convert tool_calls to dict format for JSON serialization
            tool_calls_dict = []
            for tc in msg.tool_calls:
                tool_calls_dict.append({
                    "id": tc.id,
                    "type": tc.type,
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments
                    }
                })
            assistant_msg["tool_calls"] = tool_calls_dict
            messages.append(assistant_msg)
            
            # Process each tool call
            for tool_call_idx, tool_call in enumerate(msg.tool_calls):
                function_name = tool_call.function.name
                arguments_json = tool_call.function.arguments
                
                # Parse arguments
                try:
                    arguments = json.loads(arguments_json)
                except json.JSONDecodeError as e:
                    raise ValueError(f"Failed to parse tool call arguments: {e}")
                
                # Map to backend tool name
                backend_tool_name = map_function_name_to_backend_tool_name(function_name)
                
                # Log tool call
                arg_keys = list(arguments.keys()) if isinstance(arguments, dict) else []
                print(f"[openai_agent_runner] Step {step_count}: tool_call -> name={backend_tool_name}, arguments keys={arg_keys}")
                
                # Call backend
                result = backend.call_tool(backend_tool_name, arguments)
                
                # Log tool result summary
                if isinstance(result, dict):
                    # Create a short summary of the result
                    if "matches" in result:
                        result_summary = f"{len(result.get('matches', []))} matches"
                    elif "contacts" in result:
                        result_summary = f"{len(result.get('contacts', []))} contacts"
                    elif "time_slots" in result:
                        result_summary = f"{len(result.get('time_slots', []))} time slots"
                    elif "events" in result:
                        result_summary = f"{len(result.get('events', []))} events"
                    elif "threads" in result:
                        result_summary = f"{len(result.get('threads', []))} threads"
                    elif "files" in result:
                        result_summary = f"{len(result.get('files', []))} files"
                    elif "issues" in result:
                        result_summary = f"{len(result.get('issues', []))} issues"
                    else:
                        result_summary = f"dict with {len(result)} keys"
                else:
                    result_summary = str(type(result).__name__)
                
                print(f"[openai_agent_runner] Step {step_count}: tool_result -> name={backend_tool_name}, result_summary={result_summary}")
                
                # Log raw tool call
                raw_tool_calls.append({
                    "tool_name": backend_tool_name,
                    "function_name": function_name,
                    "arguments": arguments,
                    "result": result,
                })
                
                # Build short argument summary for trace
                if backend_tool_name == "Slack.search_messages":
                    short_arg_summary = f"search_query={arguments.get('search_query', '')}"
                elif backend_tool_name == "GoogleContacts.SearchContactsByName":
                    short_arg_summary = f"name={arguments.get('name', '')}"
                elif backend_tool_name == "GoogleCalendar.FindTimeSlotsWhenEveryoneIsFree":
                    email_list = arguments.get('email_addresses', [])
                    short_arg_summary = f"email_addresses={email_list}"
                elif backend_tool_name == "GoogleCalendar.ListEvents":
                    short_arg_summary = (
                        f"min_end_datetime={arguments.get('min_end_datetime', '')}, "
                        f"max_start_datetime={arguments.get('max_start_datetime', '')}"
                    )
                elif backend_tool_name == "Gmail.SearchThreads":
                    subject = arguments.get('subject', '')
                    sender = arguments.get('sender', '')
                    if subject and sender:
                        short_arg_summary = f"subject={subject}, sender={sender}"
                    elif subject:
                        short_arg_summary = f"subject={subject}"
                    elif sender:
                        short_arg_summary = f"sender={sender}"
                    else:
                        short_arg_summary = "no filters"
                elif backend_tool_name == "Gmail.GetThread":
                    short_arg_summary = f"thread_id={arguments.get('thread_id', '')}"
                elif backend_tool_name == "GoogleDrive.gdrive_search":
                    short_arg_summary = f"query={arguments.get('query', '')}"
                elif backend_tool_name == "GoogleDrive.gdrive_read_file":
                    short_arg_summary = f"file_id={arguments.get('file_id', '')}"
                elif backend_tool_name == "Jira.SearchIssuesWithJql":
                    jql = arguments.get('jql', '')
                    # Truncate long JQL queries
                    if len(jql) > 50:
                        short_arg_summary = f"jql={jql[:50]}..."
                    else:
                        short_arg_summary = f"jql={jql}"
                else:
                    short_arg_summary = str(arguments)
                
                # Append to tool trace steps
                step_num = len(tool_trace_steps) + 1
                tool_trace_steps.append(
                    f"Step {step_num}: {backend_tool_name}({short_arg_summary})"
                )
                
                # Append tool message to messages
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": function_name,
                    "content": json.dumps(result, ensure_ascii=False),
                })
            
            # Continue to next iteration to let model observe tool results
            continue
        
        else:
            # No tool calls - this should be the final answer
            content = msg.content or ""
            print(f"[openai_agent_runner] Step {step_count}: no tool calls, expecting final answer")
            
            # Try to parse JSON from content
            try:
                # Remove markdown code fences if present
                content_clean = content.strip()
                if content_clean.startswith("```"):
                    lines = content_clean.split("\n")
                    if lines[0].startswith("```"):
                        lines = lines[1:]
                    if lines[-1].startswith("```"):
                        lines = lines[:-1]
                    content_clean = "\n".join(lines)
                
                parsed = json.loads(content_clean)
                final_answer = parsed.get("final_answer", "")
                rationale = parsed.get("rationale", "")
            except json.JSONDecodeError:
                # Fallback: use content as-is
                final_answer = content
                rationale = ""
            
            # Log final answer preview
            final_preview = (final_answer[:120] + "...") if final_answer and len(final_answer) > 120 else (final_answer or "")
            print(f"[openai_agent_runner] Final answer preview=\"{final_preview}\"")
            
            # Break the loop
            break
    
    # If we never saw a final answer, use the last message content
    if not final_answer and not rationale:
        last_msg = messages[-1] if messages else None
        if last_msg and last_msg.get("role") == "assistant":
            final_answer = last_msg.get("content", "") or ""
            rationale = ""
    
    # Construct the run log dict
    log = {
        "task_id": task_id,
        "user_prompt": user_prompt,
        "tool_trace_steps": tool_trace_steps,
        "raw_tool_calls": raw_tool_calls,
        "final_answer": final_answer,
        "rationale": rationale,
    }
    
    # Log run completion summary
    total_steps = step_count
    total_tool_calls = len(raw_tool_calls)
    print(f"[openai_agent_runner] Run complete: steps={total_steps}, tool_calls={total_tool_calls}")
    
    return log

