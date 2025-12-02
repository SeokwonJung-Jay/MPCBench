# MPCBench v2: Task-First Multi-Source Composition Benchmark

MPCBench v2 is a benchmark for evaluating LLM agents that need to compose information from multiple workplace data sources (Slack, Gmail, Calendar, Contacts, Jira, Drive) to complete tasks.

## Overview

MPCBench v2 takes a **task-first** approach: tasks are defined with their requirements and ground answers, and source data is generated to support those tasks. This is in contrast to v1's scenario-first approach.

## Architecture

### Core Components

- **`task_defs.py`**: Task definition loading and validation
- **`data_gen.py`**: Generation of per-task source data
- **`oracle_validator.py`**: Validates consistency of generated data against ground answers
- **`tool_backend.py`**: Exposes generated sources as tools to the agent
- **`agent_runner.py`**: Runs a single task with an agent
- **`evaluate.py`**: Runs evaluation over many tasks and computes scores

### Task Schema

Each task is defined as a JSON file in the `tasks/` directory with the following structure:

```json
{
  "id": "task_001",
  "category": "planning",
  "task_description": "Find a meeting time that works for Alice, Bob, and Carol next week.",
  "canonical_answer": {
    "meeting_slots": [
      {
        "date": "2025-11-25",
        "slot": "14:00-14:45"
      }
    ]
  },
  "metadata": {
    "min_required_source": 2,
    "fragmentation_depth": 1,
    "indirection_depth": 2,
    "noise_level": 0
  }
}
```

**Note**: The only ground truth for scoring is `canonical_answer`. There is no `ground_answer_text` field.

### Task Categories

- **`planning`**: Meeting scheduling tasks (requires `canonical_answer` with `meeting_slots`)
- **`document`**: Document generation tasks
- **`email_reply`**: Email reply tasks

### Metadata Fields

- **`min_required_source`**: Minimum number of distinct sources needed to solve the task
- **`fragmentation_depth`**: How many separate messages/entries contain key facts (1 = all in one entry, higher = more fragmented)
- **`indirection_depth`**: Number of "hops" across different sources needed (1 = single source, 2 = two sources, 3+ = multi-hop chains)
- **`noise_level`**: Reserved for future use (currently always 0)

### Constraint Templates

The data generator uses a library of constraint templates to create realistic multi-source scenarios. **Important**: Jira, Drive, and Gmail **never explicitly state the canonical meeting time**. They only provide constraints (ranges or exclusions) that help narrow down candidate slots.

**Calendar Templates:**
- **T_CAL_UNIQUE**: Calendar-only unique solution (indirection_depth=1) - canonical slot is the only tri-free slot
- **T_CAL_MULTI_CANDIDATES**: Multiple free slots in calendar (indirection_depth≥2) - creates ambiguity requiring other sources

**Slack Templates:**
- **T_SLACK_FILTER_TIME**: Slack provides time-of-day constraints (e.g., "afternoons after 14:00")
- **T_SLACK_FILTER_WEEKDAY**: Slack provides weekday constraints (e.g., "can't do Monday/Tuesday")
- **T_SLACK_REFERS_TO_DOC**: Slack refers to a drive document by title (multi-hop pattern)

**Jira Templates:**
- **T_JIRA_CONFLICT_SLOT**: Jira reveals conflicts for **distractor slots only** (never canonical) - marks slots as unavailable

**Drive Templates:**
- **T_DRIVE_DOC_TIME_NEGATIVE**: Drive document rules out **distractor slots only** (never canonical) - e.g., "The previous plan was to meet on {date} {slot}, but that time no longer works."

**Gmail Templates:**
- **T_GMAIL_CANCEL_SLOT**: Gmail cancels **distractor slots only** (never canonical) - e.g., "We can't do {date} {slot} anymore."

