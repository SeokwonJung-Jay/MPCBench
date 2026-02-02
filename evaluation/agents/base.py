"""
Base agent abstract class for MPCBench evaluation.
"""

from abc import ABC, abstractmethod
from typing import List, Tuple, Union


# Type aliases for candidate tuples
CandidateL1L2 = Tuple[str, str]  # (start_dt, end_dt)
CandidateL3 = Tuple[str, str, str]  # (start_dt, end_dt, room_id)
Candidate = Union[CandidateL1L2, CandidateL3]


class BaseAgent(ABC):
    """
    Abstract base class for scheduling agents.
    
    All agent implementations must inherit from this class and implement
    the solve() method.
    """
    
    @abstractmethod
    def solve(self, task_text: str, context_data: dict) -> List[Candidate]:
        """
        Solve a scheduling task given the task description and context data.
        
        Args:
            task_text: The task description text (from instance.task_text).
            context_data: Sanitized context data containing world sources
                and any relevant instance data (without oracle-only tags).
                
        Returns:
            List of candidate tuples:
                - L1/L2: [(start_dt, end_dt), ...]
                - L3: [(start_dt, end_dt, room_id), ...]
            
            Returns empty list [] if solving fails or no candidates found.
            
        Note:
            - All datetime strings should be in ISO 8601 format with timezone.
            - The order of candidates matters for ranking-based evaluation.
        """
        pass
