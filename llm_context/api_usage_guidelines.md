# API Usage Guidelines

This document describes the available tool functions and how to use them effectively.

## Tool Invocation Pattern

Tools are invoked via a JSON-RPC-style "tools/call" method with a "name" and "arguments" object. The result contains a "content" list with text or structured JSON data.

## Tool Functions

### 1. Slack.search_messages

**Arguments:**
- `search_query` (string): A search query string with keywords, names, or phrases

**Returns:**
A list of matching messages with channel information, author, text snippets, and timestamps.

**When to use:**
Use when you need to recall something someone said or find messages about a specific topic, meeting, or discussion.

**Common mistakes to avoid:**
- Calling it with extremely vague queries (e.g., "meeting" without context)
- Instead, use meaningful keywords: names, specific topics, or distinctive phrases

**Example query:**
"from:@tom meeting API launch Alice Min"

---

### 2. GoogleContacts.SearchContactsByName

**Arguments:**
- `name` (string): The person's name to search for
- `limit` (integer, optional): Maximum number of contacts to return. If not specified, returns all matching contacts.

**Returns:**
A list of contacts with names and email addresses matching the search.

**When to use:**
Use when you know a person's name but need their email address (e.g., for calendar scheduling or email lookups).

**Common mistakes to avoid:**
- Calling it when you already have an email address
- Using partial names that might match multiple people (be as specific as possible)
- Not using limit when you only need one contact (e.g., limit=1 for exact matches)

**Example:**
Search for "Alice Kim" with limit=1 to get "alice.kim@company.com"

---

### 3. GoogleCalendar.FindTimeSlotsWhenEveryoneIsFree

**Arguments:**
- `email_addresses` (array of strings): List of participant email addresses
- `start_date` (string, optional, YYYY-MM-DD): Start of the date range to search (e.g., "2025-11-17"). If not provided, uses the full range of calendar events.
- `end_date` (string, optional, YYYY-MM-DD): End of the date range to search (e.g., "2025-11-21"). If not provided, uses the full range of calendar events.
- `workday_start_time` (string, optional, HH:MM): Start of workday hours (e.g., "09:00"). Defaults to "09:00".
- `workday_end_time` (string, optional, HH:MM): End of workday hours (e.g., "18:00"). Defaults to "18:00".
- `slot_minimum_minutes` (integer, optional): Minimum duration for a meeting slot. Defaults to 30.

**Returns:**
A list of time slots with start and end datetimes where all participants are free.

**When to use:**
Use when you need to find overlapping availability for multiple people within a specific date range.

**Common mistakes to avoid:**
- Calling it with an empty list of email addresses
- Using an excessively broad date range (keep it focused, e.g., one to two weeks)
- Forgetting to specify reasonable workday hours

**Example:**
Find 45-minute slots for three people between 2025-11-17 and 2025-11-21, during 09:00-18:00.

---

### 4. GoogleCalendar.ListEvents

**Arguments:**
- `min_end_datetime` (string, ISO datetime): Minimum end time for events to include
- `max_start_datetime` (string, ISO datetime): Maximum start time for events to include
- `max_results` (integer, optional): Maximum number of events to return

**Returns:**
A list of events with summary, start, end, and attendee information.

**When to use:**
Use when you need to know what meetings happened or will happen in a specific time window.

**Common mistakes to avoid:**
- Calling it repeatedly with tiny changes when one call with a sensible window is enough
- Using overly narrow windows that might miss relevant events
- Not specifying max_results when you only need a few events

**Example:**
List events between 2025-11-09T00:00:00+09:00 and 2025-11-16T23:59:59+09:00.

---

### 5. Gmail.SearchThreads

**Arguments:**
- `subject` (string, optional): Subject line keywords to search for
- `sender` (string, optional): Sender email address
- `date_range` (string, optional): Time range like "last_30_days" or "last_7_days". Filters threads by the first message date.
- `max_results` (integer, optional): Maximum number of threads to return

**Returns:**
A list of thread IDs matching the search criteria.

**When to use:**
Use to find relevant email conversations by subject and sender within a time range.

**Common mistakes to avoid:**
- Using overly generic subjects like "update" without any other filter
- Not specifying a date_range when looking for recent conversations
- Combining too many filters that might exclude relevant threads

**Example:**
Search for threads with subject containing "feature update" from "customer@client.com" in the last 30 days.

---

### 6. Gmail.GetThread

**Arguments:**
- `thread_id` (string): The ID of the thread to retrieve

**Returns:**
The full thread with all messages, including from, to, date, and body fields.

**When to use:**
Use after locating thread IDs with Gmail.SearchThreads, when you need to inspect the conversation tone, details, and prior context.

**Common mistakes to avoid:**
- Calling it on every possible thread if only one or two are needed
- Not using SearchThreads first to narrow down relevant conversations
- Retrieving threads that are clearly unrelated to the current request

**Example:**
After finding a relevant thread ID, call GetThread to read the full conversation history.

---

### 7. GoogleDrive.gdrive_search

**Arguments:**
- `query` (string): A search expression with keywords or file name patterns
- `limit` (integer, optional): Maximum number of files to return

**Returns:**
A list of files with id, name, mimeType, and sometimes category information.

**When to use:**
Use to find documents by title, keywords, or distinctive phrases in the file name.

**Common mistakes to avoid:**
- Using very vague queries (e.g., "document" or "file")
- Instead, include distinctive words like "Playbook", "Weekly Report Template", or specific document names
- Not using limit when you only need one or two files

**Example:**
Search for "Customer Response Playbook" or "Weekly Report Template" to find specific documents.

---

### 8. GoogleDrive.gdrive_read_file

**Arguments:**
- `file_id` (string): The ID of the file to read

**Returns:**
Text content or key excerpts from the file.

**When to use:**
Use after locating a specific file with gdrive_search, when you need to know its content, section headings, or guidelines.

**Common mistakes to avoid:**
- Calling it on many unrelated files; first narrow down using gdrive_search
- Reading files that are clearly not relevant to the current request
- Not using gdrive_search first to identify the right file

**Example:**
After finding a playbook file ID, call gdrive_read_file to read the section about release ETA communication guidelines.

---

### 9. Jira.SearchIssuesWithJql

**Arguments:**
- `jql` (string): A JQL (Jira Query Language) query string
- `limit` (integer, optional): Maximum number of issues to return

**Returns:**
A list of issues with fields such as key, summary, status, fixVersions (with name and releaseDate), and updated timestamp.

**When to use:**
Use to find issues by project, free-text search, status, or update date. JQL allows complex queries combining multiple criteria.

**Common mistakes to avoid:**
- Using overly broad queries that return many irrelevant issues
- Not using date filters when looking for recently updated issues
- Forgetting to specify a project when multiple projects exist
- Using incorrect JQL syntax (e.g., missing quotes around text values)

**Example JQL queries:**
- `project = APP AND text ~ "feature X" ORDER BY updated DESC`
- `project = APP AND updated >= "2025-11-09" AND updated <= "2025-11-16"`
- `key = APP-412`

---

## Tool Selection Strategy

When working with a request, follow this approach:

1. **Decide what information is missing:** Identify what data you need to answer the request completely.

2. **Pick the smallest set of tools:** Select only the tools that can provide the necessary information. Avoid redundant calls.

3. **Avoid unnecessary calls:** Don't call tools that return information you already have or that are clearly unrelated to the request.

4. **Combine sources when needed:** Often, you'll need information from multiple sources. Call tools in a logical sequence, using results from earlier calls to inform later ones.

5. **Use specific queries:** Make your search queries and filters specific enough to return relevant results without overwhelming amounts of data.

