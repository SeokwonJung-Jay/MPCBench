# MPCBench : Multi-Source Personal Context Composition Benchmark

MPCBench is a benchmark for evaluating LLM agents that need to compose information from multiple workplace data sources (Slack, Gmail, Calendar, Jira, Drive) to complete tasks.

## Overview

MPCBench evaluates how well LLM agents can find and combine information from multiple workplace data sources to solve real-world tasks.

### Key Features

- **Multi-source information composition**: Agents must gather and combine information from multiple sources (Slack, Gmail, Calendar, Jira, Drive) to complete tasks
- **Realistic data formats**: Uses data structures and natural text styles that mirror actual workplace tools
- **Controlled difficulty**: Configurable complexity through fragmentation, indirection, and source requirements
- **LLM-based data generation**: Generates natural, realistic content using LLM models

### Evaluation Goals

- Assess agents' ability to find information across multiple sources
- Evaluate agents' capability to combine incomplete information fragments into complete answers
- Measure performance across varying difficulty levels
- Test agents' reasoning with constraint-based information (rather than explicit answers)

## Goals & Philosophy

### Benchmark Objectives

MPCBench is designed to evaluate LLM agents' capabilities in multi-source information composition scenarios commonly found in workplace environments. The primary goals are:

1. **Multi-source information gathering**: Test agents' ability to find relevant information across different workplace data sources
2. **Information composition**: Evaluate how well agents combine incomplete information fragments from multiple sources
3. **Difficulty scaling**: Measure performance across varying complexity levels through configurable parameters
4. **Constraint-based reasoning**: Assess agents' ability to work with constraints and exclusions rather than explicit answers

### Design Philosophy

#### 1. Task-First Approach

Tasks define the requirements and ground truth answers first. Source data is then generated to support those tasks, ensuring that:
- Tasks are the primary unit of evaluation
- Source data serves the task requirements
- Evaluation focuses on task completion rather than data exploration
- Controlled difficulty through systematic data generation
- Reproducible scenarios with known ground truth

#### 2. Realism in Data Format and Style

While the benchmark uses actual workplace tool data structures and natural text styles, it acknowledges that:
- **Data formats and structures** mirror real workplace tools (Slack, Jira, Gmail, Calendar, Drive)
- **Text styles** are generated to be natural and realistic using LLM models
- **Data generation purpose** is task-oriented (all data supports task completion), which differs from real workplaces where most data is task-unrelated
- **Information alignment** is perfect (all information is task-relevant), unlike real workplaces with significant noise

#### 3. Rigorous Ground Truth Alignment

- **Canonical answer uniqueness**: Generated constraints ensure that canonical answers are the only valid solutions
- **Distractor elimination**: Each source removes specific distractor candidates while preserving canonical answers
- **Constraint-only sources**: Jira, Drive, and Gmail never explicitly state canonical times - they only provide constraints (ranges or exclusions) that eliminate distractors
- **Natural constraint expression**: Constraints are expressed naturally (e.g., "afternoons after 14:00" in Slack, "conflict at 13:00" in Jira) rather than as explicit rules

#### 4. Difficulty Control Mechanisms

The benchmark provides fine-grained control over task difficulty through three key parameters:
- **Fragmentation**: Controls how information is distributed within a single source
- **Indirection**: Controls how many sources must be combined
- **Source requirements**: Controls the minimum number of distinct sources needed

## Key Concepts

### Fragmentation Depth

Controls how information is distributed within a single source:

- **`fragmentation_depth = 1`**: All information in a single message/entry (complete on its own)
- **`fragmentation_depth = 2`**: Information split across 2 messages/entries (each incomplete, must be combined)
- **`fragmentation_depth = 3+`**: Information split across 3+ messages/entries (all must be combined to understand)

For `fragmentation_depth >= 2`, each distractor assigned to a source gets `fragmentation_depth` incomplete messages/entries that must be combined to remove that distractor. The total number of messages/entries = `fragmentation_depth * len(assigned_distractors)`.

### Indirection Depth

Controls how many sources must be combined:

- **`indirection_depth = 1`**: Single source (Calendar only, no linking)
- **`indirection_depth = 2`**: Two sources linked (e.g., Slack → Jira, where Slack references a Jira issue)
- **`indirection_depth = 3+`**: Multi-hop chains across 3+ sources (e.g., Slack → Jira → Drive)

### min_required_source

The minimum number of distinct sources (excluding Calendar) needed to solve the task. This parameter:
- Determines how many additional sources (Slack, Jira, Drive, Gmail) must be used
- Ensures that Calendar alone is insufficient to find the answer
- Each source removes specific distractor slots, making canonical slots unique

### Distractors and Canonical Answers

- **Canonical Answer**: The unique ground truth answer that must be found
- **Distractor**: Incorrect candidate answers that must be eliminated
- **Distractor elimination**: Each source provides constraints that remove specific distractor slots while preserving canonical slots
- **Constraint-only sources**: Jira, Drive, and Gmail never explicitly state canonical times - they only provide constraints that eliminate distractors

