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
    
    # Contacts tool
    if "contacts" in backend.source_data:
        tools.append({
            "type": "function",
            "function": {
                "name": "contacts_search_by_name",
                "description": get_tool_description("contacts_search_by_name") or "Search contacts by name.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Name to search for"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of results (optional)"
                        }
                    },
                    "required": ["name"]
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
    elif tool_name == "contacts_search_by_name":
        return backend.contacts_search_by_name(
            name=arguments.get("name", ""),
            limit=arguments.get("limit")
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
    [핵심 함수] LLM Agent가 task를 해결하는 함수
    
    전체 흐름:
        1. ToolBackend 초기화 (source_data 로드)
        2. Tool schemas 빌드 (OpenAI function calling 형식)
        3. System prompt와 user message 구성
        4. Agent loop:
           - LLM API 호출
           - Tool call이 있으면 실행하고 결과를 LLM에 전달
           - Tool call이 없으면 final answer로 간주하고 파싱
        5. 결과 반환 및 저장
    
    핵심 개념:
        - OpenAI function calling: LLM이 tool을 선택하고 호출하는 방식
        - Tool schemas: 각 tool의 이름, 설명, 파라미터 정의
        - Agent loop: Tool call → 실행 → 결과 전달 → 다음 응답 반복
    
    Args:
        task: 해결할 task 정의
        source_data: 소스 데이터 파일 경로 딕셔너리
        agent_model: 사용할 LLM 모델 이름
        output_path: 실행 로그 저장 경로 (선택)
        tool_context_mode: "minimal" 또는 "detailed" (tool 설명 상세도)
        
    Returns:
        {
            "task_id": ...,
            "final_answer": "...",  # LLM이 생성한 최종 답변
            "rationale": "...",     # LLM이 설명한 근거
            "tool_calls": [...]     # 실행한 tool 호출 리스트
        }
    """
    # ============================================================
    # Step 1: ToolBackend 초기화
    # ============================================================
    # Source data를 로드하여 tool backend 생성
    backend = ToolBackend(source_data)
    
    # ============================================================
    # Step 2: Prompt 로드
    # ============================================================
    # System prompt 로드 (LLM의 역할 정의)
    try:
        with open(PROMPT_CONFIG_PATH, 'r', encoding='utf-8') as f:
            prompt_config = json.load(f)
        system_prompt = prompt_config.get("agent", {}).get("system_message", 
            "You are a helpful workplace assistant that can access multiple data sources to help users complete tasks.")
    except Exception:
        system_prompt = "You are a helpful workplace assistant that can access multiple data sources to help users complete tasks."
    
    # ============================================================
    # Step 3: Tool schemas 빌드
    # ============================================================
    # OpenAI function calling 형식으로 tool 정의 생성
    # - tool_context_mode에 따라 "minimal" 또는 "detailed" 설명 사용
    tools = build_tool_schemas(backend, tool_context_mode=tool_context_mode)
    
    # ============================================================
    # Step 4: User message 구성
    # ============================================================
    # Task description + 현재 날짜 + tool 사용 지시 + 응답 형식 지시
    from datetime import datetime
    if task.current_date:
        current_date = task.current_date
    else:
        current_date = datetime.now().strftime("%Y-%m-%d")
    
    user_message = task.task_description
    user_message += f"\n\nCurrent date: {current_date}. When interpreting relative dates like 'next week', use this as the reference point."
    
    if tools:
        # Tool이 있는 경우: tool 목록과 사용 지시 추가
        tool_names = [t["function"]["name"] for t in tools]
        user_message += f"\n\nYou have access to the following tools: {', '.join(tool_names)}."
        user_message += f"\n\nIMPORTANT: You MUST use the available tools to gather information before providing your final answer. Do not provide an answer without first calling the relevant tools to check calendars, contacts, and other data sources."
        user_message += f"\n\nIf you're unsure about the exact date range, you can call calendar_query_freebusy without specifying start_date and end_date to search all available dates. This is often more reliable than guessing dates."
        user_message += f"\n\nAfter you have gathered all necessary information using the tools, provide your final answer in the following format:\n"
    else:
        # Tool이 없는 경우: 기본 응답 형식만 지시
        user_message += "\n\nWhen you are ready to provide your final answer, format your response as follows:\n"
    
    # 응답 형식 지시
    user_message += "Final Answer:\n[Your final answer here]\n\n"
    user_message += "Rationale:\n[Your explanation here, including:\n"
    user_message += "- Which tools you used and why\n"
    user_message += "- What information you found from each source\n"
    user_message += "- How you applied any constraints or filters\n"
    user_message += "- Why you selected the final answer]\n"
    
    # ============================================================
    # Step 5: OpenAI client 초기화
    # ============================================================
    client = get_openai_client()
    
    # ============================================================
    # Step 6: Agent loop 시작
    # ============================================================
    # 메시지 히스토리 초기화
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message}
    ]
    
    tool_calls_log = []  # Tool 호출 로그
    step = 0
    max_steps = 10  # 안전 장치: 최대 반복 횟수
    
    while step < max_steps:
        step += 1
        
        # ============================================================
        # Step 6-1: LLM API 호출
        # ============================================================
        # OpenAI Chat Completions API 호출
        # - tools 파라미터: 사용 가능한 tool 목록
        # - tool_choice="auto": LLM이 필요시 tool을 선택하여 호출
        try:
            response = client.chat.completions.create(
                model=agent_model,
                messages=messages,  # 대화 히스토리
                tools=tools if tools else None,  # Tool 정의
                tool_choice="auto" if tools else None,  # Tool 사용 자동 선택
                temperature=0.0  # 일관성 있는 응답
            )
        except Exception as e:
            # API 호출 실패 시 에러 반환
            return {
                "task_id": task.id,
                "final_answer": f"Error calling LLM: {e}",
                "rationale": "",
                "tool_calls": tool_calls_log
            }
        
        message = response.choices[0].message
        
        # ============================================================
        # Step 6-2: Assistant 응답을 히스토리에 추가
        # ============================================================
        # LLM의 응답을 메시지 히스토리에 추가
        # (tool_calls가 있으면 함께 저장)
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
        # Step 6-3: Tool call 처리
        # ============================================================
        if message.tool_calls:
            # LLM이 tool을 호출하려고 함
            # 각 tool call을 실행하고 결과를 LLM에 전달
            
            for tool_call in message.tool_calls:
                tool_name = tool_call.function.name
                try:
                    arguments = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError:
                    arguments = {}
                
                # Tool 실행
                try:
                    result = execute_tool_call(backend, tool_name, arguments)
                except Exception as e:
                    result = {"error": str(e)}
                
                # Tool 호출 로그 저장
                tool_calls_log.append({
                    "step": len(tool_calls_log) + 1,
                    "tool_name": tool_name,
                    "arguments": arguments,
                    "result": result
                })
                
                # Tool 결과를 메시지 히스토리에 추가
                # (LLM이 다음 응답에서 이 결과를 참조할 수 있음)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(result)
                })
            
            # Tool 결과를 받았으므로 loop 계속 (LLM이 결과를 처리하고 다음 응답 생성)
            continue
        else:
            # ============================================================
            # Step 6-4: Final answer 파싱
            # ============================================================
            # Tool call이 없으면 final answer로 간주
            # "Final Answer:"와 "Rationale:" 섹션을 파싱
            
            response_content = message.content or ""
            
            final_answer = ""
            rationale = ""
            
            # 구조화된 형식에서 추출 시도
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
                # 구조화된 형식이 없으면 전체를 final_answer로 사용
                final_answer = response_content
                rationale = "No structured rationale provided. The agent did not follow the requested format."
            
            # 결과 반환
            result = {
                "task_id": task.id,
                "final_answer": final_answer,
                "rationale": rationale,
                "tool_calls": tool_calls_log
            }
            
            # 로그 저장
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
