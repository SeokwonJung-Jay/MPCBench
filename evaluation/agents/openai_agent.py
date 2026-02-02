"""
OpenAI-based agent implementation for MPCBench evaluation.
"""

import json
import os
import re
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from openai import OpenAI

from evaluation.agents.base import BaseAgent, Candidate
from evaluation.tools import SimulatedAPI


# Load environment variables from .env file
load_dotenv()


class OpenAIAgent(BaseAgent):
    """
    Agent that uses OpenAI API to solve scheduling tasks.
    """
    
    SYSTEM_PROMPT = """You are a precise scheduling engine.

Systemic constraints:
- Time grid: All candidate start/end times must align to 15-minute intervals (:00, :15, :30, :45).
- Dense packing: Enumerate all feasible slots. Do not skip overlapping time windows (e.g., if 9:00-9:30 is feasible, also include 9:15-9:45).
- Output format: All datetime strings must include timezone offset (e.g., +09:00).

Information gathering:
- You must use the provided tools to actively query information you need. Initially, only the Task is provided, so you should search for relevant IDs or text to collect information before performing scheduling.
- For Level 2/3 tasks: You MUST read the communication threads (use list_thread_ids, then read_communication_thread) to discover the actual task requirements (time window, duration, number of options, policy to follow, etc.).

**IMPORTANT: Chain-of-Thought Required**
Before providing the final JSON output, you MUST explain your reasoning process step-by-step:
1. List the constraints you identified (time windows, excluded times, required duration, etc.).
2. Explain how you filtered the candidates (e.g., which slots were eliminated and why).
3. Explain why you selected specific time slots or rooms (if applicable).
4. Finally, provide the JSON object wrapped in ```json ... ``` block.

**OUTPUT FORMAT (Strict JSON):**

[CRITICAL FOR LEVEL 3 - ROOM ASSIGNMENT]
If the task involves finding/assigning a room (Level 3), every candidate object MUST include the "room_id" field.

DEFINITION: Each "option" or "candidate" is a unique (start, end, room_id) tuple.
When asked to provide N options:
  1. Find the BEST available time slot first
  2. Provide N DIFFERENT ROOMS at that same time slot
  3. DO NOT provide N different time slots with the same room

Sorting: earliest start → earliest end → smallest room_id.

Example JSON output for Level 1/2 (no room):
```json
{
  "candidates": [
    {"start": "2026-01-20T09:00:00+09:00", "end": "2026-01-20T10:00:00+09:00"},
    {"start": "2026-01-20T09:15:00+09:00", "end": "2026-01-20T10:15:00+09:00"}
  ]
}
```

Example JSON output for Level 3 (with room - REQUIRED):
```json
{
  "candidates": [
    {"start": "2026-01-20T09:00:00+09:00", "end": "2026-01-20T10:00:00+09:00", "room_id": "room_001"},
    {"start": "2026-01-20T09:00:00+09:00", "end": "2026-01-20T10:00:00+09:00", "room_id": "room_002"},
    {"start": "2026-01-20T09:00:00+09:00", "end": "2026-01-20T10:00:00+09:00", "room_id": "room_003"}
  ]
}
```"""

    def __init__(
        self,
        model_name: str = "gpt-4o",
        temperature: float = 0.0,
        max_tokens: int = 4096,
        api_key: Optional[str] = None,
    ):
        """
        Initialize the OpenAI agent.
        
        Args:
            model_name: OpenAI model to use (default: "gpt-4o").
            temperature: Sampling temperature (default: 0.0 for deterministic).
            max_tokens: Maximum tokens in response.
            api_key: OpenAI API key. If None, reads from OPENAI_API_KEY env var.
        """
        self.model_name = model_name
        self.temperature = temperature
        self.max_tokens = max_tokens
        
        # Initialize OpenAI client
        self.client = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))
        
        # Initialize trace for silent tool use tracking
        self.last_trace: List[Dict[str, Any]] = []
    
    def solve(self, task_text: str, context_data: dict) -> List[Candidate]:
        """
        Solve a scheduling task using OpenAI API with tool use (ReAct loop).
        
        Args:
            task_text: The task description text.
            context_data: Sanitized context data (world sources + instance data).
            
        Returns:
            List of candidate tuples in ISO 8601 string format:
                - L1/L2: [(start, end), ...]
                - L3: [(start, end, room_id), ...]
            Returns empty list [] on failure.
        """
        # Initialize trace (silent mode)
        self.last_trace = []
        
        # Initialize SimulatedAPI
        world = context_data.get("world", {})
        instance = context_data.get("instance", {})
        api = SimulatedAPI(world, instance)
        
        # Get tool definitions
        tools = api.get_tool_definitions()
        
        # Build user prompt (without full context_data)
        user_prompt = self._build_user_prompt(task_text, instance)
        
        # Initialize message history
        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]
        
        # Add user message to trace (system message excluded)
        self.last_trace.append({
            "role": "user",
            "content": user_prompt,
        })
        
        # ReAct loop (max 15 turns)
        max_turns = 15
        for turn in range(max_turns):
            try:
                # Call OpenAI API with tools
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=messages,
                    tools=tools,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                )
                
                response_message = response.choices[0].message
                
                # Check if there are tool calls
                tool_calls = response_message.tool_calls
                
                # Add assistant message to history
                assistant_msg = {
                    "role": "assistant",
                    "content": response_message.content or None,
                }
                
                if tool_calls:
                    assistant_msg["tool_calls"] = [
                        {
                            "id": tc.id,
                            "type": tc.type,
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            }
                        }
                        for tc in tool_calls
                    ]
                
                messages.append(assistant_msg)
                
                # Add assistant message to trace (silent mode)
                trace_assistant_msg = {
                    "role": "assistant",
                    "content": response_message.content or None,
                }
                if tool_calls:
                    trace_assistant_msg["tool_calls"] = [
                        {
                            "id": tc.id,
                            "type": tc.type,
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            }
                        }
                        for tc in tool_calls
                    ]
                self.last_trace.append(trace_assistant_msg)
                
                if tool_calls:
                    # Execute tool calls
                    for tool_call in tool_calls:
                        tool_name = tool_call.function.name
                        tool_args_str = tool_call.function.arguments
                        
                        try:
                            # Parse arguments
                            tool_args = json.loads(tool_args_str)
                            
                            # Execute tool
                            tool_result = api.execute_tool(tool_name, tool_args)
                            
                            # Add tool result to messages
                            tool_msg = {
                                "role": "tool",
                                "tool_call_id": tool_call.id,
                                "content": json.dumps(tool_result, ensure_ascii=False),
                            }
                            messages.append(tool_msg)
                            
                            # Add tool result to trace (silent mode)
                            self.last_trace.append({
                                "role": "tool",
                                "tool_call_id": tool_call.id,
                                "content": json.dumps(tool_result, ensure_ascii=False),
                            })
                        except Exception as e:
                            # Tool execution failed (silent mode - no print)
                            error_result = {"error": f"Tool execution failed: {str(e)}"}
                            error_msg = {
                                "role": "tool",
                                "tool_call_id": tool_call.id,
                                "content": json.dumps(error_result, ensure_ascii=False),
                            }
                            messages.append(error_msg)
                            
                            # Add error to trace (silent mode)
                            self.last_trace.append(error_msg)
                    
                    # Continue loop to get next response
                    continue
                
                # No tool calls - check if we have final answer
                if response_message.content:
                    # Try to parse as JSON (final answer)
                    try:
                        candidates = self._parse_response(response_message.content)
                        if candidates:
                            return candidates
                        # If parsing returned empty list, continue to get better answer (silent mode)
                        continue
                    except Exception:
                        # Continue loop to get better answer (silent mode)
                        continue
                
                # No content and no tool calls - unexpected state (silent mode)
                continue
                
            except Exception:
                # API call failed (silent mode - no print)
                break
        
        # Max turns reached or error occurred (silent mode)
        return []
    
    def _build_user_prompt(self, task_text: str, instance: dict) -> str:
        """
        Build the user prompt with task text and basic reference information.
        
        Args:
            task_text: The task description.
            instance: The instance dict (for sources_ref and slots).
            
        Returns:
            Formatted user prompt string.
        """
        # Extract basic reference information
        sources_ref = instance.get("sources_ref", {})
        slots = instance.get("slots", {})
        participants = slots.get("participants", [])
        
        # Build available refs string
        # Note: world_id is intentionally excluded to prevent hallucination
        # Agent should use list_* tools to discover available IDs
        refs_parts = []
        if sources_ref.get("policy_doc_id"):
            refs_parts.append(f"policy_doc_id: {sources_ref['policy_doc_id']}")
        if sources_ref.get("comm_thread_ids"):
            refs_parts.append(f"comm_thread_ids: {sources_ref['comm_thread_ids']}")
        
        available_refs = "\n".join(refs_parts) if refs_parts else "Use list_* tools to discover available resources."
        
        # Build participants string
        participants_str = ", ".join(participants) if participants else "None"
        
        return f"""## Task
{task_text}

## Available References
{available_refs}

## Participants
{participants_str}

## Instructions
Use the provided tools to query information you need (calendar events, policy rules, communication threads, etc.).
After gathering all necessary information, return a JSON object with a "candidates" key containing meeting slot objects.

For Level 1/2 tasks (no room assignment):
{{"candidates": [{{"start": "ISO8601_datetime", "end": "ISO8601_datetime"}}, ...]}}

For Level 3 tasks (with room assignment):
{{"candidates": [{{"start": "ISO8601_datetime", "end": "ISO8601_datetime", "room_id": "room_xxx"}}, ...]}}

Ensure all datetime strings include timezone offset (e.g., +09:00)."""

    def _parse_response(self, content: str) -> List[Candidate]:
        """
        Parse and validate the model's JSON response.
        
        Args:
            content: Raw JSON string from the model (may include markdown, text, etc.).
            
        Returns:
            List of candidate tuples.
            Returns empty list on parsing failure.
        """
        content = content.strip()
        data = None
        
        # Try regex extraction first: find first { to last }
        try:
            match = re.search(r"\{.*\}", content, re.DOTALL)
            if match:
                json_str = match.group(0)
                try:
                    data = json.loads(json_str)
                except json.JSONDecodeError:
                    # Try fixing trailing commas (common LLM mistake)
                    json_str_fixed = re.sub(r",\s*([}\]])", r"\1", json_str)
                    try:
                        data = json.loads(json_str_fixed)
                    except json.JSONDecodeError:
                        pass  # Will fallback below
        except Exception:
            pass  # Will fallback below
        
        # Fallback: try parsing original content
        if data is None:
            try:
                data = json.loads(content)
            except json.JSONDecodeError:
                # Silent mode - no print
                return []
        
        # Extract candidates list
        candidates_raw = data.get("candidates", [])
        
        if not isinstance(candidates_raw, list):
            print(f"[OpenAIAgent] 'candidates' is not a list: {type(candidates_raw)}")
            return []
        
        # Convert to tuples
        result: List[Candidate] = []
        
        for i, candidate in enumerate(candidates_raw):
            try:
                parsed = self._parse_candidate(candidate)
                if parsed is not None:
                    result.append(parsed)
            except Exception as e:
                print(f"[OpenAIAgent] Failed to parse candidate {i}: {e}")
                continue
        
        return result
    
    def _parse_candidate(self, candidate: Dict[str, Any]) -> Optional[Candidate]:
        """
        Parse a single candidate dict into a tuple.
        
        Args:
            candidate: Candidate dict with start, end, and optionally room_id.
            
        Returns:
            Tuple (start, end) or (start, end, room_id), or None if invalid.
        """
        if not isinstance(candidate, dict):
            print(f"[OpenAIAgent] Candidate is not a dict: {candidate}")
            return None
        
        start = candidate.get("start")
        end = candidate.get("end")
        
        if not start or not end:
            print(f"[OpenAIAgent] Missing start or end: {candidate}")
            return None
        
        # Ensure strings
        start = str(start)
        end = str(end)
        
        # Check for room_id (Level 3)
        room_id = candidate.get("room_id")
        
        if room_id is not None:
            return (start, end, str(room_id))
        else:
            return (start, end)
