"""Contacts data generator module - uses LLM to generate Contacts data from world_state."""

import json
import os
from pathlib import Path
from typing import Dict, Any

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None



def load_env_file(env_path: Path = None) -> None:
    """Load environment variables from .env file."""
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


def generate_contacts_data(world_state: Dict[str, Any], data_generation_model: str = None) -> Dict[str, Any]:
    """
    Generate a contacts store from world_state using LLM.
    Must conform to schemas/contacts_schema.json.
    
    Args:
        world_state: Scenario-centric world_state dict (no per_source_plans)
        data_generation_model: Model name (if None, loads from config)
        
    Returns:
        Dict with contacts array
    """
    if OpenAI is None:
        raise ImportError("OpenAI library is not installed. Install it with: pip install openai")
    
    # Load environment variables
    load_env_file()
    
    if data_generation_model is None:
        # Load data_generation_model from model_config.json at repo root
        repo_root = Path(__file__).resolve().parent.parent
        config_path = repo_root / "model_config.json"
        if not config_path.exists():
            raise FileNotFoundError(f"Model config file not found: {config_path}")
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        data_generation_model = config.get("data_generation_model") or config.get("world_state_model")
        if not data_generation_model:
            raise ValueError("data_generation_model (or world_state_model) not specified in model_config.json")
    
    scenario_id = world_state.get("scenario_id", "scenario_A")
    print(f"[contacts_generator] Start: scenario_id={scenario_id}, model={data_generation_model}")
    
    # Load schema
    schema_path = Path("schemas/contacts_schema.json")
    with open(schema_path, 'r', encoding='utf-8') as f:
        contacts_schema = json.load(f)
    
    # Build prompt context from world_state
    people = world_state.get("people", [])
    sub_scenarios_expanded = world_state.get("sub_scenarios_expanded", [])
    noise_scenarios = world_state.get("noise_scenarios", [])
    
    # Load prompt config
    repo_root = Path(__file__).resolve().parent.parent
    config_path = repo_root / "prompt_config.json"
    with open(config_path, 'r', encoding='utf-8') as f:
        prompt_config = json.load(f)
    
    contacts_prompts = prompt_config["generator"]["contacts"]
    system_prompt = contacts_prompts["system_prompt"]
    
    # Build user prompt
    people_json = json.dumps(people, indent=2, ensure_ascii=False)
    sub_scenarios_expanded_json = json.dumps(sub_scenarios_expanded, indent=2, ensure_ascii=False)
    noise_scenarios_json = json.dumps(noise_scenarios, indent=2, ensure_ascii=False)
    contacts_schema_json = json.dumps(contacts_schema, indent=2, ensure_ascii=False)
    
    user_prompt = contacts_prompts["user_prompt_template"].format(
        people_json=people_json,
        sub_scenarios_expanded_json=sub_scenarios_expanded_json,
        noise_scenarios_json=noise_scenarios_json,
        contacts_schema_json=contacts_schema_json
    )

    # Initialize OpenAI client
    client = OpenAI()
    
    # Call LLM
    print(f"[contacts_generator] Calling LLM to generate Contacts data...")
    response = client.chat.completions.create(
        model=data_generation_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.7,
    )
    
    # Extract and parse response
    content = response.choices[0].message.content.strip()
    
    # Remove markdown code fences if present
    if content.startswith("```"):
        lines = content.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines[-1].startswith("```"):
            lines = lines[:-1]
        content = "\n".join(lines)
    
    try:
        contacts_data = json.loads(content)
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse LLM response as JSON: {e}\nResponse was: {content[:500]}")
    
    # Ensure required fields exist
    if "contacts" not in contacts_data:
        # Fallback: create contacts from world_state people
        contacts_data["contacts"] = [
            {
                "id": person["id"],
                "name": person["name"],
                "email": person["email"]
            }
            for person in people
        ]
    
    contacts_count = len(contacts_data.get("contacts", []))
    print(f"[contacts_generator] Result: contacts={contacts_count}")
    
    return contacts_data
