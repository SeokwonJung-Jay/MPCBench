#!/usr/bin/env python3
"""
Runner script for Level-1, Level-2, and Level-3 oracle.
"""

import os
import sys
from pathlib import Path

# Add repo root to path
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root))

from oracle.level1_oracle import run_level1_oracle
from oracle.level2_oracle import run_level2_oracle
from oracle.level3_oracle import run_level3_oracle


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Run Level-1, Level-2, or Level-3 oracle")
    parser.add_argument("--level", type=int, choices=[1, 2, 3], default=1, help="Difficulty level (1, 2, or 3)")
    parser.add_argument("--debug", action="store_true", help="Print debug summaries")
    args = parser.parse_args()
    
    # Get paths relative to repo root
    repo_root = Path(__file__).parent.parent
    
    if args.level == 1:
        world_path = repo_root / "generate" / "output" / "world_level1_test.json"
        instances_path = repo_root / "generate" / "output" / "instances_level1_test.jsonl"
        output_path = repo_root / "generate" / "output" / "oracle_level1_test.jsonl"
        
        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Run Level-1 oracle
        run_level1_oracle(str(world_path), str(instances_path), str(output_path), debug=args.debug)
    
    elif args.level == 2:
        world_path = repo_root / "generate" / "output" / "world_level2_test.json"
        instances_path = repo_root / "generate" / "output" / "instances_level2_test.jsonl"
        output_path = repo_root / "generate" / "output" / "oracle_level2_test.jsonl"
        
        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Run Level-2 oracle
        run_level2_oracle(str(world_path), str(instances_path), str(output_path), debug=args.debug)
    
    elif args.level == 3:
        world_path = repo_root / "generate" / "output" / "world_level3_test.json"
        instances_path = repo_root / "generate" / "output" / "instances_level3_test.jsonl"
        output_path = repo_root / "generate" / "output" / "oracle_level3_test.jsonl"
        
        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Run Level-3 oracle
        run_level3_oracle(str(world_path), str(instances_path), str(output_path), debug=args.debug)


if __name__ == "__main__":
    main()
