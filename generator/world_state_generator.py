"""World state generator module - uses LLM to generate world_state from scenario."""

import json
import os
from pathlib import Path
from typing import Dict, Any

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

from generator.model_config import load_world_state_model


def load_env_file(env_path: Path = None) -> None:
    """
    Load environment variables from .env file.
    
    Args:
        env_path: Path to .env file. If None, looks for .env in project root.
    """
    if env_path is None:
        project_root = Path(__file__).resolve().parent.parent
        env_path = project_root / ".env"
    
    if not env_path.exists():
        return
    
    with open(env_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            if '=' in line:
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip()
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]
                elif value.startswith("'") and value.endswith("'"):
                    value = value[1:-1]
                
                if key and key not in os.environ:
                    os.environ[key] = value


def generate_world_state(scenario_id: str = "scenario_A") -> Dict[str, Any]:
    """
    Generate world_state from scenario using LLM.
    
    The LLM is responsible for:
    - Enriching abstract sub_scenarios into concrete timeline events
    - Creating per_source_plans for each data source
    - Incorporating noise_level and depth parameters
    
    Args:
        scenario_id: Scenario identifier (e.g., "scenario_A")
        
    Returns:
        dict: The generated world_state dictionary
    """
    if OpenAI is None:
        raise ImportError("OpenAI library is not installed. Install it with: pip install openai")
    
    # Load environment variables
    load_env_file()
    
    # Load scenario
    scenario_path = Path(f"scenarios/{scenario_id}.json")
    if not scenario_path.exists():
        raise FileNotFoundError(f"Scenario file not found: {scenario_path}")
    
    with open(scenario_path, 'r', encoding='utf-8') as f:
        scenario = json.load(f)
    
    # Load world_state_model
    world_state_model = load_world_state_model()
    
    # Initialize OpenAI client
    client = OpenAI()
    
    # Build system prompt
    system_prompt = """You are a world state generator for a workplace benchmark. Your job is to transform an abstract scenario into a concrete, detailed world_state JSON.

The world_state should include:
1. All metadata from the scenario (scenario_id, description, noise_level, depth, global_settings, people, projects)
2. sub_scenarios_expanded: For each abstract sub_scenario from the input scenario, create a concrete expanded version with:
   - Concrete ISO datetime timestamps
   - Specific participant IDs/emails
   - Detailed event descriptions
   - Any seeds needed for data generation
   - This array should contain ONLY the expanded versions of the sub_scenarios listed in the input scenario
3. noise_scenarios: An array of noise-only scenario objects that are NOT part of the core sub_scenarios:
   - These should be realistic but unrelated workplace events/messages/activities
   - Each noise scenario should have similar structure to sub_scenarios_expanded (id, type, timestamps, participants, etc.)
   - The number of noise scenarios should scale with the noise_level parameter
4. per_source_plans: A structure with plans for each data source:
   - slack_plans: List of plans for Slack messages (may include both sub-scenario and noise plans)
   - gmail_plans: List of plans for email threads (may include both sub-scenario and noise plans)
   - calendar_plans: List of plans for calendar events (may include both sub-scenario and noise plans)
   - contacts_plans: List of plans for contacts (may include both sub-scenario and noise plans)
   - jira_plans: List of plans for Jira issues (may include both sub-scenario and noise plans)
   - drive_plans: List of plans for Drive files (may include both sub-scenario and noise plans)

IMPORTANT PARAMETERS:
- noise_level (0-1): Controls amount of unrelated/off-task data
  * 0 = almost no noise, only data directly relevant to sub_scenarios (noise_scenarios should be empty or minimal)
  * 1 = lots of unrelated messages/events/files (still realistic) (noise_scenarios should contain many entries)
- depth (0-1): Controls how indirect the evidence is
  * 0 = sub_scenario realized directly (e.g., one clear Slack message)
  * 1 = sub_scenario requires multi-step, multi-source chaining to infer
  * Intermediate values interpolate behavior

CRITICAL: sub_scenarios_expanded must correspond exactly to the sub_scenarios in the input scenario. All other unrelated scenarios should go in noise_scenarios.

You must output ONLY valid JSON matching the world_state schema. Do not include markdown code fences."""

    # Build user prompt with scenario
    user_prompt = f"""Generate a world_state JSON from this scenario:

{json.dumps(scenario, indent=2, ensure_ascii=False)}

Remember:
- noise_level={scenario.get('noise_level', 0)}: {'Generate minimal noise' if scenario.get('noise_level', 0) < 0.3 else 'Generate moderate noise' if scenario.get('noise_level', 0) < 0.7 else 'Generate significant noise'}
- depth={scenario.get('depth', 0)}: {'Make evidence direct' if scenario.get('depth', 0) < 0.3 else 'Make evidence moderately indirect' if scenario.get('depth', 0) < 0.7 else 'Make evidence highly indirect, requiring multi-source chaining'}

Output the complete world_state JSON now."""

    # Call LLM
    response = client.chat.completions.create(
        model=world_state_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.7,
    )
    
    # Extract response
    content = response.choices[0].message.content.strip()
    
    # Parse JSON (handle markdown code fences if present)
    if content.startswith("```"):
        lines = content.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines[-1].startswith("```"):
            lines = lines[:-1]
        content = "\n".join(lines)
    
    try:
        world_state = json.loads(content)
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse LLM response as JSON: {e}\nResponse was: {content[:500]}")
    
    # Basic validation
    required_keys = ["scenario_id", "people", "per_source_plans"]
    for key in required_keys:
        if key not in world_state:
            raise ValueError(f"Generated world_state missing required key: {key}")
    
    # Ensure scenario metadata is preserved
    world_state["scenario_id"] = scenario.get("scenario_id", scenario_id)
    world_state["description"] = scenario.get("description", "")
    world_state["noise_level"] = scenario.get("noise_level", 0.0)
    world_state["depth"] = scenario.get("depth", 0.0)
    world_state["global_settings"] = scenario.get("global_settings", {})
    
    # Ensure sub_scenarios_expanded and noise_scenarios exist and are properly separated
    # Get the list of sub_scenario IDs from the input scenario
    input_sub_scenario_ids = {sub.get("id") for sub in scenario.get("sub_scenarios", [])}
    
    # Initialize if missing
    if "sub_scenarios_expanded" not in world_state:
        world_state["sub_scenarios_expanded"] = []
    if "noise_scenarios" not in world_state:
        world_state["noise_scenarios"] = []
    
    # Post-process to ensure proper separation:
    # If the LLM mixed them, try to separate based on sub_scenario IDs
    # First, collect all scenarios that might be mixed
    all_scenarios = []
    
    # Check if sub_scenarios_expanded contains the right ones
    sub_scenarios_expanded = world_state.get("sub_scenarios_expanded", [])
    for sub in sub_scenarios_expanded:
        sub_id = sub.get("id", "")
        # If this ID matches an input sub_scenario, it's correct
        # Otherwise, it might be noise
        if sub_id not in input_sub_scenario_ids:
            # This might be noise, move it
            all_scenarios.append(("noise", sub))
        else:
            all_scenarios.append(("real", sub))
    
    # Check noise_scenarios - they should all be noise
    noise_scenarios = world_state.get("noise_scenarios", [])
    for noise in noise_scenarios:
        noise_id = noise.get("id", "")
        # If it matches an input sub_scenario ID, it's misclassified
        if noise_id in input_sub_scenario_ids:
            all_scenarios.append(("real", noise))
        else:
            all_scenarios.append(("noise", noise))
    
    # Rebuild the arrays properly
    world_state["sub_scenarios_expanded"] = [s for tag, s in all_scenarios if tag == "real"]
    world_state["noise_scenarios"] = [s for tag, s in all_scenarios if tag == "noise"]
    
    # Ensure we have at least the expanded versions of input sub_scenarios
    # If any are missing, add placeholders (though ideally the LLM should generate them)
    for input_sub in scenario.get("sub_scenarios", []):
        input_id = input_sub.get("id")
        found = any(s.get("id") == input_id for s in world_state["sub_scenarios_expanded"])
        if not found:
            # Add a basic expanded version
            world_state["sub_scenarios_expanded"].append({
                "id": input_id,
                "type": input_sub.get("type", "unknown"),
                "abstract_description": input_sub.get("abstract_description", ""),
                "note": "Auto-generated placeholder - LLM should have expanded this"
            })
    
    # Write to output file
    output_path = Path(f"data/{scenario_id}_world_state.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(world_state, f, indent=2, ensure_ascii=False)
    
    print(f"Generated world_state for {scenario_id} and saved to {output_path}")
    
    return world_state


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate world_state from scenario using LLM")
    parser.add_argument(
        "--scenario-id",
        type=str,
        default="scenario_A",
        help="Scenario identifier (default: scenario_A)"
    )
    args = parser.parse_args()
    
    generate_world_state(scenario_id=args.scenario_id)
