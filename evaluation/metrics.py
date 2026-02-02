"""
Metrics module for MPCBench evaluation.

Calculates Set-based F1 Score between ground truth and predictions.
"""

from typing import Any, Dict, List, Tuple, Union


# Type aliases for clarity
CandidateL1L2 = Tuple[str, str]  # (start_dt, end_dt)
CandidateL3 = Tuple[str, str, str]  # (start_dt, end_dt, room_id)
Candidate = Union[CandidateL1L2, CandidateL3]


def calculate_f1(
    gold_list: List[Candidate],
    pred_list: List[Candidate]
) -> Dict[str, Any]:
    """
    Calculate Set-based F1 Score between ground truth and predictions.
    
    Args:
        gold_list: List of ground truth candidates.
            - L1/L2: List of tuples (start_dt, end_dt)
            - L3: List of tuples (start_dt, end_dt, room_id)
        pred_list: List of predicted candidates (same format as gold_list).
        
    Returns:
        Dict containing:
            - f1: F1 score (float, 0.0 to 1.0)
            - precision: Precision (float, 0.0 to 1.0)
            - recall: Recall (float, 0.0 to 1.0)
            - exact_match: Whether gold and pred sets are identical (bool)
    """
    # Convert to sets for order-independent comparison
    gold_set = set(gold_list)
    pred_set = set(pred_list)
    
    if len(gold_set) == 0 and len(pred_set) == 0:
        return {
            'f1': 1.0, 
            'precision': 1.0, 
            'recall': 1.0, 
            'exact_match': True
        }

    # Calculate intersection (true positives)
    true_positives = len(gold_set & pred_set)
    
    # Calculate precision: TP / |pred|
    if len(pred_set) == 0:
        precision = 0.0
    else:
        precision = true_positives / len(pred_set)
    
    # Calculate recall: TP / |gold|
    if len(gold_set) == 0:
        recall = 0.0
    else:
        recall = true_positives / len(gold_set)
    
    # Calculate F1: 2 * (precision * recall) / (precision + recall)
    if precision + recall == 0:
        f1 = 0.0
    else:
        f1 = 2 * (precision * recall) / (precision + recall)
    
    # Check exact match
    exact_match = gold_set == pred_set
    
    return {
        'f1': f1,
        'precision': precision,
        'recall': recall,
        'exact_match': exact_match
    }


def candidates_from_oracle_output(
    feasible_candidates: List[Dict[str, str]],
    level: int
) -> List[Candidate]:
    """
    Convert oracle output format to tuple format for F1 calculation.
    
    Args:
        feasible_candidates: List of candidate dicts from oracle output.
            - L1/L2: [{"start": ..., "end": ...}, ...]
            - L3: [{"start": ..., "end": ..., "room_id": ...}, ...]
        level: Task level (1, 2, or 3).
        
    Returns:
        List of tuples suitable for calculate_f1().
    """
    result = []
    for candidate in feasible_candidates:
        if level in (1, 2):
            result.append((candidate['start'], candidate['end']))
        elif level == 3:
            result.append((candidate['start'], candidate['end'], candidate['room_id']))
        else:
            raise ValueError(f"Invalid level: {level}")
    return result


def evaluate_instance(
    gold_candidates: List[Dict[str, str]],
    pred_candidates: List[Dict[str, str]],
    level: int
) -> Dict[str, Any]:
    """
    Evaluate a single instance by comparing gold and predicted candidates.
    
    Args:
        gold_candidates: Ground truth candidates from oracle output.
        pred_candidates: Predicted candidates from agent output.
        level: Task level (1, 2, or 3).
        
    Returns:
        Dict containing f1, precision, recall, exact_match.
    """
    gold_tuples = candidates_from_oracle_output(gold_candidates, level)
    pred_tuples = candidates_from_oracle_output(pred_candidates, level)
    return calculate_f1(gold_tuples, pred_tuples)
