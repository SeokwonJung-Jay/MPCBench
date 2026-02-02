"""
MPCBench Agent Package.

Provides agent implementations for solving scheduling tasks.

Usage:
    from evaluation.agents.base import BaseAgent
    from evaluation.agents.openai_agent import OpenAIAgent  # requires: openai, python-dotenv
"""

from evaluation.agents.base import BaseAgent

__all__ = [
    'BaseAgent',
]


def get_openai_agent():
    """
    Lazy import for OpenAIAgent to avoid dependency errors.
    
    Returns:
        OpenAIAgent class.
        
    Raises:
        ImportError: If openai or python-dotenv is not installed.
    """
    from evaluation.agents.openai_agent import OpenAIAgent
    return OpenAIAgent
