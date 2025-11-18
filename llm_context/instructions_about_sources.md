# Using Workplace Data Sources

This document describes the available data sources and when to use them.

## 1. Slack

Slack stores team communication in channels, messages, and threads.

**What it contains:**
- Channels (e.g., "#proj-ops", "#team-weekly")
- Messages with text, authors, timestamps, and channel associations
- User information (names and email-like handles)

**Typical uses:**
- Find what someone said about a topic or meeting
- Locate summary or recap messages in team channels
- See who was mentioned for a work item or discussion
- Search for messages containing specific keywords or phrases

**Important identifiers:**
- Channel names (e.g., "#proj-ops", "#team-weekly")
- Human names and email-like handles
- Message timestamps

## 2. Gmail (Email)

Gmail contains email threads and individual messages with subjects, senders, recipients, dates, and message bodies.

**What it contains:**
- Threads (conversations) with multiple messages
- Individual messages with from/to addresses, subjects, dates, and body text
- Thread and message IDs for referencing

**Typical uses:**
- Read recent conversations with customers or external contacts
- Infer tone and context from previous email exchanges
- Track ongoing discussions about specific topics
- Understand prior questions or requests

**Important fields:**
- Thread ID (for retrieving full conversations)
- Subject (for searching and context)
- From/to addresses (sender and recipient information)
- Date (for filtering by time)
- Body (message content)

## 3. Google Calendar

Google Calendar stores events with summaries, start/end times, and attendee information.

**What it contains:**
- Events with titles, start/end datetimes, and attendee lists
- Calendar associations (linked to email addresses)
- Free/busy information for scheduling

**Typical uses:**
- List upcoming or past meetings in a date range
- Check who attends a meeting and when they are available
- Find overlapping free time slots for multiple people
- Understand meeting schedules and availability

**Important fields:**
- Summary (event title)
- Start and end (ISO datetime strings)
- Attendees (array of email addresses)

## 4. Google Contacts

Google Contacts stores contact information, primarily names and their associated email addresses.

**What it contains:**
- Contact entries with names and email addresses
- Optional additional fields (phone, organization)

**Typical uses:**
- Map a person's name to their email address
- Disambiguate multiple people with similar names
- Look up contact information for meeting participants

**Important fields:**
- Name (for searching)
- Email addresses (array of email strings)

## 5. Jira (Issue Tracker)

Jira stores work items (issues) with keys, summaries, statuses, fix versions, and update dates.

**What it contains:**
- Issues with unique keys (e.g., "APP-412")
- Summaries, statuses, and update timestamps
- Fix versions with release dates
- Project associations

**Typical uses:**
- Check the status of a work item or feature
- See planned release versions and dates
- Find issues updated within a time window
- Track project progress and milestones

**Important fields:**
- Key (unique issue identifier, e.g., "APP-412")
- Summary (brief description)
- Status (e.g., "Done", "In QA", "In Progress")
- FixVersions (array with name and releaseDate)
- Updated (timestamp of last update)

## 6. Google Drive

Google Drive stores files with metadata and sometimes text content or excerpts.

**What it contains:**
- Files with IDs, names, MIME types, and category tags
- Text excerpts or summaries for some files
- File metadata (modification dates, types)

**Typical uses:**
- Find a document by name or keywords
- Read short excerpts or summaries to understand guidelines or templates
- Locate reference materials, playbooks, or templates
- Access structured content like report templates

**Important fields:**
- File ID (for retrieving file content)
- Name (for searching and identification)
- MIME type (file format)
- Category (semantic tags like "customer_playbook", "weekly_report_template")
- Text excerpt (when available, provides key content)

## General Guidance

These data sources complement each other and serve different purposes:

- **Slack and Jira** are good for day-to-day team discussions, work item status, and project updates.
- **Gmail** is good for external and customer communication, understanding prior context and tone.
- **Calendar** is good for timing, scheduling, and understanding participant availability.
- **Contacts** connects human names to email addresses, enabling cross-source lookups.
- **Drive** holds longer-form documents, templates, guidelines, and reference materials.

When working with a request, consider what information is needed and choose the appropriate sources. You may need to combine information from multiple sources to provide a complete answer. Select tools based on the information requirements of the request, not based on any predefined patterns.

