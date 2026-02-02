"""
MPCBench Evaluation Package.

Provides utilities for:
- sanitizer: Remove oracle-only _tags fields from agent inputs
- metrics: Calculate Set-based F1 Score for evaluation
- tools: Simulated API for agent tool calls
"""

from evaluation.sanitizer import sanitize, sanitize_world, sanitize_instance
from evaluation.metrics import calculate_f1, candidates_from_oracle_output, evaluate_instance
from evaluation.tools import SimulatedAPI

__all__ = [
    'sanitize',
    'sanitize_world',
    'sanitize_instance',
    'calculate_f1',
    'candidates_from_oracle_output',
    'evaluate_instance',
    'SimulatedAPI',
]
