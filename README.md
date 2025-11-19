### scenario to world_state

python3 -m generator.world_state_generator --scenario-id scenario_A

### world_state to raw data

python3 -m generator.run_generation --scenario-id scenario_A

### generate response of target LLM

python3 -m evaluation.run_single_task --task tasks/planning/planning_task.json --agent-model gpt-4o-mini

### evaluate the response

python3 -m evaluation.run_task_and_judge --task tasks/planning/planning_task.json --agent-model gpt-4o-mini --judge-model gpt-4o-mini
