MPCBench: Multisource Personal-Context Benchmark SPEC
=====================================================

SECTION 0. Overview
-------------------

MPCBench is a synthetic but organically connected benchmark for evaluating LLMs on multi-source personal/workplace context composition.

Per company/workspace, the benchmark has data from:
- Slack
- Google Calendar
- Google Contacts
- Gmail
- Jira
- Google Drive

Core evaluation tasks:
- Planning
- Email reply
- Document generation

Models must:
- Select appropriate tools/sources.
- Align context across sources (for example, Slack with Contacts and Calendar, Gmail with Drive and Jira).
- Compose final answers that are consistent with the underlying data.

Tool calls are MCP-style JSON-RPC "tools/call" with "arguments".


SECTION 1. Repository structure
-------------------------------

The repository should contain:

- BENCHMARK_SPEC.md  (this file)

- schemas/
  - slack_schema.json
  - calendar_schema.json
  - contacts_schema.json
  - gmail_schema.json
  - jira_schema.json
  - drive_schema.json
  - world_state_schema.json
  - api_schemas/
    - Slack.json
    - Gmail.json
    - Calendar.json
    - Contacts.json
    - Jira.json
    - Drive.json

- scenarios/
  - company_A.json
  - company_B.json  (optional, can be added later)
  - templates/
    - world_defaults.json

- generator/
  - world_state_generator.py
  - propagation_engine.py
  - slack_generator.py
  - gmail_generator.py
  - calendar_generator.py
  - contacts_generator.py
  - jira_generator.py
  - drive_generator.py
  - llm_templates/   (for text generation prompts)
  - run_generation.py

- validator/
  - schema_validator.py
  - consistency_checker.py
  - cross_source_link_checker.py

- data/
  - company_A/
  - company_B/

- tasks/
  - planning/
    - planning_task.json
  - email_reply/
    - email_reply_task.json
  - document_generation/
    - document_task.json

- evaluation/
  - scoring.py
  - tool_call_validator.py
  - context_selection_eval.py
  - composition_eval.py

- llm_context/
  - instructions_about_sources.md
  - api_usage_guidelines.md
  - examples_of_tool_calls.md


SECTION 2. World state specification
------------------------------------

File: generator/world_state_generator.py

This module is the single source of truth for each company’s internal "world state".

Conceptual function:

    generate_world_state(company_scenario_file: str, defaults_file: str, seed: int) -> dict

Inputs:
- company_scenario_file: path to a company scenario JSON, for example "scenarios/company_A.json".
- defaults_file: path to a defaults/templates JSON, for example "scenarios/templates/world_defaults.json".
- seed: integer random seed for reproducibility.

Outputs:
- A Python dict called world_state.
- The dict is written to "data/<company_name>/world_state.json".
- The JSON file must conform to "schemas/world_state_schema.json".


2.1 High-level structure of world_state.json
--------------------------------------------

The world_state JSON has the following top-level structure:

1) company
2) people
3) projects
4) timeline_events
5) artifacts
6) task_alignment

Details:

1) company
- company.name : string (for example "Company A")
- company.timezone : string (for example "Asia/Seoul")

2) people  (list of employees)
Each element has:
- id : string, stable identifier (for example "person_alice")
- name : string
- email : string
- team : string (for example "Engineering", "Product")
- role : string (for example "Senior Engineer", "PM")
- collaborators : list of person ids (may be empty at first)

3) projects  (list)
Each project has:
- project_key : string (for example "APP")
- name : string (for example "API Launch")
- milestones : list of milestone objects
  - milestone.name : string (for example "Design Review", "QA", "Launch")
  - milestone.date : string, ISO date (for example "2025-11-10")
- jira_seeds : list of initial issues
  - issue_key : string (for example "APP-410")
  - summary : string
  - status : string (for example "Done", "In QA")

4) timeline_events  (list of events that drive data across tools)
Each event has:
- id : string
- timestamp : string, ISO datetime with timezone offset (for example "2025-11-07T10:30:00+09:00")
- type : string, for example:
  - "meeting_request"
  - "jira_update"
  - "weekly_summary"
