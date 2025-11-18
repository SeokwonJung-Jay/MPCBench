"""Tool backend module for executing tool calls against local data files."""

import json
from pathlib import Path
from typing import Dict, Any, List


class ToolBackend:
    """
    Backend for executing tool calls against local JSON data files.
    
    Reads from generated data files (e.g., data/scenario_A_*.json) and performs
    scenario-agnostic operations. No hardcoded scenario-specific behavior.
    """
    
    def __init__(self, data_root: str = "data", scenario_id: str = "scenario_A"):
        """
        Initialize the tool backend.
        
        Args:
            data_root: Path to the data directory (default: "data")
            scenario_id: Scenario identifier (default: "scenario_A")
        """
        self.data_root = Path(data_root)
        self.scenario_id = scenario_id
        self._slack_data = None
        self._contacts_data = None
        self._calendar_data = None
        self._gmail_data = None
        self._jira_data = None
        self._drive_data = None
        self._world_state = None
    
    def _load_slack_data(self) -> Dict[str, Any]:
        """Lazy load Slack data."""
        if self._slack_data is None:
            slack_path = self.data_root / f"{self.scenario_id}_slack.json"
            if not slack_path.exists():
                # Fallback to old path for backward compatibility
                slack_path = self.data_root / "slack.json"
            with open(slack_path, 'r', encoding='utf-8') as f:
                self._slack_data = json.load(f)
        return self._slack_data
    
    def _load_contacts_data(self) -> Dict[str, Any]:
        """Lazy load Contacts data."""
        if self._contacts_data is None:
            contacts_path = self.data_root / f"{self.scenario_id}_contacts.json"
            if not contacts_path.exists():
                contacts_path = self.data_root / "contacts.json"
            with open(contacts_path, 'r', encoding='utf-8') as f:
                self._contacts_data = json.load(f)
        return self._contacts_data
    
    def _load_calendar_data(self) -> Dict[str, Any]:
        """Lazy load Calendar data."""
        if self._calendar_data is None:
            calendar_path = self.data_root / f"{self.scenario_id}_calendar.json"
            if not calendar_path.exists():
                calendar_path = self.data_root / "calendar.json"
            with open(calendar_path, 'r', encoding='utf-8') as f:
                self._calendar_data = json.load(f)
        return self._calendar_data
    
    def _load_gmail_data(self) -> Dict[str, Any]:
        """Lazy load Gmail data."""
        if self._gmail_data is None:
            gmail_path = self.data_root / f"{self.scenario_id}_gmail.json"
            if not gmail_path.exists():
                gmail_path = self.data_root / "gmail.json"
            with open(gmail_path, 'r', encoding='utf-8') as f:
                self._gmail_data = json.load(f)
        return self._gmail_data
    
    def _load_jira_data(self) -> Dict[str, Any]:
        """Lazy load Jira data."""
        if self._jira_data is None:
            jira_path = self.data_root / f"{self.scenario_id}_jira.json"
            if not jira_path.exists():
                jira_path = self.data_root / "jira.json"
            with open(jira_path, 'r', encoding='utf-8') as f:
                self._jira_data = json.load(f)
        return self._jira_data
    
    def _load_drive_data(self) -> Dict[str, Any]:
        """Lazy load Drive data."""
        if self._drive_data is None:
            drive_path = self.data_root / f"{self.scenario_id}_drive.json"
            if not drive_path.exists():
                drive_path = self.data_root / "drive.json"
            with open(drive_path, 'r', encoding='utf-8') as f:
                self._drive_data = json.load(f)
        return self._drive_data
    
    def _load_world_state(self) -> Dict[str, Any]:
        """Lazy load world_state."""
        if self._world_state is None:
            world_state_path = self.data_root / f"{self.scenario_id}_world_state.json"
            if not world_state_path.exists():
                world_state_path = self.data_root / "world_state.json"
            if world_state_path.exists():
                with open(world_state_path, 'r', encoding='utf-8') as f:
                    self._world_state = json.load(f)
            else:
                self._world_state = {}
        return self._world_state
    
    def call_slack_search_messages(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Search Slack messages using the search_query.
        
        Performs simple text matching on message content, channel names, and user info.
        No scenario-specific hardcoding - relies entirely on generated data.
        """
        slack_data = self._load_slack_data()
        messages = slack_data.get("messages", [])
        channels = {ch["id"]: ch["name"] for ch in slack_data.get("channels", [])}
        users = {u["id"]: u for u in slack_data.get("users", [])}
        
        search_query = arguments.get("search_query", "").lower()
        if not search_query:
            return {"matches": []}
        
        matches = []
        for msg in messages:
            channel_id = msg.get("channel_id")
            channel_name = channels.get(channel_id, "")
            user_id = msg.get("user_id", "")
            text = msg.get("text", "").lower()
            
            # Check if search_query matches message text, channel name, or user name
            user = users.get(user_id, {})
            user_name = user.get("name", "").lower()
            
            # Simple keyword matching: check if any word from query appears in text/channel/user
            query_words = search_query.split()
            matches_query = False
            
            for word in query_words:
                # Skip very common words
                if word in ["the", "a", "an", "and", "or", "from", "has", "with"]:
                    continue
                if word in text or word in channel_name.lower() or word in user_name:
                    matches_query = True
                    break
            
            if matches_query:
                matches.append({
                    "channel": channel_name,
                    "text": msg.get("text", ""),
                    "timestamp": msg.get("timestamp", "")
                })
        
        return {"matches": matches}
    
    def call_contacts_search_by_name(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Search contacts by name.
        
        Performs a case-insensitive substring match on contact names.
        """
        contacts_data = self._load_contacts_data()
        contacts = contacts_data.get("contacts", [])
        
        search_name = arguments.get("name", "").lower()
        if not search_name:
            return {"contacts": []}
        
        # Simple case-insensitive substring match
        matching_contacts = []
        for contact in contacts:
            contact_name = contact.get("name", "").lower()
            if search_name in contact_name or contact_name in search_name:
                # Return in the format expected by the API
                matching_contacts.append({
                    "name": contact.get("name", ""),
                    "emails": [contact.get("email", "")]
                })
        
        return {"contacts": matching_contacts}
    
    def call_calendar_find_time_slots(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Find time slots when everyone is free.
        
        Uses calendar events and world_state global_settings to determine availability.
        No hardcoded time slots - derives from generated data.
        """
        calendar_data = self._load_calendar_data()
        world_state = self._load_world_state()
        
        email_addresses = arguments.get("email_addresses", [])
        start_date = arguments.get("start_date", "")
        end_date = arguments.get("end_date", "")
        workday_start_time = arguments.get("workday_start_time", "09:00")
        workday_end_time = arguments.get("workday_end_time", "18:00")
        slot_minimum_minutes = arguments.get("slot_minimum_minutes", 30)
        
        # Get global settings from world_state if available
        global_settings = world_state.get("global_settings", {})
        if not workday_start_time:
            workday_start_time = global_settings.get("workday_start", "09:00")
        if not workday_end_time:
            workday_end_time = global_settings.get("workday_end", "18:00")
        
        # Get all events
        events = calendar_data.get("events", [])
        
        # Build email to person lookup
        people_by_email = {}
        for person in world_state.get("people", []):
            people_by_email[person.get("email", "")] = person
        
        # Find free time slots
        # For now, return a simple implementation that finds gaps between events
        # This is a simplified version - a full implementation would compute actual availability
        # based on event overlaps and working hours
        
        # If we have explicit availability in world_state.per_source_plans, use that
        per_source_plans = world_state.get("per_source_plans", {})
        calendar_plans = per_source_plans.get("calendar_plans", [])
        
        # Look for availability slots in plans
        time_slots = []
        for plan in calendar_plans:
            if plan.get("kind") == "availability_slot" or "availability" in plan.get("kind", "").lower():
                slot_start = plan.get("start")
                slot_end = plan.get("end")
                if slot_start and slot_end:
                    time_slots.append({
                        "start": slot_start,
                        "end": slot_end
                    })
        
        # If no explicit slots in plans, derive from events (simplified)
        # In a full implementation, this would compute actual free time
        if not time_slots:
            # Fallback: return empty or use a simple heuristic
            # For now, return empty to force LLM to be explicit in plans
            pass
        
        return {"time_slots": time_slots}
    
    def call_calendar_list_events(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Minimal backend for GoogleCalendar.ListEvents.
        
        Reads events from calendar.json and returns them, optionally filtered by a date range.
        
        Args:
            arguments: Dictionary with optional keys:
                - min_end_datetime: Minimum event end datetime (ISO string), inclusive
                - max_start_datetime: Maximum event start datetime (ISO string), exclusive
                - max_results: Maximum number of events to return
        
        Returns:
            Dictionary with "events" key containing list of event objects
        """
        calendar_data = self._load_calendar_data()
        events = calendar_data.get("events", [])
        
        # Get filter parameters
        min_end_datetime = arguments.get("min_end_datetime")
        max_start_datetime = arguments.get("max_start_datetime")
        max_results = arguments.get("max_results")
        
        # Filter events by date range if provided
        filtered_events = []
        for event in events:
            event_start = event.get("start", "")
            event_end = event.get("end", "")
            
            # Check min_end_datetime: event.end >= min_end_datetime
            if min_end_datetime:
                if event_end < min_end_datetime:
                    continue
            
            # Check max_start_datetime: event.start < max_start_datetime
            if max_start_datetime:
                if event_start >= max_start_datetime:
                    continue
            
            filtered_events.append(event)
        
        # Apply max_results limit if specified
        if max_results is not None and max_results > 0:
            filtered_events = filtered_events[:max_results]
        
        return {"events": filtered_events}
    
    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Dispatch tool calls to the appropriate method.
        
        Args:
            tool_name: Name of the tool (e.g., "Slack.search_messages")
            arguments: Dictionary of tool arguments
            
        Returns:
            Dictionary representing the tool result
        """
        if tool_name == "Slack.search_messages":
            return self.call_slack_search_messages(arguments)
        elif tool_name == "GoogleContacts.SearchContactsByName":
            return self.call_contacts_search_by_name(arguments)
        elif tool_name == "GoogleCalendar.FindTimeSlotsWhenEveryoneIsFree":
            return self.call_calendar_find_time_slots(arguments)
        elif tool_name == "GoogleCalendar.ListEvents":
            return self.call_calendar_list_events(arguments)
        else:
            raise ValueError(f"Unknown tool: {tool_name}")

