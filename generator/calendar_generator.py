"""Calendar data generator module - uses LLM to generate Calendar data from world_state."""

import json
import os
from pathlib import Path
from typing import Dict, Any

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

from common.log_utils import log_llm_run, build_llm_log_payload



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


def generate_calendar_data(world_state: Dict[str, Any], data_generation_model: str = None) -> Dict[str, Any]:
    """
    Generate Google Calendar-like events from world_state using LLM.
    Must conform to schemas/calendar_schema.json.
    
    Args:
        world_state: Scenario-centric world_state dict (no per_source_plans)
        data_generation_model: Model name (if None, loads from config)
        
    Returns:
        Dict with events and calendars arrays
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
    
    scenario_id = world_state.get("scenario_id")
    if not scenario_id:
        raise ValueError("world_state must contain 'scenario_id' field")
    print(f"[calendar_generator] Start: scenario_id={scenario_id}, model={data_generation_model}")
    
    # Load schema
    schema_path = Path("schemas/calendar_schema.json")
    with open(schema_path, 'r', encoding='utf-8') as f:
        calendar_schema = json.load(f)
    
    # Build prompt context from world_state
    sub_scenarios_expanded = world_state.get("sub_scenarios_expanded", [])
    noise_scenarios = world_state.get("noise_scenarios", [])
    people = world_state.get("people", [])
    global_settings = world_state.get("global_settings", {})
    noise_level = world_state.get("noise_level", 0.0)
    depth = world_state.get("depth", 0.0)
    
    # Load prompt config
    repo_root = Path(__file__).resolve().parent.parent
    config_path = repo_root / "prompt_config.json"
    with open(config_path, 'r', encoding='utf-8') as f:
        prompt_config = json.load(f)
    
    calendar_prompts = prompt_config["generator"]["calendar"]
    system_prompt = calendar_prompts["system_prompt"]
    
    # Build user prompt
    sub_scenarios_expanded_json = json.dumps(sub_scenarios_expanded, indent=2, ensure_ascii=False)
    noise_scenarios_json = json.dumps(noise_scenarios, indent=2, ensure_ascii=False)
    people_json = json.dumps(people, indent=2, ensure_ascii=False)
    global_settings_json = json.dumps(global_settings, indent=2, ensure_ascii=False)
    calendar_schema_json = json.dumps(calendar_schema, indent=2, ensure_ascii=False)
    noise_level_desc = 'Generate minimal noise' if noise_level < 0.3 else 'Generate moderate noise' if noise_level < 0.7 else 'Generate significant noise'
    depth_desc = 'Make events direct' if depth < 0.3 else 'Make events moderately indirect' if depth < 0.7 else 'Make events highly indirect, requiring multi-step chaining'
    
    user_prompt = calendar_prompts["user_prompt_template"].format(
        sub_scenarios_expanded_json=sub_scenarios_expanded_json,
        noise_scenarios_json=noise_scenarios_json,
        people_json=people_json,
        global_settings_json=global_settings_json,
        noise_level=noise_level,
        noise_level_desc=noise_level_desc,
        depth=depth,
        depth_desc=depth_desc,
        calendar_schema_json=calendar_schema_json
    )

    # Initialize OpenAI client
    client = OpenAI()
    
    # Set up LLM logging directory
    repo_root = Path(__file__).resolve().parent.parent
    llm_log_dir = repo_root / "generator" / "logs" / "llm"
    
    # Call LLM
    print(f"[calendar_generator] Calling LLM to generate Calendar data...")
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]
    response = client.chat.completions.create(
        model=data_generation_model,
        messages=messages,
        temperature=0.9,
    )
    
    # Log this LLM call
    log_payload = build_llm_log_payload(
        model=data_generation_model,
        component="calendar_generator",
        messages=messages,
        response=response,
        scenario_id=scenario_id,
        extra_params={"temperature": 0.7},
    )
    log_file_name = f"{scenario_id}__calendar__llm.json"
    log_llm_run(llm_log_dir, log_file_name, log_payload)
    
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
        calendar_data = json.loads(content)
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse LLM response as JSON: {e}\nResponse was: {content[:500]}")
    
    # Ensure required fields exist
    if "events" not in calendar_data:
        calendar_data["events"] = []
    if "calendars" not in calendar_data:
        # Create calendars from world_state people
        calendar_data["calendars"] = [
            {
                "id": person["id"],
                "email": person["email"]
            }
            for person in people
        ]
    
    events_count = len(calendar_data.get("events", []))
    calendars_count = len(calendar_data.get("calendars", []))
    print(f"[calendar_generator] Result: events={events_count}, calendars={calendars_count}")
    
    return calendar_data