- participants : list of person ids (when applicable)

Optional fields, depending on event.type:
- issue_key : string (for example "APP-412")
- release_target : string, ISO date (for example "2025-11-28")
- description_seed : string (short seed text that later drives Slack/email content)

links : object of booleans indicating which sources are affected:
- affects_slack : boolean
- affects_calendar : boolean
- affects_contacts : boolean
- affects_jira : boolean
- affects_gmail : boolean
- affects_drive : boolean

5) artifacts
- artifacts.drive_files : list of file seeds
Each file has:
- id : string (for example "file_playbook")
- name : string (for example "Customer Response Playbook v3.pdf")
- category : string (for example "customer_playbook", "weekly_report_template")

6) task_alignment
- task_alignment.planning
  - meeting_event_id : string, id of the relevant "meeting_request" event
  - participants : list of person ids
- task_alignment.email_reply
  - jira_issue_key : string, for example "APP-412"
  - customer_email_subject_seed : string, for example "feature update"
  - customer_sender_email : string, for example "customer@client.com"
- task_alignment.document_generation
  - weekly_event_id : string, id of the relevant "weekly_summary" event
  - window_start : string, ISO date (for example "2025-11-09")
  - window_end : string, ISO date (for example "2025-11-16")


2.2 Example initial content for company A
-----------------------------------------

The generator can start by hard-coding a simple example world_state for "Company A".

company:
- name: "Company A"
- timezone: "Asia/Seoul"

people (at minimum):
- person_tom:
  - name: "Tom Park"
  - email: "tom@partner.co"
  - team: "Product"
  - role: "PM"
- person_alice:
  - name: "Alice Kim"
  - email: "alice.kim@company.com"
  - team: "Engineering"
  - role: "Senior Engineer"
- person_min:
  - name: "Min Lee"
  - email: "min.lee@company.com"
  - team: "Engineering"
  - role: "Engineer"
- person_pm:
  - name: "Dana Choi"
  - email: "dana.choi@company.com"
  - team: "Product"
  - role: "Lead PM"

projects:
- One project:
  - project_key: "APP"
  - name: "API Launch"
  - milestones:
    - milestone:
      - name: "Design Review"
      - date: "2025-11-10"
    - milestone:
      - name: "QA"
      - date: "2025-11-15"
    - milestone:
      - name: "Launch"
      - date: "2025-11-28"
  - jira_seeds:
    - issue:
      - issue_key: "APP-410"
      - summary: "Optimize API"
      - status: "Done"
    - issue:
      - issue_key: "APP-412"
      - summary: "Feature X rollout"
      - status: "In QA"

timeline_events:
- event_planning_sync:
  - id: "event_planning_sync"
  - timestamp: "2025-11-07T10:30:00+09:00"
  - type: "meeting_request"
  - participants: ["person_tom", "person_alice", "person_min"]
  - description_seed: "sync with Alice and Min about the API launch, 45 minutes, sometime next week"
  - links:
    - affects_slack: true
    - affects_calendar: true
    - affects_contacts: true
    - affects_jira: false
    - affects_gmail: false
    - affects_drive: false

- event_feature_rollout:
  - id: "event_feature_rollout"
  - timestamp: "2025-11-08T15:00:00+09:00"
  - type: "jira_update"
  - issue_key: "APP-412"
  - status: "In QA"
  - release_target: "2025-11-28"
  - links:
    - affects_slack: false
    - affects_calendar: false
    - affects_contacts: false
    - affects_jira: true
    - affects_gmail: true
    - affects_drive: true

- event_weekly_summary:
  - id: "event_weekly_summary"
  - timestamp: "2025-11-12T18:00:00+09:00"
  - type: "weekly_summary"
  - participants: ["person_pm", "person_alice", "person_min"]
  - description_seed: "weekly wins: latency reduced by 20%, users up 8% week-over-week"
  - links:
    - affects_slack: true
    - affects_calendar: true
    - affects_contacts: false
    - affects_jira: true
    - affects_gmail: false
    - affects_drive: false

