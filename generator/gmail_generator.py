"""Gmail data generator module - uses LLM to generate Gmail data from world_state."""

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


def generate_gmail_data(world_state: Dict[str, Any], data_generation_model: str = None) -> Dict[str, Any]:
    """
    Generate Gmail-style data (threads and messages) from world_state using LLM.
    Must conform to schemas/gmail_schema.json.
    
    Args:
        world_state: Scenario-centric world_state dict (no per_source_plans)
        data_generation_model: Model name (if None, loads from config)
        
    Returns:
        Dict with threads array
    """
    if OpenAI is None:
        raise ImportError("OpenAI library is not installed. Install it with: pip install openai")
    
    # Load environment variables
    load_env_file()
    
    if data_generation_model is None:
        data_generation_model = get_data_generation_model()
    
    scenario_id = world_state.get("scenario_id", "scenario_A")
    print(f"[gmail_generator] Start: scenario_id={scenario_id}, model={data_generation_model}")
    
    # Load schema
    schema_path = Path("schemas/gmail_schema.json")
    with open(schema_path, 'r', encoding='utf-8') as f:
        gmail_schema = json.load(f)
    
    # Build prompt context from world_state
    sub_scenarios_expanded = world_state.get("sub_scenarios_expanded", [])
    noise_scenarios = world_state.get("noise_scenarios", [])
    people = world_state.get("people", [])
    noise_level = world_state.get("noise_level", 0.0)
    depth = world_state.get("depth", 0.0)
    
    # Build system prompt
    system_prompt = """You are a Gmail data generator for a workplace benchmark. Your job is to generate realistic email thread data based on scenario information.

The output must be valid JSON matching the Gmail schema with:
- threads: array of {id, subject, messages[]}
  - messages: array of {id, from, to[], subject, body, date}

Generate email threads that reflect:
- Events from sub_scenarios_expanded (core scenario events)
- Events from noise_scenarios (unrelated workplace activity)
- Respect noise_level: 0 = minimal noise, 1 = lots of unrelated emails
- Respect depth: 0 = direct/obvious emails, 1 = indirect/multi-step conversations

You must output ONLY valid JSON matching the schema. Do not include markdown code fences."""

    # Build user prompt
    user_prompt = f"""Generate Gmail thread data from this world_state:

Sub-scenarios (core events):
{json.dumps(sub_scenarios_expanded, indent=2, ensure_ascii=False)}

Noise scenarios (unrelated events):
{json.dumps(noise_scenarios, indent=2, ensure_ascii=False)}

People:
{json.dumps(people, indent=2, ensure_ascii=False)}

Parameters:
- noise_level={noise_level}: {'Generate minimal noise' if noise_level < 0.3 else 'Generate moderate noise' if noise_level < 0.7 else 'Generate significant noise'}
- depth={depth}: {'Make emails direct' if depth < 0.3 else 'Make emails moderately indirect' if depth < 0.7 else 'Make emails highly indirect, requiring multi-step chaining'}

Target schema:
{json.dumps(gmail_schema, indent=2, ensure_ascii=False)}

Output the complete Gmail JSON now."""

    # Initialize OpenAI client
    client = OpenAI()
    
    # Call LLM
    print(f"[gmail_generator] Calling LLM to generate Gmail data...")
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
        gmail_data = json.loads(content)
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse LLM response as JSON: {e}\nResponse was: {content[:500]}")
    
    # Ensure required fields exist
    if "threads" not in gmail_data:
        gmail_data["threads"] = []
    
    threads_count = len(gmail_data.get("threads", []))
    total_messages = sum(len(t.get("messages", [])) for t in gmail_data.get("threads", []))
    print(f"[gmail_generator] Result: threads={threads_count}, messages={total_messages}")
    
    return gmail_data