### Constraint Templates

The data generator uses a library of constraint templates to create realistic multi-source scenarios:

**Calendar Templates:**
- **T_CAL_UNIQUE**: Calendar-only unique solution (`indirection_depth=1`) - canonical slot is the only tri-free slot
- **T_CAL_MULTI_CANDIDATES**: Multiple free slots in calendar (`indirection_depth≥2`) - creates ambiguity requiring other sources

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
- **depth=1**: T_CAL_UNIQUE only (Calendar provides unique solution)
- **depth=2**: T_CAL_MULTI_CANDIDATES + one or more constraint sources (Slack, Jira, Drive, Gmail) with unidirectional linking
- **depth≥3**: Multi-hop patterns combining constraints across multiple sources (chain linking: A → B → C). Jira/Drive/Gmail only eliminate distractors, never state canonical time

## Architecture

### Core Components

- **`task_defs.py`**: Task definition loading and validation
- **`data_gen.py`**: Generation of per-task source data
- **`tool_backend.py`**: Exposes generated sources as tools to the agent
- **`agent_runner.py`**: Runs a single task with an agent
- **`evaluate.py`**: Runs evaluation over many tasks and computes scores

### Task Schema

Each task is defined as a JSON file in the `tasks/` directory with the following structure:

```json
{
  "category": "planning",
  "current_date": "2025-11-24",
  "task_description": "Find a meeting time that works for Alice, Bob, and Carol next week.",
  "canonical_answer": {
    "meeting_slots": [
      {
        "date": "2025-12-02",
        "slot": "14:00-14:45"
      },
      {
        "date": "2025-12-03",
        "slot": "13:00-13:45"
      }
    ]
  },
  "metadata": {
    "min_required_source": 3,
    "fragmentation_depth": 2,
    "indirection_depth": 2,
    "noise_level": 0
  }
}
```

**Note**: The only ground truth for scoring is `canonical_answer`. There is no `ground_answer_text` field. Task IDs are derived from the filename (e.g., `example_planning_001.json` → ID: `example_planning_001`).

### Task Categories

- **`planning`**: Meeting scheduling tasks (requires `canonical_answer` with `meeting_slots`)
- **`document`**: Document generation tasks
- **`email_reply`**: Email reply tasks

### Metadata Fields

- **`min_required_source`**: Minimum number of distinct sources needed to solve the task (excluding Calendar)
- **`fragmentation_depth`**: How many separate messages/entries contain key facts (1 = all in one entry, higher = more fragmented)
- **`indirection_depth`**: Number of "hops" across different sources needed (1 = single source, 2 = two sources, 3+ = multi-hop chains)
- **`noise_level`**: Reserved for future use (currently always 0)

## Usage

### Quick Start

The simplest way to run evaluation:

```bash
# Evaluate all tasks (data generation happens automatically)
python3 run_evaluation.py

# Evaluate a specific task
python3 run_evaluation.py --task-id example_planning_001
```

### Loading Tasks

```python
from task_defs import load_all_tasks, load_task
from pathlib import Path

# Load all tasks
tasks = load_all_tasks()

# Load a specific task
task = load_task(Path("tasks/example_planning_001.json"))

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
python3 run_evaluation.py --task-id example_planning_001
```

#### Method 2: Python code

```python
from evaluate import evaluate_task, evaluate_all_tasks
from task_defs import load_task
from pathlib import Path

# Single task evaluation
task = load_task(Path('tasks/example_planning_001.json'))
result = evaluate_task(task, agent_model='gpt-4o-mini', generate_data=True)

# All tasks evaluation
results = evaluate_all_tasks(generate_data=True)
```

#### Method 3: Data generation only

```python
from data_gen import generate_source_data
from task_defs import load_task
from pathlib import Path
from config import LOGS_DIR

task = load_task(Path('tasks/example_planning_001.json'))
output_dir = LOGS_DIR / task.id / "data"
source_data = generate_source_data(task, output_dir)
print(f"Generated sources: {list(source_data.keys())}")
```

### Viewing Results

Evaluation results are saved to `logs/{task_id}/agent-{model}_{mode}_eval.json`:

```python
import json
from pathlib import Path

# Read results
result_path = Path('logs/example_planning_001/agent-gpt-4o-mini_minimal_eval.json')
with open(result_path, 'r') as f:
    result = json.load(f)

print(f"Answer score: {result['scores']['answer_requirements_satisfaction']}")
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
     "agent_models": ["gpt-4o-mini", "gpt-4o", "gpt-5.1"],
     "judge_models": ["gpt-5.1"],
     "data_generation_model": "gpt-5.1"
   }
   ```

### Notes