artifacts.drive_files:
- file_playbook:
  - id: "file_playbook"
  - name: "Customer Response Playbook v3.pdf"
  - category: "customer_playbook"
- file_weekly_template:
  - id: "file_weekly_template"
  - name: "Weekly Report Template.docx"
  - category: "weekly_report_template"

task_alignment:
- planning:
  - meeting_event_id: "event_planning_sync"
  - participants: ["person_tom", "person_alice", "person_min"]
- email_reply:
  - jira_issue_key: "APP-412"
  - customer_email_subject_seed: "feature update"
  - customer_sender_email: "customer@client.com"
- document_generation:
  - weekly_event_id: "event_weekly_summary"
  - window_start: "2025-11-09"
  - window_end: "2025-11-16"


SECTION 3. Propagation engine and generators
--------------------------------------------

File: generator/propagation_engine.py

This module converts the world_state into structured "plans" for each data source.

Input:
- world_state (Python dict, loaded from "data/company_A/world_state.json")

Output:
- event_plans (Python dict) with keys:
  - "slack_plans"
  - "gmail_plans"
  - "calendar_plans"
  - "contacts_plans"
  - "jira_plans"
  - "drive_plans"

Each value is a list of simple plan dicts describing what should be created/updated in that source.


3.1 Example mapping from timeline_events
----------------------------------------

If event.type == "meeting_request":
- Add a Slack plan:
  - create a message in a project channel such as "#proj-ops"
  - the message text must include the description_seed (for example, Tom talking about syncing with Alice and Min, 45 minutes, next week)
- Add a Calendar plan:
  - ensure that there are at least two possible 45-minute meeting slots in the configured date range where all participants are free
- Add a Contacts plan:
  - ensure that all participants appear in the contacts data with correct names and emails

If event.type == "jira_update":
- Add a Jira plan:
  - create or update issue APP-412
  - set a fixVersion for the project with releaseDate equal to release_target
- Add a Gmail plan:
  - create or tag a customer email thread about the feature update that depends on this issue’s status and release date
- Add a Drive plan:
  - mark that the customer response playbook file is relevant for ETA communication

If event.type == "weekly_summary":
- Add a Slack plan:
  - create a weekly summary message in a channel like "#team-weekly"
  - include the description_seed text
- Add Jira plans:
  - ensure that some issues updated in the last 7 days match the progress implied by the summary
- Add Calendar plans:
  - ensure that meetings exist within the weekly window corresponding to the summarized activities


3.2 Source-specific generators
------------------------------

Each data-source generator reads world_state and its corresponding plans:

- slack_generator.generate_slack_data(world_state, slack_plans) -> dict
- gmail_generator.generate_gmail_data(world_state, gmail_plans) -> dict
- calendar_generator.generate_calendar_data(world_state, calendar_plans) -> dict
- contacts_generator.generate_contacts_data(world_state, contacts_plans) -> dict
- jira_generator.generate_jira_data(world_state, jira_plans) -> dict
- drive_generator.generate_drive_data(world_state, drive_plans) -> dict

Each generator returns a dict that must match its schema JSON in the "schemas" directory.
The generators may initially use simple, template-like text, but that text must be compatible with the queries and examples in the tasks (for example, Slack messages must contain phrases that the planning task’s search query could match).


SECTION 4. Task definitions
---------------------------

There are three tasks, each with a characteristic tool-call pattern.

Task JSON files:
- "tasks/planning/planning_task.json"
- "tasks/email_reply/email_reply_task.json"
- "tasks/document_generation/document_task.json"

Each task JSON should include:
- task_id : string
- user_prompt : string
- allowed_tools : list of strings
- data_dependencies : object referring to relevant world_state fields (such as meeting_event_id, jira_issue_key, weekly_event_id)
- expected_tool_sequence : list of objects with:
  - tool_name : string
  - description : natural-language description of what that call should do


4.1 Task 1: Planning
---------------------

Example user prompt (English):
"Please suggest times for the meeting that Tom mentioned earlier."

