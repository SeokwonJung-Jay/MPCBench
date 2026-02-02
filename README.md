# MPCBench

**A benchmark for measuring an agent/LLM's ability to compose personal context across multiple internal sources to complete real tasks.**

## 🎯 Key Question

> "How can we measure and improve an agent/LLM's ability to compose personal context to complete real tasks?"

MPCBench prioritizes:
1.  **Improving outcomes** for the same task (accuracy, constraint adherence, success rate).
2.  **Enabling end-to-end completion** of tasks that become feasible *only* with personal-context composition.

---

## 🧠 What MPCBench Evaluates

Each task requires the agent to complete a scheduling problem by demonstrating three distinct capabilities:

### 1. Decomposition
**Breaking requirements into information needs.**
The agent must determine *which* internal records (calendars, policies, emails) are needed to satisfy the abstract user request.

### 2. Information Acquisition
**Retrieving required information via tool calls.**
The agent must actively navigate multiple sources to fetch data. It is not "fed" the context; it must go out and get it.

### 3. Integration
**Combining heterogeneous formats and contexts.**
The agent must synthesize data from different formats (JSON, Text, Tables) to generate, filter, and rank final candidates. All constraints are treated as **Hard Constraints** (violations remove a candidate).

---

## 📅 Task Family: Scheduling

The common objective is to **propose N meeting candidates within a given time window.**

### Data Sources
* **Calendar:** Busy intervals (JSON).
* **Organization Policy:**
    * Easy: JSON format.
    * Hard: Long text + machine-readable tags.
* **Communication Threads:**
    * Slack-like text + machine-readable tags for deadlines/bans.
    * Hardest level includes required participants, duration, N count, and tie-break rules.
* **People Directory & Room System:** (Hardest level) Requires joining Name → ID and Room Metadata → Availability JSON.

**Note:** Candidates are generated on a **15-minute grid** to allow deterministic oracle computation.

---

## 📊 Difficulty Levels

| Level | Complexity | Data Sources | Key Challenge |
| :--- | :--- | :--- | :--- |
| **Level 1**<br>(Easy) | **Explicit Sources** | • Calendar<br>• Policy (JSON) | Basic constraint satisfaction with structured data. |
| **Level 2**<br>(Mid) | **Implicit Sources** | • Calendar<br>• Policy (Text+Tags)<br>• Threads (Text+Tags) | **Decomposition:** Task text does not name sources. Agent must deduce where to look. |
| **Level 3**<br>(Hard) | **Cross-Tool Joins** | • All of Level 2<br>• People Directory<br>• Room System | **Integration:** Requires cross-tool joins (People/Rooms) and deterministic ranking (Earliest-first). |

---

## 🔮 Oracle-Based Labeling & Evaluation

MPCBench uses an oracle to produce the gold answer deterministically.

### The Oracle Pipeline
1.  **Tag-Based Processing:** The oracle never parses natural language. It uses machine-readable tags embedded in unstructured sources.
2.  **Pipeline Steps:** Candidate Generation → Constraint Filtering → (L3) Room Join → Deterministic Sorting → Top-N Selection.
3.  **Quality Control:** Instances with fewer than N feasible candidates are discarded and resampled during generation.

### Evaluation Metric
* **F1 Overlap:** Compare model output candidates against Oracle Top-N candidates.
* **Rationales:** The benchmark supports storing rationales, though they are qualitative (not scored yet).

---

## 📂 Repository Structure

```text
.
├── schema/         # Unified JSON schemas for World, Instance, and Oracle
├── generate/       # World + Instance generation (with discard/resample loop)
├── oracle/         # Deterministic oracle engine for gold label generation
├── evaluation/     # Parsing + Scoring (F1)
└── archive/        # Legacy MPCBench implementation (Read-only)
```
