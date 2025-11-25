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
  "ground_answer_text": "The best available time is Tuesday, 2025-11-25 from 14:00-14:45.",
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

### Task Categories

- **`planning`**: Meeting scheduling tasks (requires `canonical_answer` with `meeting_slots`)
- **`document`**: Document generation tasks
- **`email_reply`**: Email reply tasks

### Metadata Fields

- **`min_required_source`**: Minimum number of distinct sources needed
- **`fragmentation_depth`**: How many separate messages/entries contain key facts
- **`indirection_depth`**: Number of "hops" across different sources needed
- **`noise_level`**: Reserved for future use (currently always 0)

## Usage

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

```python
from evaluate import evaluate_all_tasks

# Evaluate all tasks with default models
results = evaluate_all_tasks()
```

## Directory Structure

```
MPCBench/
├── archive/
│   └── mcpbench_v1/          # Archived v1 code
├── tasks/                     # Human-authored task definitions (JSON)
├── logs/                      # Evaluation logs and run artifacts
├── config.py                  # Global configuration
├── task_defs.py               # Task loading and validation
├── data_gen.py                # Source data generation
├── oracle_validator.py        # Data consistency validation
├── tool_backend.py            # Tool interface to source data
├── agent_runner.py            # Single task execution
├── evaluate.py                # Evaluation runner
├── model_config.json          # Model settings
├── prompt_config.json         # LLM prompts
└── README.md                  # This file
```

## Design Principles

1. **Task-First**: Tasks define requirements; source data is generated to support them
2. **No Personas**: Personalization emerges from source content, not pre-defined personas
3. **Multi-Source Composition**: Tasks require combining information from multiple sources
4. **Ground Truth**: Each task has a human-written ground answer and machine-readable canonical answer

## Requirements

- Python 3.8+
- OpenAI API key (set `OPENAI_API_KEY` environment variable)