Tools used:
- Slack.search_messages
- GoogleContacts.SearchContactsByName
- GoogleCalendar.FindTimeSlotsWhenEveryoneIsFree

Expected logical sequence:
1. Call Slack.search_messages with a query such as:
   "from:@tom has:calendar OR (meeting AND (schedule OR time))"
   This should find the message where Tom talked about syncing with Alice and Min.
2. From the Slack result text, extract the intended attendees: Tom, Alice Kim, and Min Lee.
3. Call GoogleContacts.SearchContactsByName for each attendee (for example "Alice Kim", "Min Lee") to obtain their email addresses.
4. Call GoogleCalendar.FindTimeSlotsWhenEveryoneIsFree with:
   - email_addresses including "tom@partner.co", "alice.kim@company.com", "min.lee@company.com"
   - a date range such as 2025-11-13 to 2025-11-20
   - workday_start_time "09:00"
   - workday_end_time "18:00"
   - slot_minimum_minutes 45
5. Propose one or more meeting time options consistent with the returned "time_slots".

Data constraints for this task:
- Slack data must contain a message from Tom in a relevant channel that includes text similar to:
  "sync with Alice and Min about the API launch, 45 minutes, sometime next week".
- Contacts data must contain entries for Alice Kim and Min Lee with emails:
  "alice.kim@company.com" and "min.lee@company.com".
- Calendar data must include overlapping free time slots for Tom, Alice, and Min that match the example time slots used as ground truth.


4.2 Task 2: Email reply
------------------------

Example customer question (English):
"When is this feature update expected to be released?"

Tools used:
- Gmail.SearchThreads
- Gmail.GetThread
- GoogleDrive.gdrive_search
- GoogleDrive.gdrive_read_file
- Jira.SearchIssuesWithJql

Expected logical sequence:
1. Use Gmail.SearchThreads with criteria such as:
   - subject containing "feature update"
   - sender "customer@client.com"
   - date_range "last_30_days"
2. On the returned thread IDs, call Gmail.GetThread to inspect the conversation, understand the customer’s tone, and recover prior context (for example previous questions about rollout dates or early access).
3. Use GoogleDrive.gdrive_search to find a document whose name indicates a customer response playbook, such as "Customer Response Playbook v3.pdf".
4. Use GoogleDrive.gdrive_read_file on that file to read the section that describes how to communicate release ETAs (for example: use cautious language, provide a target window, specify that the dates are subject to change).
5. Use Jira.SearchIssuesWithJql with a query such as:
   "project = APP AND text ~ \"feature X\" ORDER BY updated DESC"
   to locate an issue such as APP-412 ("Feature X rollout") and read its fields (status, fixVersions, releaseDate).
6. Compose an email reply that:
   - matches the tone of the prior customer conversation,
   - follows the playbook’s guidance on release ETA communication,
   - uses Jira’s fixVersion or releaseDate (for example releaseDate "2025-11-28") as the basis for a target timeframe, with appropriate caveats.

Data constraints for this task:
- world_state must contain a project with project_key "APP" and an issue APP-412 named "Feature X rollout", status "In QA", with fixVersions including at least one version (for example "v2.3.0") whose releaseDate is "2025-11-28".
- Drive data must contain a file named "Customer Response Playbook v3.pdf" with text that outlines guidelines for communicating release ETAs.
- Gmail data must contain at least one thread from "customer@client.com" about a "feature update" in the last 30 days that can be used to derive tone and context.


4.3 Task 3: Document generation
-------------------------------

Example user prompt (English):
"Draft a weekly team report for this week."

Tools used:
- Jira.SearchIssuesWithJql
- Slack.search_messages
- GoogleDrive.gdrive_search
- GoogleDrive.gdrive_read_file
- GoogleCalendar.ListEvents

