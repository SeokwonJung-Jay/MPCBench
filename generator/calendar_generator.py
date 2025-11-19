"""Calendar data generator module - uses LLM to generate Calendar data from world_state."""

import json
import os
from pathlib import Path
from typing import Dict, Any

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

from model_config import get_data_generation_model


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
        data_generation_model = get_data_generation_model()
    
    scenario_id = world_state.get("scenario_id", "scenario_A")
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
    
    # Build system prompt
    system_prompt = """You are a Calendar data generator for a workplace benchmark. Your job is to generate realistic calendar event data based on scenario information.

The output must be valid JSON matching the Calendar schema with:
- events: array of {id, title, start, end, attendees[]}
- calendars: array of {id, email} (one per person)

Generate calendar events that reflect:
- Events from sub_scenarios_expanded (core scenario events, especially meetings)
- Events from noise_scenarios (unrelated workplace meetings/events)
- Respect noise_level: 0 = minimal noise, 1 = lots of unrelated events
- Respect depth: 0 = direct/obvious events, 1 = indirect/multi-step scheduling

You must output ONLY valid JSON matching the schema. Do not include markdown code fences."""

    # Build user prompt
    user_prompt = f"""Generate Calendar event data from this world_state:

Sub-scenarios (core events):
{json.dumps(sub_scenarios_expanded, indent=2, ensure_ascii=False)}

Noise scenarios (unrelated events):
{json.dumps(noise_scenarios, indent=2, ensure_ascii=False)}

People:
{json.dumps(people, indent=2, ensure_ascii=False)}

Global settings:
{json.dumps(global_settings, indent=2, ensure_ascii=False)}

Parameters:
- noise_level={noise_level}: {'Generate minimal noise' if noise_level < 0.3 else 'Generate moderate noise' if noise_level < 0.7 else 'Generate significant noise'}
- depth={depth}: {'Make events direct' if depth < 0.3 else 'Make events moderately indirect' if depth < 0.7 else 'Make events highly indirect, requiring multi-step chaining'}

Target schema:
{json.dumps(calendar_schema, indent=2, ensure_ascii=False)}

Output the complete Calendar JSON now."""

    # Initialize OpenAI client
    client = OpenAI()
    
    # Call LLM
    print(f"[calendar_generator] Calling LLM to generate Calendar data...")
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
