#!/usr/bin/env python3
"""
Run WebArena experiments with PolySkill

This script runs evaluations on the WebArena benchmark with polymorphic skill induction.
WebArena includes realistic websites across multiple categories:
- Shopping (OneStopShop)
- Admin (CMS)
- Reddit (Forum)
- GitLab (Development)
- Map (OpenStreetMap)
- Cross-website tasks
"""

import sys
import os
import argparse

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from experiments.run_eval_with_skill_induction import SkillInductionEvaluator


def main():
    parser = argparse.ArgumentParser(description="Run WebArena experiments with PolySkill")
    parser.add_argument(
        "--config",
        type=str,
        required=True,
        help="Path to YAML config file"
    )
    parser.add_argument(
        "--category",
        type=str,
        choices=["shopping", "admin", "reddit", "gitlab", "map", "cross", "all"],
        default="all",
        help="WebArena category to evaluate"
    )
    parser.add_argument(
        "--model",
        type=str,
        default="deepseek-chat",
        help="Model to use (gpt-4, claude-3.7-sonnet, qwen3-coder, glm-4.5)"
    )

    args = parser.parse_args()

    print(f"""
╔════════════════════════════════════════════════════════════╗
║           PolySkill WebArena Evaluation                    ║
╠════════════════════════════════════════════════════════════╣
║ Category: {args.category:<47} ║
║ Model:    {args.model:<47} ║
║ Config:   {args.config:<47} ║
╚════════════════════════════════════════════════════════════╝
    """)

    # Run evaluation
    evaluator = SkillInductionEvaluator(args.config)
    evaluator.run_evaluation()

    # Print skills summary
    evaluator.print_skills_summary()


if __name__ == "__main__":
    main()
