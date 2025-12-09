"""Tool backend for MPCBench v2.

Exposes generated source data as tools to the agent.
"""

from typing import Dict, Any, List, Optional, Union
from pathlib import Path
import json


class ToolBackend:
    """Backend that provides tool interfaces to source data."""

    def __init__(self, source_data: Dict[str, Path]):
        """
        Initialize tool backend with source data paths.
        
        Args:
            source_data: Dictionary mapping source names to file paths
        """
        self.source_data = source_data
        self._loaded_data = {}

    def _load_source(self, source_name: str) -> Dict[str, Any]:
        """Lazy load a source data file."""
        if source_name not in self._loaded_data:
            if source_name in self.source_data:
                with open(self.source_data[source_name], 'r', encoding='utf-8') as f:
                    self._loaded_data[source_name] = json.load(f)
            else:
                self._loaded_data[source_name] = {}
        return self._loaded_data[source_name]

    def calendar_list_events(
        self,
        email_addresses: List[str],
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        List calendar events for given email addresses.
        
        Similar to Google Calendar API events.list endpoint.
        
        Args:
            email_addresses: List of email addresses to check
            start_date: Optional start date filter (YYYY-MM-DD)
            end_date: Optional end date filter (YYYY-MM-DD)
            
        Returns:
            Dictionary with "events" list, each event has:
            - email: Email address
            - date: Date (YYYY-MM-DD)
            - slot: Time slot (HH:MM-HH:MM)
            - busy: Boolean indicating if busy
        """
        calendar_data = self._load_source("calendar")
        events = calendar_data.get("events", [])
        
        # Filter by email addresses
        filtered_events = [
            e for e in events
            if e.get("email") in email_addresses
        ]
        
        # Filter by date range if provided
        if start_date or end_date:
            date_filtered = []
            for event in filtered_events:
                event_date = event.get("date", "")
                if start_date and event_date < start_date:
                    continue
                if end_date and event_date > end_date:
                    continue
                date_filtered.append(event)
            filtered_events = date_filtered
        
        return {"events": filtered_events}

    def calendar_query_freebusy(
        self,
        email_addresses: List[str],
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        duration_minutes: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Query common free time slots for multiple email addresses.
        
        Similar to Google Calendar API freebusy.query endpoint.
        Internally calls calendar_list_events() to get events, then calculates
        common free time slots.
        
        Args:
            email_addresses: List of email addresses to check
            start_date: Optional start date filter (YYYY-MM-DD)
            end_date: Optional end date filter (YYYY-MM-DD)
            duration_minutes: Minimum duration in minutes (optional, currently ignored)
            
        Returns:
            Dictionary with "time_slots" list, each slot has:
            - date: Date (YYYY-MM-DD)
            - slot: Time slot (HH:MM-HH:MM)
            - participants: List of email addresses
        """
        # Internally call calendar_list_events to get events
        events_result = self.calendar_list_events(
            email_addresses=email_addresses,
            start_date=start_date,
            end_date=end_date
        )
        events = events_result.get("events", [])
        
        # Group events by (date, slot) pairs
        slot_map = {}  # (date, slot) -> {email: busy}
        for event in events:
            date = event.get("date")
            slot = event.get("slot")
            email = event.get("email")
            busy = event.get("busy", True)
            
            if not date or not slot or not email:
                continue
            
            key = (date, slot)
            if key not in slot_map:
                slot_map[key] = {}
            slot_map[key][email] = busy
        
        # Find slots where all requested emails are free
        free_slots = []
        for (date, slot), email_status in slot_map.items():
            # Check if all requested emails are free
            all_free = True
            for email in email_addresses:
                if email not in email_status:
                    # No event for this email - assume free
                    continue
                if email_status[email]:
                    # This email is busy
                    all_free = False
                    break
            
            if all_free:
                free_slots.append({
                    "date": date,
                    "slot": slot,
                    "participants": email_addresses
                })
        
        return {"time_slots": free_slots}

    def slack_list_channels(self) -> Dict[str, Any]:
        """
        List Slack channels.
        
        Similar to Slack API conversations.list endpoint.
        
        Returns:
            Dictionary with "channels" list, each channel has:
            - channel_id: Channel identifier
            - name: Channel name
            - description: Channel description
        """
        slack_data = self._load_source("slack")
        channels = slack_data.get("channels", [])
        
        # If channels array exists, return it directly
        if channels:
            return {"channels": channels}
        
        # Fallback: extract from messages (backward compatibility)
        messages = slack_data.get("messages", [])
        channels_set = set()
        for msg in messages:
            channel = msg.get("channel", "")
            if channel:
                channels_set.add(channel)
        
        # Convert to list of channel dicts
        channels = [{"channel_id": ch, "name": ch} for ch in sorted(channels_set)]
        
        return {"channels": channels}

    def slack_list_messages(self, channel_id: Optional[str] = None, limit: Optional[int] = None) -> Dict[str, Any]:
        """
        List Slack messages, optionally filtered by channel_id.
        
        Similar to Slack API conversations.history endpoint.
        
        Args:
            channel_id: Optional channel identifier to filter messages. If not provided, returns messages from all channels.
            limit: Optional maximum number of results
            
        Returns:
            Dictionary with "messages" list, each message has:
            - message_id: Message identifier (format: "channel:index")
            - channel_id: Channel identifier
            - text: Message text
            - user: User who sent the message
            - timestamp: Message timestamp
        """
        slack_data = self._load_source("slack")
        messages = slack_data.get("messages", [])
        
        # Filter by channel_id if provided
        if channel_id:
            filtered_messages = [msg for msg in messages if msg.get("channel") == channel_id]
        else:
            filtered_messages = messages
        
        # Add message_id (format: "channel:index")
        result_messages = []
        for idx, msg in enumerate(filtered_messages):
            channel = msg.get("channel", "")
            message_id = f"{channel}:{idx}"
            result_messages.append({
                "message_id": message_id,
                "channel_id": channel,
                "text": msg.get("text", ""),
                "user": msg.get("user", ""),
                "timestamp": msg.get("timestamp", "")
            })
            if limit and len(result_messages) >= limit:
                break
        
        return {"messages": result_messages}

    def slack_search_messages(self, user_name: str, limit: Optional[int] = None) -> Dict[str, Any]:
        """
        Search Slack messages by user name.
        
        Similar to Slack API search.messages endpoint filtered by user.
        
        Args:
            user_name: User name to search for (e.g., "alice", "bob"). If empty, returns all messages.
            limit: Optional maximum number of results
            
        Returns:
            Dictionary with "messages" list, each message has:
            - message_id: Message identifier (format: "channel:index")
            - channel_id: Channel identifier
            - text: Message text
            - user: User who sent the message
            - timestamp: Message timestamp
        """
        slack_data = self._load_source("slack")
        messages = slack_data.get("messages", [])
        
        # If empty user_name, return all messages
        if not user_name or user_name.strip() == "":
            result_messages = []
            for idx, msg in enumerate(messages):
                channel = msg.get("channel", "")
                message_id = f"{channel}:{idx}"
                result_messages.append({
                    "message_id": message_id,
                    "channel_id": channel,
                    "text": msg.get("text", ""),
                    "user": msg.get("user", ""),
                    "timestamp": msg.get("timestamp", "")
                })
                if limit and len(result_messages) >= limit:
                    break
            return {"messages": result_messages}
        
        # Search by user name (case-insensitive)
        matches = []
        user_name_lower = user_name.lower()
        for idx, msg in enumerate(messages):
            msg_user = msg.get("user", "").lower()
            # Match if user name is in the message user field
            if user_name_lower in msg_user or msg_user == user_name_lower:
                channel = msg.get("channel", "")
                message_id = f"{channel}:{idx}"
                matches.append({
                    "message_id": message_id,
                    "channel_id": channel,
                    "text": msg.get("text", ""),
                    "user": msg.get("user", ""),
                    "timestamp": msg.get("timestamp", "")
                })
                if limit and len(matches) >= limit:
                    break
        
        return {"messages": matches}

    def slack_get_channel(self, channel_id: str) -> Dict[str, Any]:
        """
        Get channel information by channel_id.
        
        Similar to Slack API conversations.info endpoint.
        
        Args:
            channel_id: Channel identifier
            
        Returns:
            Dictionary with channel details:
            - channel_id: Channel identifier
            - name: Channel name
        """
        slack_data = self._load_source("slack")
        messages = slack_data.get("messages", [])
        
        # Check if channel exists
        channels_set = set()
        for msg in messages:
            channel = msg.get("channel", "")
            if channel:
                channels_set.add(channel)
        
        if channel_id in channels_set:
            return {
                "channel_id": channel_id,
                "name": channel_id
            }
        else:
            return {"error": f"Channel with channel_id '{channel_id}' not found"}

    def gmail_list_threads(self, query: Optional[str] = None, limit: Optional[int] = None) -> Dict[str, Any]:
        """
        List Gmail threads, optionally filtered by search query.
        
        Similar to Gmail API users.threads.list endpoint.
        
        Args:
            query: Optional search query to filter threads by subject or message content
            limit: Optional maximum number of results
            
        Returns:
            Dictionary with "threads" list, each thread has:
            - thread_id: Thread identifier
            - subject: Thread subject
        """
        gmail_data = self._load_source("gmail")
        threads = gmail_data.get("threads", [])
        
        # If query provided, filter threads
        if query:
            # Split query into words (word-based search, like actual Gmail API)
            query_words = [w.strip() for w in query.lower().split() if w.strip()]
            matches = []
            for thread in threads:
                thread_subject = thread.get("subject", "")
                # Combine thread subject and all message content for search
                combined_text = thread_subject.lower()
                for msg in thread.get("messages", []):
                    msg_subject = msg.get("subject", "")
                    msg_text = msg.get("text", "")
                    combined_text += " " + msg_subject.lower() + " " + msg_text.lower()
                
                # Check if all query words are present (AND operation, like actual Gmail API)
                if query_words and all(word in combined_text for word in query_words):
                    matches.append({
                        "thread_id": thread.get("thread_id", ""),
                        "subject": thread_subject
                    })
                    if limit and len(matches) >= limit:
                        break
            return {"threads": matches}
        else:
            # Return all threads (metadata only)
            result_threads = []
            for thread in threads:
                result_threads.append({
                    "thread_id": thread.get("thread_id", ""),
                    "subject": thread.get("subject", "")
                })
                if limit and len(result_threads) >= limit:
                    break
            return {"threads": result_threads}

    def gmail_list_messages(self, query: Optional[str] = None, limit: Optional[int] = None) -> Dict[str, Any]:
        """
        List Gmail messages across all threads, optionally filtered by search query.
        
        Similar to Gmail API users.messages.list endpoint.
        Message IDs are dynamically generated as "thread_id:index".
        
        Args:
            query: Optional search query to filter messages by subject or text
            limit: Optional maximum number of results
            
        Returns:
            Dictionary with "messages" list, each message has:
            - message_id: Message identifier (format: "thread_id:index")
            - subject: Message subject
        """
        gmail_data = self._load_source("gmail")
        threads = gmail_data.get("threads", [])
        
        # Flatten all messages from all threads
        all_messages = []
        for thread in threads:
            thread_id = thread.get("thread_id", "")
            messages = thread.get("messages", [])
            for idx, msg in enumerate(messages):
                message_id = f"{thread_id}:{idx}"
                all_messages.append({
                    "message_id": message_id,
                    "thread_id": thread_id,
                    "subject": msg.get("subject", ""),
                    "text": msg.get("text", ""),
                    "from": msg.get("from", ""),
                    "to": msg.get("to", []),
                    "timestamp": msg.get("timestamp", "")
                })
        
        # If query provided, filter messages
        if query:
            # Split query into words (word-based search, like actual Gmail API)
            query_words = [w.strip() for w in query.lower().split() if w.strip()]
            matches = []
            for msg in all_messages:
                subject = msg.get("subject", "")
                text = msg.get("text", "")
                # Combine subject and text for search
                combined_text = (subject + " " + text).lower()
                
                # Check if all query words are present (AND operation, like actual Gmail API)
                if query_words and all(word in combined_text for word in query_words):
                    matches.append({
                        "message_id": msg.get("message_id", ""),
                        "subject": subject
                    })
                    if limit and len(matches) >= limit:
                        break
            return {"messages": matches}
        else:
            # Return all messages (metadata only)
            result_messages = []
            for msg in all_messages:
                result_messages.append({
                    "message_id": msg.get("message_id", ""),
                    "subject": msg.get("subject", "")
                })
                if limit and len(result_messages) >= limit:
                    break
            return {"messages": result_messages}

    def gmail_get_thread(self, thread_id: str) -> Dict[str, Any]:
        """
        Get thread details by thread_id.
        
        Similar to Gmail API users.threads.get endpoint.
        
        Args:
            thread_id: Thread identifier
            
        Returns:
            Dictionary with thread details including all messages.
        """
        gmail_data = self._load_source("gmail")
        threads = gmail_data.get("threads", [])
        
        # Find thread by thread_id
        for thread in threads:
            if thread.get("thread_id") == thread_id:
                return thread
        
        # Thread not found
        return {"error": f"Thread with thread_id '{thread_id}' not found"}

    def gmail_get_message(self, message_id: str) -> Dict[str, Any]:
        """
        Get message details by message_id.
        
        Similar to Gmail API users.messages.get endpoint.
        Message ID format: "thread_id:index"
        
        Args:
            message_id: Message identifier (format: "thread_id:index")
            
        Returns:
            Dictionary with message details.
        """
        gmail_data = self._load_source("gmail")
        threads = gmail_data.get("threads", [])
        
        # Parse message_id (format: "thread_id:index")
        if ":" not in message_id:
            return {"error": f"Invalid message_id format: '{message_id}'. Expected format: 'thread_id:index'."}
        
        thread_id, index_str = message_id.rsplit(":", 1)
        try:
            index = int(index_str)
        except ValueError:
            return {"error": f"Invalid message_id format: '{message_id}'. Index must be an integer."}
        
        # Find thread
        for thread in threads:
            if thread.get("thread_id") == thread_id:
                messages = thread.get("messages", [])
                if 0 <= index < len(messages):
                    msg = messages[index]
                    return {
                        "message_id": message_id,
                        "thread_id": thread_id,
                        "subject": msg.get("subject", ""),
                        "text": msg.get("text", ""),
                        "from": msg.get("from", ""),
                        "to": msg.get("to", []),
                        "timestamp": msg.get("timestamp", "")
                    }
                else:
                    return {"error": f"Message index {index} out of range for thread '{thread_id}'"}
        
        # Thread not found
        return {"error": f"Thread with thread_id '{thread_id}' not found"}

    def jira_list_projects(self) -> Dict[str, Any]:
        """
        List Jira projects.
        
        Similar to Jira API project.getAllProjects endpoint.
        
        Returns:
            Dictionary with "projects" list, each project has:
            - project_key: Project key (e.g., "API")
            - name: Project name
            - description: Project description
        """
        jira_data = self._load_source("jira")
        projects = jira_data.get("projects", [])
        
        # If projects array exists, return it directly
        if projects:
            return {"projects": projects}
        
        # Fallback: extract from issues (backward compatibility)
        issues = jira_data.get("issues", [])
        project_keys_set = set()
        for issue in issues:
            issue_key = issue.get("issue_key", "")
            if not issue_key:
                issue_key = issue.get("issue_id", "")  # Support old format
            if "-" in issue_key:
                project_key = issue_key.split("-")[0]
                project_keys_set.add(project_key)
        
        # Convert to list of project dicts
        projects = [{"project_key": key, "name": key} for key in sorted(project_keys_set)]
        
        return {"projects": projects}

    def jira_search_issues(
        self,
        jql: Optional[str] = None,
        project: Optional[str] = None,
        status: Optional[str] = None,
        limit: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Search Jira issues using JQL query or filters.
        
        Similar to Jira API search.search endpoint.
        
        Args:
            jql: Optional JQL query string (e.g., "status=Open")
            project: Optional project key to filter by
            status: Optional status to filter by
            limit: Optional maximum number of results
            
        Returns:
            Dictionary with "issues" list, each issue has:
            - issue_key: Issue identifier (e.g., "API-121")
            - summary: Issue summary
            - status: Issue status
        """
        jira_data = self._load_source("jira")
        issues = jira_data.get("issues", [])
        
        # Start with all issues
        filtered = issues
        
        # Apply JQL if provided (simple parsing for common cases)
        if jql:
            jql_lower = jql.lower()
            # Simple JQL parsing for common patterns
            if "status=" in jql_lower:
                # Extract status from JQL (e.g., "status=Open")
                status_match = jql_lower.split("status=")[1].split()[0] if "status=" in jql_lower else None
                if status_match:
                    filtered = [issue for issue in filtered if issue.get("status", "").lower() == status_match]
            if "project=" in jql_lower:
                # Extract project from JQL (e.g., "project=API")
                project_match = jql_lower.split("project=")[1].split()[0] if "project=" in jql_lower else None
                if project_match:
                    # Support both issue_key and issue_id for backward compatibility
                    filtered = [issue for issue in filtered 
                               if issue.get("issue_key", issue.get("issue_id", "")).startswith(f"{project_match}-")]
        
        # Apply project filter
        if project:
            # Support both issue_key and issue_id for backward compatibility
            filtered = [issue for issue in filtered 
                       if issue.get("issue_key", issue.get("issue_id", "")).startswith(f"{project}-")]
        
        # Apply status filter
        if status:
            filtered = [issue for issue in filtered if issue.get("status", "") == status]
        
        # Limit results
        if limit:
            filtered = filtered[:limit]
        
        # Return metadata only (issue_key, summary, status)
        result_issues = []
        for issue in filtered:
            # Support both issue_key and issue_id for backward compatibility
            issue_key = issue.get("issue_key", issue.get("issue_id", ""))
            result_issues.append({
                "issue_key": issue_key,
                "summary": issue.get("summary", ""),
                "status": issue.get("status", "")
            })
        
        return {"issues": result_issues}

    def jira_get_issue(self, issue_key: str) -> Dict[str, Any]:
        """
        Get issue details by issue_key.
        
        Similar to Jira API issue.getIssue endpoint.
        
        Args:
            issue_key: Issue identifier (e.g., "API-121")
            
        Returns:
            Dictionary with issue details:
            - issue_key: Issue identifier
            - summary: Issue summary
            - description: Issue description
            - status: Issue status
        """
        jira_data = self._load_source("jira")
        issues = jira_data.get("issues", [])
        
        # Find issue by issue_key
        for issue in issues:
            # Support both issue_key and issue_id for backward compatibility
            current_key = issue.get("issue_key", issue.get("issue_id", ""))
            if current_key == issue_key:
                return {
                    "issue_key": current_key,
                    "summary": issue.get("summary", ""),
                    "description": issue.get("description", ""),
                    "status": issue.get("status", "")
                }
        
        # Issue not found
        return {"error": f"Issue with issue_key '{issue_key}' not found"}

    def jira_get_project(self, project_key: str) -> Dict[str, Any]:
        """
        Get project information by project_key.
        
        Similar to Jira API project.getProject endpoint.
        
        Args:
            project_key: Project key (e.g., "API")
            
        Returns:
            Dictionary with project details:
            - project_key: Project key
            - name: Project name
            - description: Project description
        """
        jira_data = self._load_source("jira")
        projects = jira_data.get("projects", [])
        
        # If projects array exists, search in it
        if projects:
            for project in projects:
                if project.get("project_key") == project_key:
                    return project
        
        # Fallback: extract from issues (backward compatibility)
        issues = jira_data.get("issues", [])
        project_keys_set = set()
        for issue in issues:
            issue_key = issue.get("issue_key", "")
            if not issue_key:
                issue_key = issue.get("issue_id", "")  # Support old format
            if "-" in issue_key:
                key = issue_key.split("-")[0]
                project_keys_set.add(key)
        
        if project_key in project_keys_set:
            return {
                "project_key": project_key,
                "name": project_key
            }
        else:
            return {"error": f"Project with project_key '{project_key}' not found"}

    def drive_list_files(self, query: Optional[str] = None, limit: Optional[int] = None) -> Dict[str, Any]:
        """
        List Drive files, optionally filtered by search query.
        
        Similar to Google Drive API files.list endpoint.
        
        Args:
            query: Optional search query to filter files by name
            limit: Optional maximum number of results
            
        Returns:
            Dictionary with "files" list, each file has:
            - file_id: File identifier
            - name: File name
        """
        drive_data = self._load_source("drive")
        files = drive_data.get("files", [])
        
        # If query provided, filter by name or text content
        if query:
            query_lower = query.lower()
            matches = []
            for file in files:
                name = file.get("name", "")
                text = file.get("text", "")
                # Search in both file name and text content
                if query_lower in name.lower() or query_lower in text.lower():
                    matches.append({
                        "file_id": file.get("file_id", ""),
                        "name": name
                    })
                    if limit and len(matches) >= limit:
                        break
            return {"files": matches}
        else:
            # Return all files (without text content)
            result_files = []
            for file in files:
                result_files.append({
                    "file_id": file.get("file_id", ""),
                    "name": file.get("name", "")
                })
                if limit and len(result_files) >= limit:
                    break
            return {"files": result_files}

    def drive_get_file(self, file_id: str) -> Dict[str, Any]:
        """
        Get file details by file_id.
        
        Similar to Google Drive API files.get endpoint.
        
        Args:
            file_id: File identifier
            
        Returns:
            Dictionary with file metadata (file_id, name) but NOT text content.
            To get text content, use drive_export_file() instead.
        """
        drive_data = self._load_source("drive")
        files = drive_data.get("files", [])
        
        # Find file by file_id
        for file in files:
            if file.get("file_id") == file_id:
                return {
                    "file_id": file.get("file_id", ""),
                    "name": file.get("name", "")
                }
        
        # File not found
        return {"error": f"File with file_id '{file_id}' not found"}

    def drive_export_file(self, file_id: str) -> Dict[str, Any]:
        """
        Export file content by file_id.
        
        Similar to Google Drive API files.export endpoint.
        Internally calls drive_get_file() to find the file, then returns text content.
        
        Args:
            file_id: File identifier
            
        Returns:
            Dictionary with "content" string containing file text.
        """
        drive_data = self._load_source("drive")
        files = drive_data.get("files", [])
        
        # Find file by file_id
        for file in files:
            if file.get("file_id") == file_id:
                text = file.get("text", "")
                return {"content": text}
        
        # File not found
        return {"error": f"File with file_id '{file_id}' not found"}
