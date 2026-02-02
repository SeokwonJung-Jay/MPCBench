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

### Decomposition

| Aspect | Level 1 | Level 2 | Level 3 |
|--------|---------|---------|---------|
| Sources | 1-2 | 3 | 4+ |
| Source hints in task | All sources named | # of sources told | No hints |
| Requirement-to-source mapping | 1:1 | 1:1 | Some mapped to several sources |
| Requirement independence | Independent | Independent | Some dependent |

### Information Acquisition

| Aspect | Level 1 | Level 2 | Level 3 |
|--------|---------|---------|---------|
| APIs provided | Few | Some unnecessary APIs | Many similar tools |
| Retrieval steps | 1-2 | 3-4 | 5+ |
| Parameters | Keyword/date only | Same | Same |
| API result quality | Clean, single item | Multiple items, long text noise | Cross-tool joins required, more noise |

### Integration

| Aspect | Level 1 | Level 2 | Level 3 |
|--------|---------|---------|---------|
| Output formats | Similar (JSON) | 1-2 different (JSON + text) | 3+ different (JSON + text + table) |
| Context types | Single (availability) | 1-2 (availability + policy) | 3+ (availability + policy + room + capacity) |

## Oracle-based labeling and evaluation

MPCBench uses an oracle to produce the gold answer deterministically:

- The oracle never parses natural language. Any unstructured text sources include machine-readable tags.

- Pipeline: candidate generation → constraint filtering → (level 3) room join → deterministic sorting → top-N selection

- Instances with fewer than N feasible candidates after filtering are discarded and resampled.

Evaluation (current):

- Compare model output candidates against oracle top-N candidates using F1 overlap.

- The benchmark may store rationales/explanations, but they are not scored yet.

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
