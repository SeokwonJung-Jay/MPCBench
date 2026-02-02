# MPCBench

MPCBench is a benchmark for measuring an agent/LLM's ability to compose personal context across multiple internal sources to complete real tasks.

## Key question

"How can we measure and improve an agent/LLM's ability to compose personal context to complete real tasks?"

MPCBench prioritizes:

- Improving outcomes for the same task (accuracy, constraint adherence, success rate, etc.)

- Enabling end-to-end completion of tasks that become feasible only with personal-context composition

## What MPCBench evaluates

Each task requires the agent to complete a scheduling problem by performing three capabilities:

1) Decomposition: break requirements into information needs (which internal records are needed)

2) Information acquisition: retrieve required information via tool calls from multiple sources

3) Integration: combine heterogeneous formats/contexts to generate, filter, and rank final candidates

All constraints are treated as hard constraints (violations remove a candidate).

## Task family (scheduling)

Common objective: propose N meeting candidates within a given time window.

Data sources may include:

- Calendar busy intervals (JSON)

- Organization policy (JSON in easy; long text + machine-readable tags in harder levels)

- Communication threads (Slack-like text + machine-readable tags for deadlines/bans; and in the hardest level also required participants, duration, N, and tie-break rules)

- (Hardest level) people directory (name → id join) and room system (room metadata table + availability JSON requiring joins)

Candidates are generated on a 15-minute grid to allow deterministic oracle computation.

## Difficulty levels (numeric)

- Level 1 (easy): Calendar + Policy (policy is JSON; sources are explicit)

- Level 2 (mid): Calendar + Policy (long text + tags) + Communication threads (text + tags); task text does not name sources (only indicates multiple internal sources)

- Level 3 (hard): Level 2 + People directory + Room system; task text provides no hints about sources; cross-tool joins are required; ranking is earliest-first with deterministic tie-break (e.g., room_id ascending)

## Level Design Matrix

| Dimension | Level 1 | Level 2 | Level 3 |
|-----------|---------|---------|---------|
| **Decomposition** | - 1-2 sources and requirements<br>- All sources are named in the task<br>- Each requirement is mapped into 1 source<br>- Each requirement is independent | - 3 sources and 1-2 requirements<br>- # of sources are told<br>- Each requirement is mapped into 1 source<br>- Each requirement is independent | - 4+ sources and 3+ requirements<br>- No hints for source usage<br>- Some requirements are mapped into several sources<br>- Some requirements are dependent |
| **Information Acquisition** | - Only a few APIs provided<br>- Requires 1-2 retrieval steps<br>- No parameters beyond keyword and date<br>- API returns a clean, single relevant item | - Some unnecessary APIs are provided<br>- Requires 3-4 retrieval steps<br>- API result may contain multiple items or long texts as noise | - Many APIs with multiple similar tools<br>- Requires 5+ retrieval steps<br>- Requires cross-tool joins and multi-step retrieval<br>- More noise |
| **Integration** | - All outputs have similar structure (JSON)<br>- All outputs have similar context (availability only) | - 1-2 different formats (JSON + text)<br>- 1-2 different contexts (availability + policy) | - 3+ different formats (JSON + text + table)<br>- 3+ different contexts (availability + policy + room + capacity) |

## Oracle-based labeling and evaluation

MPCBench uses an oracle to produce the gold answer deterministically:

- The oracle never parses natural language. Any unstructured text sources include machine-readable tags.

- Pipeline: candidate generation → constraint filtering → (level 3) room join → deterministic sorting → top-N selection

- Instances with fewer than N feasible candidates after filtering are discarded and resampled.

Evaluation (current):

- Compare model output candidates against oracle top-N candidates using F1 overlap.

- The benchmark may store rationales/explanations, but they are not scored yet.

## Evaluation Results (gpt-4o)

### Summary

| Level | F1 Score | Exact Match |
|-------|----------|-------------|
| L1 | 0.90 | 4/5 |
| L2 | 0.80 | 4/5 |
| L3 | 0.33 | 1/5 |

### Failure Analysis

| Level | Root Cause | Detail | Category |
|-------|------------|--------|----------|
| L1 | Busy Time Overlap | person_002 busy 11:30-12:00, Agent selected 11:45-12:45 which overlaps | Integration |
| L2 | Unspecified Rule Applied | Applied POLICY_3 (buffer) not specified in task, missed 11:00 slot | Decomposition |
| L3 | Policy Day Misapply | Applied "Monday 9-12 restricted" to Thursday (01-22) | Integration |
| L3 | Output Format Ignore | Ignored "same time, different rooms" instruction, selected 3 different time slots | Decomposition |
| L3 | Constraint Integration | Failed to combine buffer + busy + room availability constraints | Integration |
| L3 | Room Selection Error | Excluded room_003 (available at 09:00) due to confusion with other time bookings | Integration |

## Data artifacts

Recommended structure:

- `worlds/`: `world_level1.json`, `world_level2.json`, `world_level3.json` (one fixed world per level)

- `instances/`: `instances_level1.jsonl`, `instances_level2.jsonl`, `instances_level3.jsonl` (many instances per level)

- `oracles/`: `oracle_level1.jsonl`, `oracle_level2.jsonl`, `oracle_level3.jsonl` (oracle labels; join by instance_id)

## Repo structure

- `schema/`: JSON schemas for world/instance/oracle (single unified schema per concept; level handled inside)

- `generate/`: world + instance generation (with discard/resample loop)

- `oracle/`: deterministic oracle engine

- `evaluation/`: parsing + scoring (F1)

- `archive/`: legacy MPCBench implementation (read-only; never modify)
