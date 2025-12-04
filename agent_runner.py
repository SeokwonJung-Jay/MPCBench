"""Agent runner for MPCBench v2.

Runs a single task by calling the LLM with tools and getting an answer.
"""

from typing import Dict, Any, Optional, List
from pathlib import Path
import json
import os

# Import config to ensure .env is loaded
import config

from config import PROMPT_CONFIG_PATH, MODEL_CONFIG_PATH
from task_defs import Task
from tool_backend import ToolBackend


def get_openai_client():
    """Get OpenAI client, checking for API key."""
    try:
        from openai import OpenAI
        # Ensure config is imported (loads .env)
        import config
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set. Please set it in .env file or as an environment variable.")
        return OpenAI(api_key=api_key)
    except ImportError:
        raise ImportError("openai package not installed. Install with: pip install openai")


def build_tool_schemas(backend: ToolBackend, tool_context_mode: str = "detailed") -> List[Dict[str, Any]]:
    """
    Build OpenAI tool schemas based on available sources in backend.
    
    Args:
        backend: ToolBackend instance
        tool_context_mode: "minimal" or "detailed" (default: "detailed")
        
    Returns:
        List of tool schemas for OpenAI function calling
    """
    # Load prompt config for tool descriptions
    try:
        with open(PROMPT_CONFIG_PATH, 'r', encoding='utf-8') as f:
            prompt_config = json.load(f)
        tool_descriptions = prompt_config.get("tool_descriptions", {})
    except Exception:
        tool_descriptions = {}
    
    def get_tool_description(tool_name: str) -> str:
        """Get tool description based on context mode."""
        tool_desc = tool_descriptions.get(tool_name, "")
        if isinstance(tool_desc, dict):
            # New format: {minimal: "...", detailed: "..."}
            return tool_desc.get(tool_context_mode, tool_desc.get("detailed", ""))
        else:
            # Old format: just a string (for backward compatibility)
            return tool_desc if isinstance(tool_desc, str) else ""
    
    tools = []
    
    # Calendar tools
    if "calendar" in backend.source_data:
        # calendar_list_events
        tools.append({
            "type": "function",
            "function": {
                "name": "calendar_list_events",
                "description": get_tool_description("calendar_list_events") or "List calendar events for given email addresses within an optional date range.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "email_addresses": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of email addresses to check events for"
                        },
                        "start_date": {
                            "type": "string",
                            "description": "Optional start date filter (YYYY-MM-DD). If not specified, searches all available dates. Use current date as reference for relative dates like 'next week'."
                        },
                        "end_date": {
                            "type": "string",
                            "description": "Optional end date filter (YYYY-MM-DD). If not specified, searches all available dates. Use current date as reference for relative dates like 'next week'."
                        }
                    },
                    "required": ["email_addresses"]
                }
            }
        })
        
        # calendar_query_freebusy
        tools.append({
            "type": "function",
            "function": {
                "name": "calendar_query_freebusy",
                "description": get_tool_description("calendar_query_freebusy") or "Query common free time slots for multiple email addresses.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "email_addresses": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of email addresses to check availability for"
                        },
                        "start_date": {
                            "type": "string",
                            "description": "Optional start date filter (YYYY-MM-DD). If not specified, searches all available dates. Use current date as reference for relative dates like 'next week'."
                        },
                        "end_date": {
                            "type": "string",
                            "description": "Optional end date filter (YYYY-MM-DD). If not specified, searches all available dates. Use current date as reference for relative dates like 'next week'."
                        },
                        "duration_minutes": {
                            "type": "integer",
                            "description": "Minimum duration in minutes (optional)"
                        }
                    },
                    "required": ["email_addresses"]
                }
            }
        })
    
    # Slack tools
    if "slack" in backend.source_data:
        # slack_list_channels
        tools.append({
            "type": "function",
            "function": {
                "name": "slack_list_channels",
                "description": get_tool_description("slack_list_channels") or "List Slack channels.",
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            }
        })
        
        # slack_list_messages
        tools.append({
            "type": "function",
            "function": {
                "name": "slack_list_messages",
                "description": get_tool_description("slack_list_messages") or "List Slack messages, optionally filtered by channel_id.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "channel_id": {
                            "type": "string",
                            "description": "Optional channel identifier to filter messages. If not provided, returns messages from all channels."
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of results (optional)"
                        }
                    }
                }
            }
        })
        
        # slack_search_messages
        tools.append({
            "type": "function",
            "function": {
                "name": "slack_search_messages",
                "description": get_tool_description("slack_search_messages") or "Search Slack messages by user name.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "user_name": {
                            "type": "string",
                            "description": "User name to search for (e.g., 'alice', 'bob'). If empty, returns all messages."
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of results (optional)"
                        }
                    },
                    "required": ["user_name"]
                }
            }
        })
        
        # slack_get_channel
        tools.append({
            "type": "function",
            "function": {
                "name": "slack_get_channel",
                "description": get_tool_description("slack_get_channel") or "Get channel information by channel_id.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "channel_id": {
                            "type": "string",
                            "description": "Channel identifier (obtained from slack_list_channels)"
                        }
                    },
                    "required": ["channel_id"]
                }
            }
        })
    
    # Gmail tools
    if "gmail" in backend.source_data:
        # gmail_list_threads
        tools.append({
            "type": "function",
            "function": {
                "name": "gmail_list_threads",
                "description": get_tool_description("gmail_list_threads") or "List Gmail threads, optionally filtered by search query.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Optional search query to filter threads by subject or message content. If not provided, returns all threads."
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of results (optional)"
                        }
                    }
                }
            }
        })
        
        # gmail_list_messages
        tools.append({
            "type": "function",
            "function": {
                "name": "gmail_list_messages",
                "description": get_tool_description("gmail_list_messages") or "List Gmail messages across all threads, optionally filtered by search query.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Optional search query to filter messages by subject or text. If not provided, returns all messages."
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of results (optional)"
                        }
                    }
                }
            }
        })
        
        # gmail_get_thread
        tools.append({
            "type": "function",
            "function": {
                "name": "gmail_get_thread",
                "description": get_tool_description("gmail_get_thread") or "Get thread details by thread_id.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "thread_id": {
                            "type": "string",
                            "description": "Thread identifier (obtained from gmail_list_threads)"
                        }
                    },
                    "required": ["thread_id"]
                }
            }
        })
        
        # gmail_get_message
        tools.append({
            "type": "function",
            "function": {
                "name": "gmail_get_message",
                "description": get_tool_description("gmail_get_message") or "Get message details by message_id.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "message_id": {
                            "type": "string",
                            "description": "Message identifier in format 'thread_id:index' (obtained from gmail_list_messages)"
                        }
                    },
                    "required": ["message_id"]
                }
            }
        })
    
    # Jira tools
    if "jira" in backend.source_data:
        # jira_list_projects
        tools.append({
            "type": "function",
            "function": {
                "name": "jira_list_projects",
                "description": get_tool_description("jira_list_projects") or "List Jira projects.",
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            }
        })
        
        # jira_search_issues
        tools.append({
            "type": "function",
            "function": {
                "name": "jira_search_issues",
                "description": get_tool_description("jira_search_issues") or "Search Jira issues using JQL query or filters.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "project": {
                            "type": "string",
                            "description": "Project key to filter by (optional)"
                        },
                        "status": {
                            "type": "string",
                            "description": "Status to filter by (optional)"
                        }
                    }
                }
            }
        })
    
    # Drive tools
    if "drive" in backend.source_data:
        # drive_list_files
        tools.append({
            "type": "function",
            "function": {
                "name": "drive_list_files",
                "description": get_tool_description("drive_list_files") or "List Drive files, optionally filtered by search query.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Optional search query to filter files by name. If not provided, returns all files."
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of results (optional)"
                        }
                    }
                }
            }
        })
        
        # drive_get_file
        tools.append({
            "type": "function",
            "function": {
                "name": "drive_get_file",
                "description": get_tool_description("drive_get_file") or "Get file details by file_id.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_id": {
                            "type": "string",
                            "description": "File identifier (obtained from drive_list_files)"
                        }
                    },
                    "required": ["file_id"]
                }
            }
        })
        
        # drive_export_file
        tools.append({
            "type": "function",
            "function": {
                "name": "drive_export_file",
                "description": get_tool_description("drive_export_file") or "Export file content by file_id.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_id": {
                            "type": "string",
                            "description": "File identifier (obtained from drive_list_files or drive_get_file)"
                        }
                    },
                    "required": ["file_id"]
                }
            }
        })
    
    return tools


