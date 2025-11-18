"""Main script to run data generation."""

import argparse
import json
from pathlib import Path

from generator.propagation_engine import build_event_plans
from generator.slack_generator import generate_slack_data
from generator.gmail_generator import generate_gmail_data
from generator.calendar_generator import generate_calendar_data
from generator.contacts_generator import generate_contacts_data
from generator.jira_generator import generate_jira_data
from generator.drive_generator import generate_drive_data


def main():
    """Generate all source data files from world_state."""
    parser = argparse.ArgumentParser(description="Generate source data files from world_state")
    parser.add_argument(
        "--scenario-id",
        type=str,
        default="scenario_A",
        help="Scenario identifier (default: scenario_A)"
    )
    args = parser.parse_args()
    scenario_id = args.scenario_id
    
    print(f"[run_generation] Starting data generation for scenario: {scenario_id}")
    
    # Load world_state
    world_state_path = Path(f"data/{scenario_id}_world_state.json")
    print(f"[run_generation] Resolved world_state path: {world_state_path}")
    
    if not world_state_path.exists():
        raise FileNotFoundError(
            f"World state file not found: {world_state_path}\n"
            f"Run 'python -m generator.world_state_generator --scenario-id {scenario_id}' first."
        )
    
    print(f"[run_generation] Loading world_state from {world_state_path}...")
    with open(world_state_path, 'r', encoding='utf-8') as f:
        world_state = json.load(f)
    print(f"[run_generation] World_state loaded successfully")
    
    # Extract per_source_plans from LLM-generated world_state
    print(f"[run_generation] Building per-source event plans...")
    plans = build_event_plans(world_state)
    print(f"[run_generation] Plans built. Counts per source:")
    print(f"  - Slack plans: {len(plans.get('slack_plans', []))}")
    print(f"  - Gmail plans: {len(plans.get('gmail_plans', []))}")
    print(f"  - Calendar plans: {len(plans.get('calendar_plans', []))}")
    print(f"  - Contacts plans: {len(plans.get('contacts_plans', []))}")
    print(f"  - Jira plans: {len(plans.get('jira_plans', []))}")
    print(f"  - Drive plans: {len(plans.get('drive_plans', []))}")
    
    # Generate data for each source
    print(f"[run_generation] Generating Slack data...")
    slack_data = generate_slack_data(world_state, plans["slack_plans"])
    
    print(f"[run_generation] Generating Gmail data...")
    gmail_data = generate_gmail_data(world_state, plans["gmail_plans"])
    
    print(f"[run_generation] Generating Calendar data...")
    calendar_data = generate_calendar_data(world_state, plans["calendar_plans"])
    
    print(f"[run_generation] Generating Contacts data...")
    contacts_data = generate_contacts_data(world_state, plans["contacts_plans"])
    
    print(f"[run_generation] Generating Jira data...")
    jira_data = generate_jira_data(world_state, plans["jira_plans"])
    
    print(f"[run_generation] Generating Drive data...")
    drive_data = generate_drive_data(world_state, plans["drive_plans"])
    
    # Write output files (using scenario_id in filename)
    output_dir = Path("data")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    slack_output_path = output_dir / f"{scenario_id}_slack.json"
    print(f"[run_generation] Writing Slack data to {slack_output_path}...")
    with open(slack_output_path, 'w', encoding='utf-8') as f:
        json.dump(slack_data, f, indent=2, ensure_ascii=False)
    
    gmail_output_path = output_dir / f"{scenario_id}_gmail.json"
    print(f"[run_generation] Writing Gmail data to {gmail_output_path}...")
    with open(gmail_output_path, 'w', encoding='utf-8') as f:
        json.dump(gmail_data, f, indent=2, ensure_ascii=False)
    
    calendar_output_path = output_dir / f"{scenario_id}_calendar.json"
    print(f"[run_generation] Writing Calendar data to {calendar_output_path}...")
    with open(calendar_output_path, 'w', encoding='utf-8') as f:
        json.dump(calendar_data, f, indent=2, ensure_ascii=False)
    
    contacts_output_path = output_dir / f"{scenario_id}_contacts.json"
    print(f"[run_generation] Writing Contacts data to {contacts_output_path}...")
    with open(contacts_output_path, 'w', encoding='utf-8') as f:
        json.dump(contacts_data, f, indent=2, ensure_ascii=False)
    
    jira_output_path = output_dir / f"{scenario_id}_jira.json"
    print(f"[run_generation] Writing Jira data to {jira_output_path}...")
    with open(jira_output_path, 'w', encoding='utf-8') as f:
        json.dump(jira_data, f, indent=2, ensure_ascii=False)
    
    drive_output_path = output_dir / f"{scenario_id}_drive.json"
    print(f"[run_generation] Writing Drive data to {drive_output_path}...")
    with open(drive_output_path, 'w', encoding='utf-8') as f:
        json.dump(drive_data, f, indent=2, ensure_ascii=False)
    
    # Print summary
    scenario_name = world_state.get("scenario_id", scenario_id)
    print(f"[run_generation] Summary for {scenario_name}:")
    print(f"  {scenario_id}_slack.json: {len(slack_data.get('channels', []))} channels, {len(slack_data.get('messages', []))} messages")
    print(f"  {scenario_id}_gmail.json: {len(gmail_data.get('threads', []))} threads")
    print(f"  {scenario_id}_calendar.json: {len(calendar_data.get('events', []))} events")
    print(f"  {scenario_id}_contacts.json: {len(contacts_data.get('contacts', []))} contacts")
    print(f"  {scenario_id}_jira.json: {len(jira_data.get('issues', []))} issues")
    print(f"  {scenario_id}_drive.json: {len(drive_data.get('files', []))} files")
    print(f"[run_generation] Done.")


if __name__ == "__main__":
    main()
