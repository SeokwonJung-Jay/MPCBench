"""Helper module to load model configuration for data generation."""

import json
from pathlib import Path


def load_world_state_model() -> str:
    """
    Load world_state_model from evaluation/model_config.json.
    
    Returns:
        Model name string (e.g., "gpt-4o-mini")
        
    Raises:
        FileNotFoundError: If model_config.json doesn't exist
        ValueError: If world_state_model field is missing
    """
    config_path = Path("evaluation/model_config.json")
    
    if not config_path.exists():
        raise FileNotFoundError(f"Model config file not found: {config_path}")
    
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    world_state_model = config.get("world_state_model")
    
    if not world_state_model:
        raise ValueError("world_state_model not specified in evaluation/model_config.json")
    
    return world_state_model