def execute_tool_call(backend: ToolBackend, tool_name: str, arguments: Dict[str, Any]) -> Any:
    """
    Execute a tool call on the backend.
    
    Args:
        backend: ToolBackend instance
        tool_name: Name of the tool to call
        arguments: Tool arguments
        
    Returns:
        Tool result
    """
    if tool_name == "calendar_list_events":
        return backend.calendar_list_events(
            email_addresses=arguments.get("email_addresses", []),
            start_date=arguments.get("start_date"),
            end_date=arguments.get("end_date")
        )
    elif tool_name == "calendar_query_freebusy":
        return backend.calendar_query_freebusy(
            email_addresses=arguments.get("email_addresses", []),
            start_date=arguments.get("start_date"),
            end_date=arguments.get("end_date"),
            duration_minutes=arguments.get("duration_minutes")
        )
    elif tool_name == "slack_list_channels":
        return backend.slack_list_channels()
    elif tool_name == "slack_list_messages":
        return backend.slack_list_messages(
            channel_id=arguments.get("channel_id"),
            limit=arguments.get("limit")
        )
    elif tool_name == "slack_search_messages":
        return backend.slack_search_messages(
            user_name=arguments.get("user_name", ""),
            limit=arguments.get("limit")
        )
    elif tool_name == "slack_get_channel":
        return backend.slack_get_channel(
            channel_id=arguments.get("channel_id", "")
        )
    elif tool_name == "gmail_list_threads":
        return backend.gmail_list_threads(
            query=arguments.get("query"),
            limit=arguments.get("limit")
        )
    elif tool_name == "gmail_list_messages":
        return backend.gmail_list_messages(
            query=arguments.get("query"),
            limit=arguments.get("limit")
        )
    elif tool_name == "gmail_get_thread":
        return backend.gmail_get_thread(
            thread_id=arguments.get("thread_id", "")
        )
    elif tool_name == "gmail_get_message":
        return backend.gmail_get_message(
            message_id=arguments.get("message_id", "")
        )
    elif tool_name == "jira_list_projects":
        return backend.jira_list_projects()
    elif tool_name == "jira_search_issues":
        return backend.jira_search_issues(
            jql=arguments.get("jql"),
            project=arguments.get("project"),
            status=arguments.get("status"),
            limit=arguments.get("limit")
        )
    elif tool_name == "jira_get_issue":
        return backend.jira_get_issue(
            issue_key=arguments.get("issue_key", "")
        )
    elif tool_name == "jira_get_project":
        return backend.jira_get_project(
            project_key=arguments.get("project_key", "")
        )
    elif tool_name == "drive_list_files":
        return backend.drive_list_files(
            query=arguments.get("query"),
            limit=arguments.get("limit")
        )
    elif tool_name == "drive_get_file":
        return backend.drive_get_file(
            file_id=arguments.get("file_id", "")
        )
    elif tool_name == "drive_export_file":
        return backend.drive_export_file(
            file_id=arguments.get("file_id", "")
        )
    else:
        raise ValueError(f"Unknown tool: {tool_name}")


