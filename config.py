"""Global configuration for MPCBench v2."""

from pathlib import Path

# Paths
ROOT_DIR = Path(__file__).parent
TASKS_DIR = ROOT_DIR / "tasks"
LOGS_DIR = ROOT_DIR / "logs"

# Model configuration
MODEL_CONFIG_PATH = ROOT_DIR / "model_config.json"
PROMPT_CONFIG_PATH = ROOT_DIR / "prompt_config.json"

# Ensure directories exist
TASKS_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)