Expected logical sequence:
1. Use Jira.SearchIssuesWithJql for issues in project APP that were updated within the last 7 days (for example using a relative date filter or explicit date range based on world_state.task_alignment.document_generation.window_start and window_end).
2. Use Slack.search_messages to retrieve weekly summary messages in a channel like "#team-weekly" that contain words such as "summary" or "recap", or that appear as threaded recaps.
3. Use GoogleDrive.gdrive_search to locate a report template document, such as "Weekly Report Template.docx" or a team OKR document.
4. Use GoogleDrive.gdrive_read_file on the template file to obtain the structure, including sections such as "Goals", "Key Results", "Highlights", "Risks", and "Next Week".
5. Use GoogleCalendar.ListEvents with min and max date constraints matching the weekly window to fetch meetings held during that week (for example events like "API Performance Review").
6. Generate a weekly team report draft that:
   - summarizes Jira issue progress (for example completed tasks and tasks in QA),
   - incorporates the key wins and metrics from the Slack weekly summary (for example latency reduced by 20 percent, users up 8 percent week-over-week),
   - lists significant meetings from Calendar,
   - follows the structure of the report template (sections for Goals, Key Results, Highlights, Risks, and Next Week).

Data constraints for this task:
- Jira data must contain issues updated in the last 7 days with meaningful summaries and status changes, aligned with the weekly summary.
- Slack data must contain at least one weekly summary message consistent with event_weekly_summary’s description_seed ("weekly wins: latency reduced by 20%, users up 8% week-over-week").
- Drive data must contain a weekly report template file with a clear section structure.
- Calendar data must contain events within the specified weekly window that are consistent with the team’s work.


SECTION 5. LLM evaluation protocol
----------------------------------

Evaluation scripts in the "evaluation" directory will:
- Load generated data from "data/company_A/" (world_state.json and each source’s JSON).
- Load task specifications from "tasks/".
- Accept as input a model’s tool-call trace and final natural-language answer.

They should compute:

1) Tool-call validity:
- All called tools exist in "schemas/api_schemas" (for example Slack.search_messages, Gmail.SearchThreads).
- Arguments match the API schemas (correct argument names and types).
- IDs used in arguments (issue keys, file IDs, thread IDs, email addresses) refer to real objects in the generated data.

2) Context selection:
- For the planning task, the model uses Slack + Contacts + Calendar in a reasonable way.
- For the email-reply task, the model uses Gmail + Drive + Jira.
- For the document-generation task, the model uses Jira + Slack + Drive + Calendar.
- The model avoids unnecessary tools or obviously irrelevant tool calls.

3) Alignment:
- The model’s references (for example issue keys, meeting titles, email subjects) correspond to objects that actually exist in the data.
- Time ranges, participants, and relationships between entities (for example which issue is the rollout issue, which meeting belongs to which project) match what is encoded in the data.

4) Final answer quality:
- Planning: all suggested time slots are consistent with the overlapping free time found by GoogleCalendar.FindTimeSlotsWhenEveryoneIsFree.
- Email reply: the reply’s tone and content align with the Gmail thread; the ETA and phrasing align with both Jira’s release date and Drive playbook guidance.
- Document generation: the draft report’s structure matches the template; its content correctly summarizes Jira issues, Slack summaries, and Calendar events.


SECTION 6. LLM context files
----------------------------

LLM context files in "llm_context":

- instructions_about_sources.md:
  A description of what information each source contains (Slack, Gmail, Calendar, Contacts, Jira, Drive) and typical reasons to consult each source.

- api_usage_guidelines.md:
  For each tool function (Slack.search_messages, GoogleContacts.SearchContactsByName, GoogleCalendar.FindTimeSlotsWhenEveryoneIsFree, Gmail.SearchThreads, Gmail.GetThread, GoogleDrive.gdrive_search, GoogleDrive.gdrive_read_file, Jira.SearchIssuesWithJql, GoogleCalendar.ListEvents), describe:
  - arguments,
  - the type of data it returns,
  - when it is appropriate to call the tool.

- examples_of_tool_calls.md:
  One or more concise example tool-call sequences for each of the three tasks (planning, email reply, document generation), using simplified JSON-RPC request and response snippets that show the intended usage pattern.

End of MPCBench specification.

