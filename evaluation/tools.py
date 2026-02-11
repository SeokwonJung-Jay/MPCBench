"""
Simulated API tools for MPCBench evaluation.

Provides a simulated API interface that agents can use to query world and instance data.
"""

from typing import Any, Dict, List, Optional

try:
    from zoneinfo import ZoneInfo
except ImportError:
    # Fallback for Python < 3.9
    from backports.zoneinfo import ZoneInfo


class SimulatedAPI:
    """
    Simulated API for agent tool calls.
    
    Provides methods to query world and instance data in a structured way.
    """
    
    def __init__(self, world: dict, instance: dict):
        """
        Initialize the simulated API with world and instance data.
        
        Args:
            world: World data dict (from world_level*.json).
            instance: Instance data dict (from instances_level*.jsonl).
        """
        self.world = world
        self.instance = instance
        self.level = world.get("level", instance.get("level", 1))
        self.timezone_str = world.get("timezone", "Asia/Seoul")
    
    def _inject_timezone(self, dt_str: str) -> str:
        """
        Inject timezone offset into datetime string if missing.
        
        Args:
            dt_str: Datetime string (may or may not have timezone offset).
            
        Returns:
            Datetime string with timezone offset (e.g., +09:00).
        """
        if not dt_str:
            return dt_str
        
        # Check if already has timezone offset
        # Pattern: ends with +HH:MM, -HH:MM, or Z
        if dt_str.endswith("Z"):
            return dt_str  # UTC
        
        # Check if ends with offset pattern (+/-HH:MM)
        if len(dt_str) >= 6:
            last_6 = dt_str[-6:]
            if (last_6.startswith("+") or last_6.startswith("-")) and ":" in last_6:
                # Already has offset
                return dt_str
        
        # Get timezone offset
        try:
            tz = ZoneInfo(self.timezone_str)
            # Get UTC offset for a reference datetime
            from datetime import datetime
            ref_dt = datetime(2026, 1, 1, tzinfo=tz)
            offset = ref_dt.utcoffset()
            
            if offset:
                # Format offset as +HH:MM or -HH:MM
                total_seconds = int(offset.total_seconds())
                hours = total_seconds // 3600
                minutes = abs((total_seconds % 3600) // 60)
                sign = "+" if total_seconds >= 0 else "-"
                offset_str = f"{sign}{abs(hours):02d}:{minutes:02d}"
                return f"{dt_str}{offset_str}"
        except Exception:
            # Fallback: use common timezone mappings
            tz_mapping = {
                "Asia/Seoul": "+09:00",
                "UTC": "+00:00",
                "America/New_York": "-05:00",
                "America/Los_Angeles": "-08:00",
                "Europe/London": "+00:00",
                "Europe/Paris": "+01:00",
                "Asia/Tokyo": "+09:00",
            }
            offset_str = tz_mapping.get(self.timezone_str, "+00:00")
            return f"{dt_str}{offset_str}"
        
        return dt_str
    
    def get_current_time(self) -> Dict[str, Any]:
        """
        Get the current time for this evaluation context.
        
        Returns:
            Dict with "current_time" (ISO datetime string with timezone offset).
        """
        # Use instance time_window start or world_start as "current time"
        time_window = self.instance.get("slots", {}).get("time_window", {})
        current_time = time_window.get("start")
        
        if not current_time:
            current_time = self.world.get("world_start")
        
        # Inject timezone if missing
        if current_time:
            current_time = self._inject_timezone(current_time)
        
        return {
            "current_time": current_time or "",
            "timezone": self.timezone_str
        }
    
    def get_calendar_events(self, person_id: str) -> Dict[str, Any]:
        """
        Get calendar events (busy intervals) for a person.
        
        Args:
            person_id: Person identifier (e.g., "person_001").
            
        Returns:
            Dict with "person_id" and "events" (list of busy events with timezone offsets).
        """
        calendar_json = self.world.get("sources", {}).get("calendar_json", {})
        events = calendar_json.get(person_id, [])
        
        if not isinstance(events, list):
            events = []
        
        # Inject timezone into event datetime fields
        processed_events = []
        for event in events:
            if isinstance(event, dict):
                processed_event = event.copy()
                if "start" in processed_event:
                    processed_event["start"] = self._inject_timezone(processed_event["start"])
                if "end" in processed_event:
                    processed_event["end"] = self._inject_timezone(processed_event["end"])
                processed_events.append(processed_event)
            else:
                processed_events.append(event)
        
        return {
            "person_id": person_id,
            "events": processed_events
        }
    
    def get_policy_rules(self, policy_id: str) -> Dict[str, Any]:
        """
        Get policy rules for a given policy ID (Level 1 only).
        
        Args:
            policy_id: Policy identifier (e.g., "POLICY_1").
            
        Returns:
            Dict with "policy_id" and "rules" (list of rule objects).
        """
        policy_json = self.world.get("sources", {}).get("policy_json", {})
        policy_data = policy_json.get(policy_id, {})
        rules = policy_data.get("rules", [])
        
        return {
            "policy_id": policy_id,
            "rules": rules if isinstance(rules, list) else []
        }
    
    def list_policy_ids(self) -> Dict[str, Any]:
        """
        List available structured policy rule IDs (Level 1 only).
        
        Returns:
            Dict with "policy_ids" (list of available policy IDs).
        """
        policy_json = self.world.get("sources", {}).get("policy_json", {})
        
        if isinstance(policy_json, dict):
            return {"policy_ids": list(policy_json.keys())}
        
        return {"policy_ids": []}
    
    def list_document_ids(self) -> Dict[str, Any]:
        """
        List available policy document IDs (Level 2/3 only).
        
        Returns:
            Dict with "document_ids" (list of available document IDs).
        """
        policy_text = self.world.get("sources", {}).get("policy_text", {})
        
        # If policy_text is a dict, return its keys
        if isinstance(policy_text, dict):
            return {"document_ids": list(policy_text.keys())}
        
        # If policy_text is a string, return virtual ID
        if isinstance(policy_text, str) and policy_text:
            return {"document_ids": ["primary_policy_doc"]}
        
        return {"document_ids": []}
    
    def list_thread_ids(self) -> Dict[str, Any]:
        """
        List available communication thread IDs (Level 2/3 only).
        
        Returns:
            Dict with "thread_ids" (list of available thread IDs).
        """
        # Check instance sources first
        instance_sources = self.instance.get("sources", {})
        comm_threads = instance_sources.get("comm_threads", [])
        
        # If not in instance, check world sources
        if not comm_threads:
            world_sources = self.world.get("sources", {})
            comm_threads = world_sources.get("comm_threads", [])
        
        # If comm_threads is a list, extract thread_ids
        if isinstance(comm_threads, list):
            thread_ids = []
            for thread in comm_threads:
                if isinstance(thread, dict) and thread.get("thread_id"):
                    thread_ids.append(thread["thread_id"])
            if thread_ids:
                return {"thread_ids": thread_ids}
        
        # Check for comm_thread_text as string (fallback)
        comm_thread_text = instance_sources.get("comm_thread_text", "")
        if not comm_thread_text:
            comm_thread_text = self.world.get("sources", {}).get("comm_thread_text", "")
        
        if isinstance(comm_thread_text, str) and comm_thread_text:
            return {"thread_ids": ["primary_thread"]}
        
        return {"thread_ids": []}
    
    def read_policy_document(self, doc_id: str) -> Dict[str, Any]:
        """
        Read policy document text (Level 2/3 only).
        You MUST obtain the ID via list_document_ids first.
        
        Args:
            doc_id: Document identifier (obtained from list_document_ids).
            
        Returns:
            Dict with "doc_id", "title", and "text" (policy text content).
        """
        policy_text = self.world.get("sources", {}).get("policy_text", {})
        
        # If policy_text is a dict with doc_id key (new structure)
        if isinstance(policy_text, dict):
            doc_data = policy_text.get(doc_id, {})
            if doc_data:
                return {
                    "doc_id": doc_id,
                    "title": doc_data.get("title", ""),
                    "text": doc_data.get("text", "")
                }
            else:
                return {
                    "doc_id": doc_id,
                    "error": f"Document '{doc_id}' not found. Use list_document_ids() to see available documents."
                }
        
        # If policy_text is a string (legacy single document) and virtual ID matches
        if isinstance(policy_text, str):
            if doc_id == "primary_policy_doc":
                return {
                    "doc_id": doc_id,
                    "title": "Company Policy Document",
                    "text": policy_text
                }
        
        return {
            "doc_id": doc_id,
            "error": f"Document '{doc_id}' not found."
        }
    
    def read_communication_thread(self, thread_id: str) -> Dict[str, Any]:
        """
        Read a communication thread (Level 2/3 only).
        You MUST obtain the ID via list_thread_ids first.
        
        Args:
            thread_id: Thread identifier (obtained from list_thread_ids).
            
        Returns:
            Dict with "thread_id", "text" (thread text), and "tags" (if available).
        """
        # Check instance sources first
        instance_sources = self.instance.get("sources", {})
        comm_threads = instance_sources.get("comm_threads", [])
        
        # If not in instance, check world sources
        if not comm_threads:
            world_sources = self.world.get("sources", {})
            comm_threads = world_sources.get("comm_threads", [])
        
        # Search for thread in list
        if isinstance(comm_threads, list):
            for thread in comm_threads:
                if isinstance(thread, dict) and thread.get("thread_id") == thread_id:
                    return {
                        "thread_id": thread_id,
                        "text": thread.get("thread_text", thread.get("text", "")),
                        "tags": thread.get("thread_tags", thread.get("tags", {}))
                    }
        
        # Handle virtual "primary_thread" ID for string-based comm_thread_text
        if thread_id == "primary_thread":
            comm_thread_text = instance_sources.get("comm_thread_text", "")
            if not comm_thread_text:
                comm_thread_text = self.world.get("sources", {}).get("comm_thread_text", "")
            
            if isinstance(comm_thread_text, str) and comm_thread_text:
                return {
                    "thread_id": thread_id,
                    "text": comm_thread_text,
                    "tags": {}
                }
        
        return {
            "thread_id": thread_id,
            "text": "",
            "tags": {}
        }
    
    def search_person(self, name_query: str) -> Dict[str, Any]:
        """
        Search for a person by name (Level 3 only).
        
        Args:
            name_query: Name or partial name to search for.
            
        Returns:
            Dict with "matches" (list of matching person records).
        """
        people_table = self.world.get("sources", {}).get("people_table", {})
        rows = people_table.get("rows", [])
        
        if not isinstance(rows, list):
            return {"matches": []}
        
        # Case-insensitive search
        name_query_lower = name_query.lower()
        matches = []
        
        for row in rows:
            person_name = row.get("person_name", "")
            if name_query_lower in person_name.lower():
                matches.append(row)
        
        return {"matches": matches}
    
    def list_rooms(self, min_capacity: int = 0) -> Dict[str, Any]:
        """
        List rooms filtered by minimum capacity (Level 3 only).
        
        Args:
            min_capacity: Minimum room capacity (default: 0).
            
        Returns:
            Dict with "rooms" (list of room records matching criteria).
        """
        rooms_table = self.world.get("sources", {}).get("rooms_table", {})
        rows = rooms_table.get("rows", [])
        
        if not isinstance(rows, list):
            return {"rooms": []}
        
        filtered_rooms = []
        for row in rows:
            capacity = row.get("capacity", 0)
            if isinstance(capacity, (int, float)) and capacity >= min_capacity:
                filtered_rooms.append(row)
        
        return {"rooms": filtered_rooms}
    
    def get_room_availability(self, room_id: str) -> Dict[str, Any]:
        """
        Get room availability (busy intervals) for a room (Level 3 only).
        
        Args:
            room_id: Room identifier (e.g., "room_001").
            
        Returns:
            Dict with "room_id" and "events" (list of busy events with timezone offsets).
        """
        room_availability_json = self.world.get("sources", {}).get("room_availability_json", {})
        events = room_availability_json.get(room_id, [])
        
        if not isinstance(events, list):
            events = []
        
        # Inject timezone into event datetime fields
        processed_events = []
        for event in events:
            if isinstance(event, dict):
                processed_event = event.copy()
                if "start" in processed_event:
                    processed_event["start"] = self._inject_timezone(processed_event["start"])
                if "end" in processed_event:
                    processed_event["end"] = self._inject_timezone(processed_event["end"])
                processed_events.append(processed_event)
            else:
                processed_events.append(event)
        
        return {
            "room_id": room_id,
            "events": processed_events
        }
    
    @staticmethod
    def get_tool_definitions() -> List[Dict[str, Any]]:
        """
        Generate OpenAI-compatible tool definitions (JSON Schema format).
        
        Returns:
            List of tool definition dicts for OpenAI API.
        """
        return [
            {
                "type": "function",
                "function": {
                    "name": "get_current_time",
                    "description": "Get the current time for this evaluation context.",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_calendar_events",
                    "description": "Get calendar events (busy intervals) for a person by person_id.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "person_id": {
                                "type": "string",
                                "description": "Person identifier (e.g., 'person_001')"
                            }
                        },
                        "required": ["person_id"]
                    }
                }
            },
            # Policy discovery and read tools
            {
                "type": "function",
                "function": {
                    "name": "list_policy_ids",
                    "description": "List available structured policy rule IDs (Level 1 only). Use this to discover which policy_id values are available before calling get_policy_rules.",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_policy_rules",
                    "description": "Get policy rules for a given policy ID (Level 1 only). Returns machine-readable policy rules. You MUST obtain the ID via list_policy_ids first.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "policy_id": {
                                "type": "string",
                                "description": "Policy identifier (e.g., 'POLICY_1')"
                            }
                        },
                        "required": ["policy_id"]
                    }
                }
            },
            # Document discovery and read tools
            {
                "type": "function",
                "function": {
                    "name": "list_document_ids",
                    "description": "List available policy document IDs (Level 2/3 only). Use this to discover which doc_id values are available before calling read_policy_document.",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "read_policy_document",
                    "description": "Read policy document text (Level 2/3 only). Returns the policy text document. You MUST obtain the ID via list_document_ids first.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "doc_id": {
                                "type": "string",
                                "description": "Document identifier (obtained from list_document_ids)"
                            }
                        },
                        "required": ["doc_id"]
                    }
                }
            },
            # Thread discovery and read tools
            {
                "type": "function",
                "function": {
                    "name": "list_thread_ids",
                    "description": "List available communication thread IDs (Level 2/3 only). Use this to discover which thread_id values are available before calling read_communication_thread.",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "read_communication_thread",
                    "description": "Read a communication thread by thread_id (Level 2/3 only). Returns thread text and metadata. You MUST obtain the ID via list_thread_ids first.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "thread_id": {
                                "type": "string",
                                "description": "Thread identifier (obtained from list_thread_ids)"
                            }
                        },
                        "required": ["thread_id"]
                    }
                }
            },
            # Person search tools
            {
                "type": "function",
                "function": {
                    "name": "search_person",
                    "description": "Search for a person by name (Level 3 only). Returns matching person records with person_id and person_name.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name_query": {
                                "type": "string",
                                "description": "Name or partial name to search for"
                            }
                        },
                        "required": ["name_query"]
                    }
                }
            },
            # Room discovery and availability tools
            {
                "type": "function",
                "function": {
                    "name": "list_rooms",
                    "description": "List rooms filtered by minimum capacity (Level 3 only). Returns room records with room_id, capacity, and other metadata.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "min_capacity": {
                                "type": "integer",
                                "description": "Minimum room capacity (default: 0)",
                                "default": 0
                            }
                        },
                        "required": []
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_room_availability",
                    "description": "Get room availability (busy intervals) for a room by room_id (Level 3 only). You MUST obtain the ID via list_rooms first.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "room_id": {
                                "type": "string",
                                "description": "Room identifier (e.g., 'room_001')"
                            }
                        },
                        "required": ["room_id"]
                    }
                }
            }
        ]
    
    def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a tool call by name and arguments.
        
        Args:
            tool_name: Name of the tool to execute.
            arguments: Arguments dict for the tool.
            
        Returns:
            Tool execution result dict.
        """
        method_map = {
            "get_current_time": self.get_current_time,
            "get_calendar_events": self.get_calendar_events,
            # Policy tools
            "list_policy_ids": self.list_policy_ids,
            "get_policy_rules": self.get_policy_rules,
            # Document tools
            "list_document_ids": self.list_document_ids,
            "read_policy_document": self.read_policy_document,
            # Thread tools
            "list_thread_ids": self.list_thread_ids,
            "read_communication_thread": self.read_communication_thread,
            # Person tools
            "search_person": self.search_person,
            # Room tools
            "list_rooms": self.list_rooms,
            "get_room_availability": self.get_room_availability,
        }
        
        method = method_map.get(tool_name)
        if not method:
            return {"error": f"Unknown tool: {tool_name}"}
        
        try:
            # Call method with unpacked arguments
            result = method(**arguments)
            return result
        except Exception as e:
            return {"error": f"Tool execution failed: {str(e)}"}
