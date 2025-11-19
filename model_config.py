"""Unified model configuration for MPCBench.

This module provides a single source of truth for all model configurations:
- data_generation_model: Used for world_state generation and per-source data generation
- agent_models: Used by evaluation agents (run_single_task)
- judge_models: Used by evaluation judges (judge_runner)
"""

import json
from pathlib import Path
from typing import List


def load_model_config(config_path: Path = None) -> dict:
    """
    Load model configuration from JSON file.
    
    Args:
        config_path: Path to config file. If None, uses evaluation/model_config.json
        
    Returns:
        Dict with keys: data_generation_model, agent_models, judge_models
    """
    if config_path is None:
        config_path = Path("evaluation/model_config.json")
    
    if not config_path.exists():
        raise FileNotFoundError(f"Model config file not found: {config_path}")
    
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    return config


def get_data_generation_model(config_path: Path = None) -> str:
    """
    Get the data generation model name.
    
    This model is used for:
    - Generating world_state from scenarios (LLM #1)
    - Generating per-source data from world_state (LLM #2)
    
    Args:
        config_path: Path to config file. If None, uses evaluation/model_config.json
        
    Returns:
        Model name string (e.g., "gpt-4o-mini")
        
    Raises:
        ValueError: If data_generation_model field is missing
    """
    config = load_model_config(config_path)
    
    # Support both old name (world_state_model) and new name (data_generation_model)
    model = config.get("data_generation_model") or config.get("world_state_model")
    
    if not model:
        raise ValueError("data_generation_model (or world_state_model) not specified in model config")
    
    return model


def get_agent_models(config_path: Path = None) -> List[str]:
    """
    Get list of agent model names.
    
    Args:
        config_path: Path to config file. If None, uses evaluation/model_config.json
        
    Returns:
        List of model name strings
    """
    config = load_model_config(config_path)
    return config.get("agent_models", [])


def get_judge_models(config_path: Path = None) -> List[str]:
    """
    Get list of judge model names.
    
    Args:
        config_path: Path to config file. If None, uses evaluation/model_config.json
        
    Returns:
        List of model name strings
    """
    config = load_model_config(config_path)
    return config.get("judge_models", [])

