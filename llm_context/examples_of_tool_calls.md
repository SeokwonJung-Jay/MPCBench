# Example Tool Call Sequences

This document provides end-to-end examples of how to combine multiple tools to accomplish common workplace tasks.

## Example: Finding a Meeting Time

**User message:**
"Could you find a time next week for a meeting with Tom, Alice, and Min?"

**Tool sequence:**

1. **Slack.search_messages**
   - Query: `"from:@tom meeting Alice Min next week"`
   - Purpose: Locate the message where Tom mentioned the meeting to understand context and confirm participants.

2. **GoogleContacts.SearchContactsByName**
   - For "Alice Kim": Returns email address `alice.kim@company.com`
   - For "Min Lee": Returns email address `min.lee@company.com`
   - For "Tom": Returns email address `tom@partner.co`
   - Purpose: Map participant names to email addresses needed for calendar queries.

3. **GoogleCalendar.FindTimeSlotsWhenEveryoneIsFree**
   - Arguments:
     - `email_addresses`: `["tom@partner.co", "alice.kim@company.com", "min.lee@company.com"]`
     - `start_date`: `"2025-11-17"` (YYYY-MM-DD format)
     - `end_date`: `"2025-11-21"` (YYYY-MM-DD format)
     - `workday_start_time`: `"09:00"`
     - `workday_end_time`: `"18:00"`
     - `slot_minimum_minutes`: `45`
   - Returns: List of time slots where all three participants are free.
   - Note: If `start_date` or `end_date` is not provided, the tool automatically uses the full range of calendar events.

**Example assistant response:**
"I found a few options for the meeting with Tom, Alice, and Min next week:

- **Option 1:** Thursday, November 14, 10:00 AM - 10:45 AM
- **Option 2:** Monday, November 17, 4:30 PM - 5:15 PM

Both slots are 45 minutes long and work for all three participants. Would either of these work for you?"

---

## Example: Answering a Customer About a Feature Release

**User message:**
"A customer asked when a new feature will be available. How should I reply?"

**Tool sequence:**

1. **Gmail.SearchThreads**
   - Arguments:
     - `subject`: `"feature update"`
     - `sender`: `"customer@client.com"`
     - `date_range`: `"last_30_days"`
   - Purpose: Find recent email threads about the feature from this customer.

2. **Gmail.GetThread**
   - Arguments: `thread_id` from the search results
   - Purpose: Read the full conversation to understand the customer's tone, prior questions, and context.

3. **GoogleDrive.gdrive_search**
   - Query: `"Customer Response Playbook"`
   - Purpose: Locate the customer response playbook document with communication guidelines.

4. **GoogleDrive.gdrive_read_file**
   - Arguments: `file_id` from the search results
   - Purpose: Read the section about release ETA communication to understand how to phrase the response.

5. **Jira.SearchIssuesWithJql**
   - Query: `project = APP AND text ~ "feature X" ORDER BY updated DESC`
   - Purpose: Find the relevant rollout issue (e.g., APP-412) and retrieve its status, fixVersions, and releaseDate.

**Example assistant response:**
"Based on the customer's previous emails and our internal tracking, here's a suggested reply:

---

Subject: Re: Feature Update

Hi [Customer],

Thank you for your continued interest in our feature updates. I wanted to provide you with an update on the timeline.

Based on our current development schedule, we're targeting a release window around late November 2025 (approximately November 28, 2025). Please note that this is a target date and may be subject to change based on final testing and quality assurance.

We'll keep you informed as we get closer to the release. If you have any questions in the meantime, please don't hesitate to reach out.

Best regards,
[Your name]

---

This response follows our playbook guidance by using cautious language, providing a target window rather than an exact date, and including appropriate caveats."

---

## Example: Drafting a Weekly Team Report

**User message:**
"Please draft a weekly team report summarizing this week's work."

**Tool sequence:**

1. **Jira.SearchIssuesWithJql**
   - Query: `project = APP AND updated >= "2025-11-09" AND updated <= "2025-11-16" ORDER BY updated DESC`
   - Purpose: Fetch issues updated within the weekly window to understand what work was completed or progressed.

2. **Slack.search_messages**
   - Query: `"#team-weekly summary wins recap"`
   - Purpose: Retrieve weekly summary messages from the team channel that contain key metrics and achievements.

3. **GoogleDrive.gdrive_search**
   - Query: `"Weekly Report Template"`
   - Purpose: Find the weekly report template document to understand the expected structure.

4. **GoogleDrive.gdrive_read_file**
   - Arguments: `file_id` from the search results
   - Purpose: Read the template to get the section structure (Goals, Key Results, Highlights, Risks, Next Week).

5. **GoogleCalendar.ListEvents**
   - Arguments:
     - `min_end_datetime`: `"2025-11-09T00:00:00+09:00"`
     - `max_start_datetime`: `"2025-11-16T23:59:59+09:00"`
   - Purpose: List meetings and events that occurred during the week.

**Example assistant response outline:**
"Here's a draft weekly team report for the week of November 9-16, 2025:

## Goals
- Continue API Launch project milestones
- Maintain quality standards through QA processes

## Key Results
- **API Optimization (APP-410):** Completed and marked as Done
- **Feature X Rollout (APP-412):** Progressed to In QA status
- **Performance Improvements:** Latency reduced by 20% compared to previous week
- **User Growth:** 8% week-over-week increase in active users

## Highlights
- Successfully completed API optimization work
- Feature X rollout entered QA phase, on track for late November release
- Significant performance improvements achieved
- Strong user growth momentum continued

## Risks
- Feature X rollout timeline dependent on QA completion
- Need to monitor performance metrics as user base grows

## Next Week
- Complete QA for Feature X rollout
- Prepare for release candidate
- Continue monitoring performance metrics
- Review and plan for upcoming milestones

## Significant Meetings
- API Performance Review (November 12, 2:00 PM - 3:00 PM) - Reviewed performance improvements and discussed rollout timeline"

---

## General Notes

These examples demonstrate how to:
- Combine information from multiple sources to provide complete answers
- Use tool results to inform subsequent tool calls
- Structure responses based on templates and guidelines found in the data
- Maintain consistency with prior communications and established patterns

Remember to adapt your approach based on the specific information available and the requirements of each request.

