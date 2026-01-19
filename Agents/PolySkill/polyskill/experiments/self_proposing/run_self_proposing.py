#!/usr/bin/env python3
"""
Run Self-Proposing Exploration with PolySkill

This script enables agents to:
1. Autonomously explore websites
2. Propose their own goals/tasks
3. Learn polymorphic skills from successful attempts
4. Build a library of transferable skills without predefined tasks

This represents the "task-free" continual learning setting from the paper.
"""

import sys
import os
import argparse

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from experiments.run_eval_with_skill_induction import SkillInductionEvaluator


def main():
    parser = argparse.ArgumentParser(
        description="Run self-proposing exploration with PolySkill"
    )
    parser.add_argument(
        "--config",
        type=str,
        required=True,
        help="Path to YAML config file"
    )
    parser.add_argument(
        "--domain",
        type=str,
        choices=["shopping", "dev_tools", "mixed"],
        default="mixed",
        help="Domain(s) for exploration"
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=150,
        help="Number of exploration iterations"
    )
    parser.add_argument(
        "--model",
        type=str,
        default="gpt-4",
        help="Model to use (gpt-4, claude-3.7-sonnet)"
    )

    args = parser.parse_args()

    print(f"""
╔════════════════════════════════════════════════════════════╗
║         PolySkill Self-Proposing Exploration               ║
╠════════════════════════════════════════════════════════════╣
║ Domain:      {args.domain:<45} ║
║ Iterations:  {args.iterations:<45} ║
║ Model:       {args.model:<45} ║
║ Config:      {args.config:<45} ║
╠════════════════════════════════════════════════════════════╣
║ Mode: Autonomous task proposal and skill learning          ║
║ The agent will:                                             ║
║   • Explore websites independently                          ║
║   • Propose its own goals                                   ║
║   • Learn transferable polymorphic skills                   ║
╚════════════════════════════════════════════════════════════╝
    """)

    # Run evaluation
    evaluator = SkillInductionEvaluator(args.config)
    evaluator.run_evaluation()

    # Print detailed skills summary
    evaluator.print_skills_summary()

    print(f"""
╔════════════════════════════════════════════════════════════╗
║                  Exploration Complete                       ║
╠════════════════════════════════════════════════════════════╣
║ Check the learned skills above to see what the agent       ║
║ discovered during autonomous exploration!                   ║
╚════════════════════════════════════════════════════════════╝
    """)


if __name__ == "__main__":
    main()
