"""Jira data generator module - uses LLM to generate Jira data from world_state."""

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


def generate_jira_data(world_state: Dict[str, Any], data_generation_model: str = None) -> Dict[str, Any]:
    """
    Generate Jira-like issues data from world_state using LLM.
    Must conform to schemas/jira_schema.json.
    
    Args:
        world_state: Scenario-centric world_state dict (no per_source_plans)
        data_generation_model: Model name (if None, loads from config)
        
    Returns:
        Dict with projects and issues arrays
    """
    if OpenAI is None:
        raise ImportError("OpenAI library is not installed. Install it with: pip install openai")
    
    # Load environment variables
    load_env_file()
    
    if data_generation_model is None:
        data_generation_model = get_data_generation_model()
    
    scenario_id = world_state.get("scenario_id", "scenario_A")
    print(f"[jira_generator] Start: scenario_id={scenario_id}, model={data_generation_model}")
    
    # Load schema
    schema_path = Path("schemas/jira_schema.json")
    with open(schema_path, 'r', encoding='utf-8') as f:
        jira_schema = json.load(f)
    
    # Build prompt context from world_state
    projects = world_state.get("projects", [])
    sub_scenarios_expanded = world_state.get("sub_scenarios_expanded", [])
    noise_scenarios = world_state.get("noise_scenarios", [])
    noise_level = world_state.get("noise_level", 0.0)
    depth = world_state.get("depth", 0.0)
    
    # Build system prompt
    system_prompt = """You are a Jira data generator for a workplace benchmark. Your job is to generate realistic Jira issue data based on scenario information.

The output must be valid JSON matching the Jira schema with:
- projects: array of {key, name, fixVersions[]}
- issues: array of {key, summary, status, updated (optional), fixVersions[] (optional), project: {key}}

Generate Jira issues that reflect:
- Seed issues from projects.jira_seeds (must be included)
- Events from sub_scenarios_expanded (core scenario events related to issues)
- Events from noise_scenarios (unrelated workplace issues)
- Respect noise_level: 0 = minimal noise, 1 = lots of unrelated issues
- Respect depth: 0 = direct/obvious issue updates, 1 = indirect/multi-step issue tracking

You must output ONLY valid JSON matching the schema. Do not include markdown code fences."""

    # Build user prompt
    user_prompt = f"""Generate Jira issue data from this world_state:

Projects (with jira_seeds that must be included):
{json.dumps(projects, indent=2, ensure_ascii=False)}

Sub-scenarios (core events):
{json.dumps(sub_scenarios_expanded, indent=2, ensure_ascii=False)}

Noise scenarios (unrelated events):
{json.dumps(noise_scenarios, indent=2, ensure_ascii=False)}

Parameters:
- noise_level={noise_level}: {'Generate minimal noise' if noise_level < 0.3 else 'Generate moderate noise' if noise_level < 0.7 else 'Generate significant noise'}
- depth={depth}: {'Make issue updates direct' if depth < 0.3 else 'Make issue updates moderately indirect' if depth < 0.7 else 'Make issue updates highly indirect, requiring multi-step chaining'}

Target schema:
{json.dumps(jira_schema, indent=2, ensure_ascii=False)}

Output the complete Jira JSON now."""

    # Initialize OpenAI client
    client = OpenAI()
    
    # Call LLM
    print(f"[jira_generator] Calling LLM to generate Jira data...")
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
        jira_data = json.loads(content)
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse LLM response as JSON: {e}\nResponse was: {content[:500]}")
    
    # Ensure required fields exist
    if "projects" not in jira_data:
        # Fallback: create projects from world_state
        jira_data["projects"] = [
            {
                "key": proj.get("project_key", "APP"),
                "name": proj.get("name", ""),
                "fixVersions": []
            }
            for proj in projects
        ]
    if "issues" not in jira_data:
        # Fallback: create issues from jira_seeds
        issues = []
        for project in projects:
            project_key = project.get("project_key", "APP")
            for seed in project.get("jira_seeds", []):
                issues.append({
                    "key": seed.get("issue_key", ""),
                    "summary": seed.get("summary", ""),
                    "status": seed.get("status", ""),
                    "project": {"key": project_key}
                })
        jira_data["issues"] = issues
    
    projects_count = len(jira_data.get("projects", []))
    issues_count = len(jira_data.get("issues", []))
    print(f"[jira_generator] Result: projects={projects_count}, issues={issues_count}")
    
    return jira_data