Templates are selected based on `indirection_depth` and `min_required_source`:
- **depth=1**: T_CAL_UNIQUE only
- **depth=2**: T_CAL_MULTI_CANDIDATES + one of T_SLACK_FILTER_TIME, T_SLACK_FILTER_WEEKDAY, or T_JIRA_CONFLICT_SLOT
- **depth≥3**: Multi-hop patterns combining constraints across multiple sources (Jira/Drive/Gmail only eliminate distractors, never state canonical time)

## Usage

### Quick Start

The simplest way to run evaluation:

```bash
# Evaluate all tasks (data generation happens automatically)
python3 run_evaluation.py

# Evaluate a specific task
python3 run_evaluation.py example_planning_001
```

### Loading Tasks

```python
from task_defs import load_all_tasks, load_task
from pathlib import Path

# Load all tasks
tasks = load_all_tasks()

# Load a specific task
task = load_task(Path("tasks/task_001.json"))

# Check task type
if task.is_planning():
    print(f"Canonical answer: {task.canonical_answer}")
```

### Running Evaluation

#### Method 1: Using the script (recommended)

```bash
# All tasks
python3 run_evaluation.py

# Specific task
python3 run_evaluation.py example_planning_001
```

#### Method 2: Python code

```python
from evaluate import evaluate_task, evaluate_all_tasks
from task_defs import load_task
from pathlib import Path

# Single task evaluation
task = load_task(Path('tasks/example_planning_task.json'))
result = evaluate_task(task, agent_model='gpt-4o-mini', generate_data=True)

# All tasks evaluation
results = evaluate_all_tasks(generate_data=True)

# Specific models
results = evaluate_all_tasks(
    agent_models=['gpt-4o-mini', 'gpt-4o'],
    generate_data=True
)
```

#### Method 3: Data generation only

```python
from data_gen import generate_source_data
from task_defs import load_task
from pathlib import Path
from config import LOGS_DIR

task = load_task(Path('tasks/example_planning_task.json'))
output_dir = LOGS_DIR / task.id / "data"
source_data = generate_source_data(task, output_dir)
print(f"Generated sources: {list(source_data.keys())}")
```

### Viewing Results

Evaluation results are saved to `logs/{task_id}/agent-{model}_eval.json`:

```python
import json
from pathlib import Path

# Read results
result_path = Path('logs/example_planning_001/agent-gpt-4o-mini_eval.json')
with open(result_path, 'r') as f:
    result = json.load(f)

print(f"Answer score: {result['scores']['answer_requirements_satisfaction']}")
print(f"Source score: {result['scores']['source_grounded_reasoning']}")
print(f"Final answer: {result['agent_result']['final_answer']}")
```

### Environment Setup

1. **Set OpenAI API key:**

   Create a `.env` file in the project root:
   ```bash
   # Create .env file
   echo "OPENAI_API_KEY=your-api-key-here" > .env
   ```
   
   Or set it as an environment variable:
   ```bash
   export OPENAI_API_KEY="your-api-key"
   ```
   
   **Note**: The `.env` file is gitignored and will not be committed. The code will automatically load environment variables from `.env` if `python-dotenv` is installed.

2. **Install dependencies:**
   ```bash
   pip install openai python-dotenv
   ```
   
   **Note**: If `python-dotenv` is not installed, the code will still work but will only read from environment variables (not `.env` file).

3. **Configure models** in `model_config.json`:
   ```json
   {
     "agent_models": ["gpt-4o-mini", "gpt-4o"],
     "judge_models": ["gpt-5.1"],
     "data_generation_model": "gpt-5.1"
   }
   ```

### Notes

- `generate_data=True` generates fresh data each time; set `False` to reuse existing data
- Data generation uses templates from `generator_config.json`
- Missing config entries will raise `ValueError` (no silent fallbacks)

## Directory Structure

