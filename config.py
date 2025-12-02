"""Global configuration for MPCBench v2."""

from pathlib import Path
import os

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # dotenv not installed, manually load .env file
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    if key and value:
                        os.environ.setdefault(key, value)

# Paths
ROOT_DIR = Path(__file__).parent
TASKS_DIR = ROOT_DIR / "tasks"
LOGS_DIR = ROOT_DIR / "logs"

# Model configuration
MODEL_CONFIG_PATH = ROOT_DIR / "model_config.json"
PROMPT_CONFIG_PATH = ROOT_DIR / "prompt_config.json"
# GENERATOR_CONFIG_PATH is deprecated - generator config is now in prompt_config.json under "generator" key
GENERATOR_CONFIG_PATH = ROOT_DIR / "generator_config.json"

# Ensure directories exist
TASKS_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)

# Cache for configs
_generator_config_cache = None


def get_generator_config() -> dict:
    """Load and cache generator config from prompt_config.json."""
    global _generator_config_cache
    if _generator_config_cache is None:
        import json
        with open(PROMPT_CONFIG_PATH, 'r', encoding='utf-8') as f:
            prompt_config = json.load(f)
            _generator_config_cache = prompt_config.get("generator", {})
            if not _generator_config_cache:
                # Fallback to old generator_config.json for backward compatibility
                if GENERATOR_CONFIG_PATH.exists():
                    with open(GENERATOR_CONFIG_PATH, 'r', encoding='utf-8') as f:
                        _generator_config_cache = json.load(f)
    return _generator_config_cache

