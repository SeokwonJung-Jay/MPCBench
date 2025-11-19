"""Slack data generator module - uses LLM to generate Slack data from world_state."""

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


def generate_slack_data(world_state: Dict[str, Any], data_generation_model: str = None) -> Dict[str, Any]:
    """
    Generate a Slack workspace JSON document from world_state using LLM.
    Must conform to schemas/slack_schema.json.
    
    Args:
        world_state: Scenario-centric world_state dict (no per_source_plans)
        data_generation_model: Model name (if None, loads from config)
        
    Returns:
        Dict with workspace_name, channels, messages, users
    """
    if OpenAI is None:
        raise ImportError("OpenAI library is not installed. Install it with: pip install openai")
    
    # Load environment variables
    load_env_file()
    
    if data_generation_model is None:
        data_generation_model = get_data_generation_model()
    
    scenario_id = world_state.get("scenario_id", "scenario_A")
    print(f"[slack_generator] Start: scenario_id={scenario_id}, model={data_generation_model}")
    
    # Load schema
    schema_path = Path("schemas/slack_schema.json")
    with open(schema_path, 'r', encoding='utf-8') as f:
        slack_schema = json.load(f)
    
    # Build prompt context from world_state
    sub_scenarios_expanded = world_state.get("sub_scenarios_expanded", [])
    noise_scenarios = world_state.get("noise_scenarios", [])
    people = world_state.get("people", [])
    noise_level = world_state.get("noise_level", 0.0)
    depth = world_state.get("depth", 0.0)
    
    # Build system prompt
    system_prompt = """You are a Slack data generator for a workplace benchmark. Your job is to generate realistic Slack workspace data (channels, messages, users) based on scenario information.

The output must be valid JSON matching the Slack schema with:
- workspace_name: string
- channels: array of {id, name}
- messages: array of {id, channel_id, user_id, text, timestamp}
- users: array of {id, name, email}

Generate messages that reflect:
- Events from sub_scenarios_expanded (core scenario events)
- Events from noise_scenarios (unrelated workplace activity)
- Respect noise_level: 0 = minimal noise, 1 = lots of unrelated messages
- Respect depth: 0 = direct/obvious messages, 1 = indirect/multi-step conversations

You must output ONLY valid JSON matching the schema. Do not include markdown code fences."""

    # Build user prompt
    user_prompt = f"""Generate Slack workspace data from this world_state:

Sub-scenarios (core events):
{json.dumps(sub_scenarios_expanded, indent=2, ensure_ascii=False)}

Noise scenarios (unrelated events):
{json.dumps(noise_scenarios, indent=2, ensure_ascii=False)}

People:
{json.dumps(people, indent=2, ensure_ascii=False)}

Parameters:
- noise_level={noise_level}: {'Generate minimal noise' if noise_level < 0.3 else 'Generate moderate noise' if noise_level < 0.7 else 'Generate significant noise'}
- depth={depth}: {'Make messages direct' if depth < 0.3 else 'Make messages moderately indirect' if depth < 0.7 else 'Make messages highly indirect, requiring multi-step chaining'}

Target schema:
{json.dumps(slack_schema, indent=2, ensure_ascii=False)}

Output the complete Slack JSON now."""

    # Initialize OpenAI client
    client = OpenAI()
    
    # Call LLM
    print(f"[slack_generator] Calling LLM to generate Slack data...")
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
        slack_data = json.loads(content)
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse LLM response as JSON: {e}\nResponse was: {content[:500]}")
    
    # Ensure required fields exist
    if "workspace_name" not in slack_data:
        slack_data["workspace_name"] = f"{scenario_id.replace('_', ' ').title()} Workspace"
    if "channels" not in slack_data:
        slack_data["channels"] = []
    if "messages" not in slack_data:
        slack_data["messages"] = []
    if "users" not in slack_data:
        # Create users from world_state people
        slack_data["users"] = [
            {
                "id": person["id"],
                "name": person["name"],
                "email": person["email"]
            }
            for person in people
        ]
    
    channels_count = len(slack_data.get("channels", []))
    messages_count = len(slack_data.get("messages", []))
    users_count = len(slack_data.get("users", []))
    print(f"[slack_generator] Result: channels={channels_count}, messages={messages_count}, users={users_count}")
    
    return slack_data