```
MPCBench/
├── archive/
│   └── mcpbench_v1/          # Archived v1 code (gitignored)
├── tasks/                     # Human-authored task definitions (JSON)
├── logs/                      # Evaluation logs and run artifacts
├── config.py                  # Global configuration
├── task_defs.py               # Task loading and validation
├── data_gen.py                # Source data generation (constraint templates)
├── oracle_validator.py        # Data consistency validation
├── tool_backend.py            # Tool interface to source data
├── agent_runner.py            # Single task execution (OpenAI tools)
├── evaluate.py                # Evaluation runner
├── model_config.json          # Model settings
├── prompt_config.json         # LLM prompts
├── generator_config.json      # Data generation templates and defaults
└── README.md                  # This file
```

## Planning Pipeline

The end-to-end pipeline for planning tasks:

1. **Task Definition** (`task_defs.py`): Load task JSON with `canonical_answer` and `metadata`
2. **Data Generation** (`data_gen.py`): 
   - Extract participant names from `task_description` using heuristics, or use `fallback_names` from `generator_config.json`
   - Generate participant emails using `email_domain` from config
   - Apply constraint templates based on `indirection_depth` and `min_required_source`:
     - **depth=1**: Calendar only (T_CAL_UNIQUE)
     - **depth=2**: Calendar + Slack/Jira constraints (Pattern 2A/2B/2C)
     - **depth≥3**: Multi-hop patterns with constraint-only sources (Pattern 3A/3B/3C)
   - **Jira/Drive/Gmail never explicitly state canonical time** - they only eliminate distractor slots or provide range constraints
   - All text content comes from `generator_config.json` templates (no hard-coded strings)
   - Raises `ValueError` if required config entries are missing (no silent fallbacks)
   - Generate calendar, slack, jira, drive, gmail, contacts JSON files
3. **Oracle Validation** (`oracle_validator.py`): 
   - Derive participants dynamically from calendar data
   - Verify canonical slots are free for all participants
4. **Tool Backend** (`tool_backend.py`): Expose generated sources as queryable tools (generic search/filter logic)
5. **Agent Execution** (`agent_runner.py`): 
   - OpenAI function-calling agent iteratively uses tools
   - Produces `final_answer`, `rationale`, and `tool_calls` log
6. **Evaluation** (`evaluate.py`): Score agent answer against `canonical_answer` (substring matching for date and slot)

## Configuration

### `generator_config.json`

All data-specific content (names, emails, templates, timestamps) lives in `generator_config.json`:

- **Global**: `fallback_names`, `email_domain`
- **Slack**: `base_user_names`, `time_filter_templates`, `weekday_filter_templates`, `doc_reference_templates`
- **Jira**: `project_keys`, `conflict_templates`
- **Drive**: `doc_title_templates`, `doc_time_positive_templates`, `doc_time_negative_templates`
- **Gmail**: `from_candidates`, `to_candidates`, `subject_templates`, `confirmation_templates`, `cancellation_templates`, `timestamp_patterns`

No Python code contains hard-coded names, emails, project names, or timestamps.

## Design Principles

1. **Task-First**: Tasks define requirements; source data is generated to support them
2. **No Personas**: Personalization emerges from source content, not pre-defined personas
3. **No Hard-Coded Data**: All names, emails, projects, labels come from `generator_config.json` or are derived from `task_description`/`canonical_answer`. Missing config entries raise `ValueError` (no silent fallbacks)
4. **Constraint Templates**: Reusable templates create realistic multi-source scenarios. Jira/Drive/Gmail provide constraints only (never explicitly state canonical time)
5. **Canonical Answer Only**: Scoring uses only `canonical_answer` (no `ground_answer_text`)
6. **Dynamic Participants**: Participants are extracted from `task_description` or generated from config, never hard-coded
7. **Multi-Source Reasoning**: Agents must combine calendar availability with constraints from Slack/Jira/Drive/Gmail to find the unique canonical slot

## Requirements

- Python 3.8+
- OpenAI API key (set `OPENAI_API_KEY` environment variable)

