## overall flow

### Data synthesis

[1] Scenario (human-authored spec)
    - Role:
      High-level story and configuration written by a human:
      who is involved, what’s happening, when, and how noisy/complex it should be.

           │
           │  (LLM: data_generation_model)
           ▼

[2] World state 
    - Role:
      Canonical structured “universe” for the scenario:
      people, projects, and expanded sub-scenarios + noise events
      organized into a consistent internal state.

           │
           │  (LLM: data_generation_model)
           ▼

[3] Per-source data 
    - Role:
      Source-specific logs/data (Slack, Gmail, Calendar, Contacts, Jira, Drive, …)
      generated directly from the world state, so that all tools see a
      consistent story across channels.





## How to run the code

#### scenario to world_state

python3 -m generator.world_state_generator --scenario-id scenario_A

#### world_state to raw data

python3 -m generator.run_generation --scenario-id scenario_A

#### generate response of target LLM

python3 -m evaluation.run_single_task --task tasks/planning/planning_task.json --agent-model gpt-4o-mini

#### evaluate the response

python3 -m evaluation.run_task_and_judge --task tasks/planning/planning_task.json --agent-model gpt-4o-mini --judge-model gpt-4o-mini