- `generate_data=True` generates fresh data each time; set `False` to reuse existing data
- Data generation uses templates and prompts from `prompt_config.json`
- Missing config entries will raise `ValueError` (no silent fallbacks)

## Directory Structure

```
MPCBench/
├── tasks/                     # Human-authored task definitions (JSON)
├── logs/                      # Evaluation logs and run artifacts
├── config.py                  # Global configuration
├── task_defs.py               # Task loading and validation
├── data_gen.py                # Source data generation (constraint templates)
├── tool_backend.py            # Tool interface to source data
├── agent_runner.py            # Single task execution (OpenAI tools)
├── evaluate.py                # Evaluation runner
├── run_evaluation.py          # Main evaluation script
├── model_config.json          # Model settings
├── prompt_config.json         # LLM prompts and data generation config
└── README.md                  # This file
```

## Planning Pipeline

The end-to-end pipeline for planning tasks:

1. **Task Definition** (`task_defs.py`): Load task JSON with `canonical_answer` and `metadata`
2. **Data Generation** (`data_gen.py`): 
   - Extract participant names from `task_description` using heuristics, or use `fallback_names` from `prompt_config.json`
   - Generate participant emails using `email_domain` from config
   - **LLM-based content generation**: Slack, Jira, Drive, and Gmail content is generated using LLM (specified in `model_config.json`'s `data_generation_model`)
     - LLM generates natural, realistic content that meets fragmentation and indirection requirements
     - Generated content is validated by another LLM call to ensure it meets criteria (incompleteness, constraint application, linked source references)
     - Falls back to template-based generation if LLM validation fails after retries
   - **Calendar generation**: Logic-based generation (structured data with free/busy slots)
   - **Distractor generation**: Distractors are generated within the same date range as canonical slots to ensure `min_required_source` and `indirection_depth` work correctly
   - Apply constraint templates based on `indirection_depth` and `min_required_source`:
     - **depth=1**: Calendar only (T_CAL_UNIQUE)
     - **depth=2**: Calendar + Slack/Jira/Drive/Gmail constraints (unidirectional linking)
     - **depth≥3**: Multi-hop patterns with constraint-only sources (chain linking)
   - **Jira/Drive/Gmail never explicitly state canonical time** - they only eliminate distractor slots or provide range constraints
   - All prompts and templates come from `prompt_config.json` (no hard-coded strings)
   - Raises `ValueError` if required config entries are missing (no silent fallbacks)
   - Generate calendar, slack, jira, drive, gmail JSON files
3. **Tool Backend** (`tool_backend.py`): Expose generated sources as queryable tools (generic search/filter logic)
4. **Agent Execution** (`agent_runner.py`): 
   - OpenAI function-calling agent iteratively uses tools
   - Produces `final_answer`, `rationale`, and `tool_calls` log
5. **Evaluation** (`evaluate.py`): Score agent answer against `canonical_answer` (substring matching for date and slot)

## Configuration

### `prompt_config.json`

All data-specific content (names, emails, templates, timestamps) and LLM prompts live in `prompt_config.json`:

**Generator Config** (under `generator` key):
- **Global**: `fallback_names`, `email_domain`
- **Slack**: `base_user_names`, `time_filter_templates`, `weekday_filter_templates`, `doc_reference_templates`
- **Jira**: `project_keys`, `conflict_templates`
- **Drive**: `doc_title_templates`, `doc_time_negative_templates`
- **Gmail**: `from_candidates`, `to_candidates`, `subject_templates`, `cancellation_templates`
- **Calendar**: `timestamp_patterns` (used by all sources)

**LLM Data Generation** (under `data_generation` key):
- **System messages**: For data generation and validation LLMs
- **User prompt templates**: Instructions, requirements, and format specifications for each source type
- **Source descriptions**: Brief descriptions for each source type (Slack, Jira, Drive, Gmail)
- **Validation prompts**: Check instructions and response format for LLM-based validation

**Agent Prompts** (under `agent` key):
- **System messages**: Minimal and detailed versions for different tool context modes
- **User message instructions**: Tool usage guidance, response format, calendar warnings

No Python code contains hard-coded names, emails, project names, timestamps, or prompt text.

## Requirements

- Python 3.8+
- OpenAI API key (set `OPENAI_API_KEY` environment variable)

## TODO

### Data Generation
- [ ] Support team-based tasks (e.g., "Find a meeting time for our team")
- [ ] Currently only planning tasks are supported. When adding email/document evaluation, add corresponding functions and ensure they don't conflict
- [ ] Add noise - generate distractor data unrelated to constraints
- [ ] Modify `source_descriptions` in `prompt_config.json` to generate more realistic data for each source type (Slack, Jira, Drive, Gmail)

### API and Data Consistency
- [ ] Verify API-data consistency and remove unnecessary APIs that don't align with generated data structure

### Evaluation
- [ ] Consider rationale in scoring system
- [ ] Adjust penalty ratio for extra slots
