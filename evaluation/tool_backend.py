"""Tool backend module for executing tool calls against local data files."""

import json
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime, timedelta
import re


class ToolBackend:
    """
    Backend for executing tool calls against local JSON data files.
    
    Reads from generated data files (e.g., data/{scenario_id}_*.json) and performs
    scenario-agnostic operations. No hardcoded scenario-specific behavior.
    """
    
    def __init__(self, data_root: str = "data", scenario_id: str = None):
        """
        Initialize the tool backend.
        
        Args:
            data_root: Path to the data directory (default: "data")
            scenario_id: Scenario identifier (required, no default)
            
        Raises:
            ValueError: If scenario_id is not provided
        """
        if not scenario_id:
            raise ValueError("scenario_id is required and cannot be None or empty")
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
        
        Uses calendar events to compute actual free time slots by analyzing
        event overlaps and working hours. No LLM or per_source_plans dependency.
        """
        calendar_data = self._load_calendar_data()
        world_state = self._load_world_state()
        
        email_addresses = arguments.get("email_addresses", [])
        date_range_start = arguments.get("date_range_start", "")
        date_range_end = arguments.get("date_range_end", "")
        workday_start_time = arguments.get("workday_start_time", "09:00")
        workday_end_time = arguments.get("workday_end_time", "18:00")
        slot_minimum_minutes = arguments.get("slot_minimum_minutes", 30)
        
        if not email_addresses:
            return {"time_slots": []}
        
        # Get global settings from world_state if available
        global_settings = world_state.get("global_settings", {})
        if not workday_start_time:
            workday_start_time = global_settings.get("workday_start", "09:00")
        if not workday_end_time:
            workday_end_time = global_settings.get("workday_end", "18:00")
        
        # Parse workday times (HH:MM format)
        workday_start_hour, workday_start_min = map(int, workday_start_time.split(":"))
        workday_end_hour, workday_end_min = map(int, workday_end_time.split(":"))
        
        # Get all events
        events = calendar_data.get("events", [])
        
        # Build busy time ranges for each email
        # Format: {email: [(start_dt, end_dt), ...]}
        busy_times_by_email: Dict[str, List[tuple]] = {email: [] for email in email_addresses}
        
        for event in events:
            event_start_str = event.get("start", "")
            event_end_str = event.get("end", "")
            if not event_start_str or not event_end_str:
                continue
            
            # Parse ISO datetime strings
            try:
                # Handle timezone offset (e.g., +09:00)
                event_start_dt = datetime.fromisoformat(event_start_str.replace('Z', '+00:00'))
                event_end_dt = datetime.fromisoformat(event_end_str.replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                continue
            
            # Check which participants are in this event
            attendees = event.get("attendees", [])
            attendee_emails = {a.get("email", "") for a in attendees if a.get("email")}
            
            # Add this event to busy times for matching participants
            for email in email_addresses:
                if email in attendee_emails:
                    busy_times_by_email[email].append((event_start_dt, event_end_dt))
        
        # Sort busy times for each email
        for email in email_addresses:
            busy_times_by_email[email].sort(key=lambda x: x[0])
        
        # Determine timezone from events (use first event's timezone if available)
        tzinfo = None
        if events:
            first_event_start = events[0].get("start", "")
            if first_event_start:
                try:
                    first_dt = datetime.fromisoformat(first_event_start.replace('Z', '+00:00'))
                    tzinfo = first_dt.tzinfo
                except (ValueError, AttributeError):
                    pass
        
        # Parse date range
        try:
            if date_range_start:
                # If date_range_start is just a date (YYYY-MM-DD), add time
                if len(date_range_start) == 10:
                    date_range_start = f"{date_range_start}T00:00:00"
                range_start_dt = datetime.fromisoformat(date_range_start.replace('Z', '+00:00'))
                if tzinfo and not range_start_dt.tzinfo:
                    range_start_dt = range_start_dt.replace(tzinfo=tzinfo)
            else:
                range_start_dt = None
            if date_range_end:
                # If date_range_end is just a date (YYYY-MM-DD), add time
                if len(date_range_end) == 10:
                    date_range_end = f"{date_range_end}T23:59:59"
                range_end_dt = datetime.fromisoformat(date_range_end.replace('Z', '+00:00'))
                if tzinfo and not range_end_dt.tzinfo:
                    range_end_dt = range_end_dt.replace(tzinfo=tzinfo)
            else:
                range_end_dt = None
        except (ValueError, AttributeError):
            return {"time_slots": []}
        
        # Find common free slots
        time_slots = []
        
        # Iterate day by day
        current_date = range_start_dt.date() if range_start_dt else datetime.now().date()
        end_date = range_end_dt.date() if range_end_dt else current_date + timedelta(days=7)
        
        while current_date <= end_date:
            # Build workday time range for this date
            day_start = datetime.combine(current_date, datetime.min.time()).replace(
                hour=workday_start_hour, minute=workday_start_min
            )
            day_end = datetime.combine(current_date, datetime.min.time()).replace(
                hour=workday_end_hour, minute=workday_end_min
            )
            
            # Apply timezone if available
            if tzinfo:
                day_start = day_start.replace(tzinfo=tzinfo)
                day_end = day_end.replace(tzinfo=tzinfo)
            
            # Get busy times for this day for all participants
            day_busy_ranges = []
            for email in email_addresses:
                for busy_start, busy_end in busy_times_by_email[email]:
                    # Only consider events on this day
                    if busy_start.date() == current_date or busy_end.date() == current_date:
                        # Clip to workday hours
                        clip_start = max(busy_start, day_start)
                        clip_end = min(busy_end, day_end)
                        if clip_start < clip_end:
                            day_busy_ranges.append((clip_start, clip_end))
            
            # Merge overlapping busy ranges
            if day_busy_ranges:
                day_busy_ranges.sort(key=lambda x: x[0])
                merged_busy = []
                for start, end in day_busy_ranges:
                    if merged_busy and start <= merged_busy[-1][1]:
                        # Merge with previous range
                        merged_busy[-1] = (merged_busy[-1][0], max(merged_busy[-1][1], end))
                    else:
                        merged_busy.append((start, end))
            else:
                merged_busy = []
            
            # Find free slots between busy ranges
            current_time = day_start
            for busy_start, busy_end in merged_busy:
                # Check if there's a free slot before this busy period
                if current_time < busy_start:
                    slot_duration = (busy_start - current_time).total_seconds() / 60
                    if slot_duration >= slot_minimum_minutes:
                        time_slots.append({
                            "start": current_time.isoformat(),
                            "end": busy_start.isoformat()
                        })
                current_time = max(current_time, busy_end)
            
            # Check if there's a free slot after the last busy period
            if current_time < day_end:
                slot_duration = (day_end - current_time).total_seconds() / 60
                if slot_duration >= slot_minimum_minutes:
                    time_slots.append({
                        "start": current_time.isoformat(),
                        "end": day_end.isoformat()
                    })
            
            current_date += timedelta(days=1)
        
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
    
    def call_gmail_search_threads(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Search Gmail threads by subject, sender, or date range.
        
        Performs case-insensitive substring matching on thread subjects and
        sender email addresses. Filters by date range if provided.
        """
        gmail_data = self._load_gmail_data()
        threads = gmail_data.get("threads", [])
        
        subject_filter = arguments.get("subject", "").lower() if arguments.get("subject") else None
        sender_filter = arguments.get("sender", "").lower() if arguments.get("sender") else None
        date_range = arguments.get("date_range", "")
        
        matching_thread_ids = []
        
        for thread in threads:
            # Check subject match
            if subject_filter:
                thread_subject = thread.get("subject", "").lower()
                if subject_filter not in thread_subject:
                    continue
            
            # Check sender match (first message's from field)
            if sender_filter:
                messages = thread.get("messages", [])
                if not messages:
                    continue
                first_message_from = messages[0].get("from", "").lower()
                if sender_filter not in first_message_from:
                    continue
            
            # Check date range (simplified: check first message date)
            if date_range:
                messages = thread.get("messages", [])
                if not messages:
                    continue
                first_message_date = messages[0].get("date", "")
                # Simple date range matching (e.g., "last_30_days")
                # For now, just check if date_range is specified, actual date parsing can be enhanced
                # This is a simplified implementation
                pass
            
            matching_thread_ids.append(thread.get("id", ""))
        
        return {"thread_ids": matching_thread_ids}
    
    def call_gmail_get_thread(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get a full Gmail thread by thread ID.
        
        Returns the complete thread with all messages.
        """
        gmail_data = self._load_gmail_data()
        threads = gmail_data.get("threads", [])
        
        thread_id = arguments.get("thread_id", "")
        if not thread_id:
            return {"thread": None}
        
        for thread in threads:
            if thread.get("id") == thread_id:
                return {"thread": thread}
        
        return {"thread": None}
    
    def call_drive_search(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Search Google Drive files by name or content.
        
        Performs case-insensitive substring matching on file names and content.
        """
        drive_data = self._load_drive_data()
        files = drive_data.get("files", [])
        
        query = arguments.get("query", "").lower()
        limit = arguments.get("limit")
        
        if not query:
            return {"files": []}
        
        matching_files = []
        for file in files:
            file_name = file.get("name", "").lower()
            file_content = file.get("content", "").lower()
            
            if query in file_name or query in file_content:
                matching_files.append({
                    "id": file.get("id", ""),
                    "name": file.get("name", ""),
                    "mimeType": file.get("mimeType", "")
                })
        
        # Apply limit if specified
        if limit is not None and limit > 0:
            matching_files = matching_files[:limit]
        
        return {"files": matching_files}
    
    def call_drive_read_file(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Read the content of a Google Drive file by file ID.
        
        Returns the file metadata and content.
        """
        drive_data = self._load_drive_data()
        files = drive_data.get("files", [])
        
        file_id = arguments.get("file_id", "")
        if not file_id:
            return {"file": None}
        
        for file in files:
            if file.get("id") == file_id:
                return {
                    "file": {
                        "id": file.get("id", ""),
                        "name": file.get("name", ""),
                        "content": file.get("content", "")
                    }
                }
        
        return {"file": None}
    
    def call_jira_search_issues_with_jql(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Search Jira issues using a simplified JQL parser.
        
        Supports basic JQL patterns:
        - project = KEY
        - status = "Status"
        - text ~ "keyword" (searches summary)
        - ORDER BY updated DESC/ASC
        
        This is a simplified implementation that handles common patterns.
        """
        jira_data = self._load_jira_data()
        issues = jira_data.get("issues", [])
        
        jql = arguments.get("jql", "")
        if not jql:
            return {"issues": []}
        
        # Parse JQL (simplified)
        filtered_issues = issues.copy()
        
        # Extract project filter: project = KEY
        project_match = re.search(r'project\s*=\s*(\w+)', jql, re.IGNORECASE)
        if project_match:
            project_key = project_match.group(1)
            filtered_issues = [
                issue for issue in filtered_issues
                if issue.get("project", {}).get("key", "") == project_key
            ]
        
        # Extract status filter: status = "Status"
        status_match = re.search(r'status\s*=\s*"([^"]+)"', jql, re.IGNORECASE)
        if status_match:
            status_value = status_match.group(1)
            filtered_issues = [
                issue for issue in filtered_issues
                if issue.get("status", "") == status_value
            ]
        
        # Extract text search: text ~ "keyword"
        text_match = re.search(r'text\s*~\s*"([^"]+)"', jql, re.IGNORECASE)
        if text_match:
            keyword = text_match.group(1).lower()
            filtered_issues = [
                issue for issue in filtered_issues
                if keyword in issue.get("summary", "").lower()
            ]
        
        # Extract ORDER BY clause
        order_match = re.search(r'ORDER\s+BY\s+(\w+)\s+(DESC|ASC)', jql, re.IGNORECASE)
        if order_match:
            order_field = order_match.group(1).lower()
            order_direction = order_match.group(2).upper()
            
            if order_field == "updated":
                reverse = (order_direction == "DESC")
                filtered_issues.sort(
                    key=lambda x: x.get("updated", ""),
                    reverse=reverse
                )
        
        # Format output (include required fields)
        result_issues = []
        for issue in filtered_issues:
            result_issues.append({
                "key": issue.get("key", ""),
                "summary": issue.get("summary", ""),
                "status": issue.get("status", ""),
                "updated": issue.get("updated", ""),
                "fixVersions": issue.get("fixVersions", []),
                "project": issue.get("project", {})
            })
        
        return {"issues": result_issues}
    
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
        elif tool_name == "Gmail.SearchThreads":
            return self.call_gmail_search_threads(arguments)
        elif tool_name == "Gmail.GetThread":
            return self.call_gmail_get_thread(arguments)
        elif tool_name == "GoogleDrive.gdrive_search":
            return self.call_drive_search(arguments)
        elif tool_name == "GoogleDrive.gdrive_read_file":
            return self.call_drive_read_file(arguments)
        elif tool_name == "Jira.SearchIssuesWithJql":
            return self.call_jira_search_issues_with_jql(arguments)
        else:
            raise ValueError(f"Unknown tool: {tool_name}")