def run_task(
    task: Task,
    source_data: Dict[str, Path],
    agent_model: str = "gpt-4o-mini",
    output_path: Optional[Path] = None,
    tool_context_mode: str = "detailed"
) -> Dict[str, Any]:
    """
    [Core function] Function for LLM Agent to solve a task
    
    Overall flow:
        1. Initialize ToolBackend (load source_data)
        2. Build tool schemas (OpenAI function calling format)
        3. Construct system prompt and user message
        4. Agent loop:
           - Call LLM API
           - If tool calls exist, execute and pass results to LLM
           - If no tool calls, treat as final answer and parse
        5. Return and save results
    
    Key concepts:
        - OpenAI function calling: How LLM selects and calls tools
        - Tool schemas: Definition of each tool's name, description, parameters
        - Agent loop: Tool call → execute → pass results → next response (repeat)
    
    Args:
        task: Task definition to solve
        source_data: Dictionary of source data file paths
        agent_model: LLM model name to use
        output_path: Path to save execution log (optional)
        tool_context_mode: "minimal" or "detailed" (tool description detail level)
        
    Returns:
        {
            "task_id": ...,
            "final_answer": "...",  # Final answer generated by LLM
            "rationale": "...",     # Rationale explained by LLM
            "tool_calls": [...]     # List of executed tool calls
        }
    """
    # ============================================================
    # Step 1: Initialize ToolBackend
    # ============================================================
    # Load source data to create tool backend
    backend = ToolBackend(source_data)
    
    # ============================================================
    # Step 2: Load prompts
    # ============================================================
    # Load system prompt (defines LLM's role)
    # 17-1: Explicit check - raise ValueError if config is missing
    try:
        with open(PROMPT_CONFIG_PATH, 'r', encoding='utf-8') as f:
            prompt_config = json.load(f)
    except FileNotFoundError:
        raise ValueError(f"Prompt config file not found: {PROMPT_CONFIG_PATH}")
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in prompt config: {e}")
    
    agent_config = prompt_config.get("agent", {})
    if not agent_config:
        raise ValueError("Missing 'agent' section in prompt_config.json")
    
    # 17-2: System prompt minimal/detailed separation
    system_message_config = agent_config.get("system_message")
    if not system_message_config:
        raise ValueError("Missing 'agent.system_message' in prompt_config.json")
    
    if isinstance(system_message_config, str):
        # Backward compatibility: if it's a string, use it for both modes
        system_prompt = system_message_config
    elif isinstance(system_message_config, dict):
        # New format: select based on tool_context_mode
        system_prompt = system_message_config.get(tool_context_mode)
        if not system_prompt:
            raise ValueError(f"Missing 'agent.system_message.{tool_context_mode}' in prompt_config.json")
    else:
        raise ValueError("'agent.system_message' must be a string or an object with 'minimal' and 'detailed' keys")
    
    # ============================================================
    # Step 3: Build tool schemas
    # ============================================================
    # Create tool definitions in OpenAI function calling format
    # - Use "minimal" or "detailed" descriptions based on tool_context_mode
    tools = build_tool_schemas(backend, tool_context_mode=tool_context_mode)
    
    # ============================================================
    # Step 4: Construct user message
    # ============================================================
    # Task description + current date + tool usage instructions + response format instructions
    # 17-4: User message instructions from config
    from datetime import datetime
    if task.current_date:
        current_date = task.current_date
    else:
        current_date = datetime.now().strftime("%Y-%m-%d")
    
    user_message = task.task_description
    user_message += f"\n\nCurrent date: {current_date}. When interpreting relative dates like 'next week', use this as the reference point."
    
    # 17-3: Remove tool branch - tools are always available (at least calendar)
    # 17-4: Load user message instructions from config
    user_message_instructions = agent_config.get("user_message_instructions", {})
    if not user_message_instructions:
        raise ValueError("Missing 'agent.user_message_instructions' in prompt_config.json")
    
    instructions = user_message_instructions.get(tool_context_mode)
    if not instructions:
        raise ValueError(f"Missing 'agent.user_message_instructions.{tool_context_mode}' in prompt_config.json")
    
    # Build user message from config
    tool_names = [t["function"]["name"] for t in tools]
    tool_list_text = instructions.get("tool_list", "").format(tool_names=', '.join(tool_names))
    tool_usage_text = instructions.get("tool_usage", "")
    date_range_hint = instructions.get("date_range_hint", "")
    calendar_warning = instructions.get("calendar_warning", "")
    response_format = instructions.get("response_format", "")
    
    user_message += f"\n\n{tool_list_text}"
    user_message += f"\n\n{tool_usage_text}"
    if date_range_hint:
        user_message += f"\n\n{date_range_hint}"
    if calendar_warning:
        user_message += f"\n\n{calendar_warning}"
    user_message += f"\n\n{response_format}"
    
    # ============================================================
    # Step 5: Initialize OpenAI client
    # ============================================================
    client = get_openai_client()
    
    # ============================================================
    # Step 6: Start agent loop
    # ============================================================
    # Initialize message history
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message}
    ]
    
    tool_calls_log = []  # Tool call log
    step = 0
    max_steps = 10  # Safety mechanism: maximum iteration count
    
    while step < max_steps:
        step += 1
        
        # ============================================================
        # Step 6-1: Call LLM API
        # ============================================================
        # Call OpenAI Chat Completions API
        # - tools parameter: list of available tools
        # - tool_choice="auto": LLM selects and calls tools when needed
        try:
            # 17-3: Remove tool branch - tools are always available
            response = client.chat.completions.create(
                model=agent_model,
                messages=messages,  # Conversation history
                tools=tools,  # Tool definitions (always present)
                tool_choice="auto",  # Automatic tool selection
                temperature=0.0  # Consistent responses
            )
        except Exception as e:
            # Return error if API call fails
            return {
                "task_id": task.id,
                "final_answer": f"Error calling LLM: {e}",
                "rationale": "",
                "tool_calls": tool_calls_log
            }
        
        message = response.choices[0].message
        
        # ============================================================
        # Step 6-2: Add assistant response to history
        # ============================================================
        # Add LLM's response to message history
        # (save tool_calls together if present)
        messages.append({
            "role": "assistant",
            "content": message.content,
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": tc.type,
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments
                    }
                } for tc in (message.tool_calls or [])
            ] if message.tool_calls else None
        })
        
        # ============================================================
        # Step 6-3: Process tool calls
        # ============================================================
        if message.tool_calls:
            # LLM wants to call tools
            # Execute each tool call and pass results to LLM
            
            for tool_call in message.tool_calls:
                tool_name = tool_call.function.name
                try:
                    arguments = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError:
                    arguments = {}
                
                # Execute tool
                try:
                    result = execute_tool_call(backend, tool_name, arguments)
                except Exception as e:
                    result = {"error": str(e)}
                
                # Save tool call log
                tool_calls_log.append({
                    "step": len(tool_calls_log) + 1,
                    "tool_name": tool_name,
                    "arguments": arguments,
                    "result": result
                })
                
                # Add tool results to message history
                # (LLM can reference these results in the next response)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(result)
                })
            
            # Continue loop after receiving tool results (LLM processes results and generates next response)
            continue
        else:
            # ============================================================
            # Step 6-4: Parse final answer
            # ============================================================
            # If no tool calls, treat as final answer
            # Parse "Final Answer:" and "Rationale:" sections
            
            response_content = message.content or ""
            
            final_answer = ""
            rationale = ""
            
            # Try to extract from structured format
            if "Final Answer:" in response_content and "Rationale:" in response_content:
                parts = response_content.split("Rationale:", 1)
                if len(parts) == 2:
                    final_answer_part = parts[0].replace("Final Answer:", "").strip()
                    rationale = parts[1].strip()
                    final_answer = final_answer_part
                else:
                    final_answer = response_content
                    rationale = "No separate rationale provided."
            elif "Final Answer:" in response_content:
                final_answer = response_content.split("Final Answer:", 1)[1].strip() if "Final Answer:" in response_content else response_content
                rationale = "No rationale section found in response."
            else:
                # If no structured format, use entire content as final_answer
                final_answer = response_content
                rationale = "No structured rationale provided. The agent did not follow the requested format."
            
            # Return result
            result = {
                "task_id": task.id,
                "final_answer": final_answer,
                "rationale": rationale,
                "tool_calls": tool_calls_log
            }
            
            # Save log
            if output_path:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(result, f, indent=2)
            
            return result
    
    # If we hit max steps, return what we have
    response_content = messages[-1].get("content", "") if messages else ""
    
    # Parse final_answer and rationale from structured response
    final_answer = ""
    rationale = ""
    
    if response_content:
        # Try to extract from structured format
        if "Final Answer:" in response_content and "Rationale:" in response_content:
            parts = response_content.split("Rationale:", 1)
            if len(parts) == 2:
                final_answer_part = parts[0].replace("Final Answer:", "").strip()
                rationale = parts[1].strip()
                final_answer = final_answer_part
            else:
                final_answer = response_content
                rationale = "No separate rationale provided."
        elif "Final Answer:" in response_content:
            final_answer = response_content.split("Final Answer:", 1)[1].strip() if "Final Answer:" in response_content else response_content
            rationale = "No rationale section found in response."
        else:
            final_answer = response_content
            rationale = "No structured rationale provided. The agent did not follow the requested format."
    else:
        final_answer = "Max steps reached"
        rationale = "The agent reached the maximum number of steps without providing a final answer."
    
    return {
        "task_id": task.id,
        "final_answer": final_answer,
        "rationale": rationale,
        "tool_calls": tool_calls_log
    }
