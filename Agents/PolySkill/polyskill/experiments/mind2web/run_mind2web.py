#!/usr/bin/env python3
"""
Run Mind2Web experiments with PolySkill

This script runs evaluations on the Mind2Web benchmark with polymorphic skill induction.
Supports three evaluation settings:
- Cross-task: Generalization to new tasks on seen websites
- Cross-website: Generalization to new websites in seen domains
- Cross-domain: Generalization to entirely new domains
"""

import sys
import os
import argparse

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from experiments.run_eval_with_skill_induction import SkillInductionEvaluator


def main():
    parser = argparse.ArgumentParser(description="Run Mind2Web experiments with PolySkill")
    parser.add_argument(
        "--config",
        type=str,
        required=True,
        help="Path to YAML config file"
    )
    parser.add_argument(
        "--setting",
        type=str,
        choices=["cross-task", "cross-website", "cross-domain"],
        default="cross-task",
        help="Evaluation setting"
    )
    parser.add_argument(
        "--model",
        type=str,
        default="gpt-4",
        help="Model to use (gpt-4, claude-3.7-sonnet, qwen3-coder, glm-4.5)"
    )

    args = parser.parse_args()

    print(f"""
╔════════════════════════════════════════════════════════════╗
║           PolySkill Mind2Web Evaluation                    ║
╠════════════════════════════════════════════════════════════╣
║ Setting: {args.setting:<48} ║
║ Model:   {args.model:<48} ║
║ Config:  {args.config:<48} ║
╚════════════════════════════════════════════════════════════╝
    """)

    # Run evaluation
    evaluator = SkillInductionEvaluator(args.config)
    evaluator.run_evaluation()

    # Print skills summary
    evaluator.print_skills_summary()


if __name__ == "__main__":
    main()
