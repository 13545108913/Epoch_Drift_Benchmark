#!/usr/bin/env python3
"""
Main script for evaluating digital agent trajectories with LLM as Judge.

Usage:
    python judge/evaluate_trajectory.py --trajectory_path <path> --method <method> [options]
"""

import argparse
import asyncio
import json
import os
import tempfile
from typing import Dict, Any

from .trajectory_judge import TrajectoryJudge


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Evaluate digital agent trajectories with LLM as Judge")
    
    parser.add_argument(
        "--trajectory_path",
        type=str,
        required=True,
        help="Path to trajectory.pb.xz file"
    )
    
    parser.add_argument(
        "--method",
        type=str,
        choices=["webjudge_general", "webjudge_online_mind2web", "webvoyager"],
        default="webjudge_online_mind2web",
        help="Evaluation method to use"
    )
    
    parser.add_argument(
        "--model_provider",
        type=str,
        default="openai",
        help="Model provider (openai, anthropic, etc.)"
    )
    
    parser.add_argument(
        "--model_name",
        type=str,
        default="gpt-4o",
        help="Model name"
    )
    
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.0,
        help="Model temperature"
    )
    
    parser.add_argument(
        "--input_images",
        type=str,
        nargs="*",
        help="Paths to input images for context (for webjudge_general)"
    )
    
    parser.add_argument(
        "--k_screenshots",
        type=int,
        default=0,
        help="Number of final screenshots to use for webvoyager (0 = all)"
    )
    
    parser.add_argument(
        "--output_path",
        type=str,
        help="Path to save evaluation results (JSON)"
    )
    
    parser.add_argument(
        "--temp_dir",
        type=str,
        help="Temporary directory for screenshots"
    )
    
    return parser.parse_args()


async def main():
    """Main evaluation function."""
    args = parse_args()
    
    # Validate trajectory file exists
    if not os.path.exists(args.trajectory_path):
        raise FileNotFoundError(f"Trajectory file not found: {args.trajectory_path}")
    
    # Configure model
    model_config = {
        "provider": args.model_provider,
        "name": args.model_name,
        "temperature": args.temperature,
        "max_tokens": 2048
    }
    
    # Initialize judge
    judge = TrajectoryJudge(model_config)
    
    # Create temp directory if not provided
    temp_dir = args.temp_dir
    if temp_dir is None:
        temp_dir = tempfile.mkdtemp(prefix="trajectory_judge_")
        print(f"Using temporary directory: {temp_dir}")
    else:
        os.makedirs(temp_dir, exist_ok=True)
    
    print(f"Evaluating trajectory: {args.trajectory_path}")
    print(f"Method: {args.method}")
    print(f"Model: {args.model_provider}/{args.model_name}")
    
    # Run evaluation based on method
    if args.method == "webjudge_general":
        results = await judge.judge_trajectory_webjudge_general(
            trajectory_path=args.trajectory_path,
            input_image_paths=args.input_images,
            temp_dir=temp_dir
        )
    elif args.method == "webjudge_online_mind2web":
        results = await judge.judge_trajectory_webjudge_online_mind2web(
            trajectory_path=args.trajectory_path,
            temp_dir=temp_dir
        )
    elif args.method == "webvoyager":
        results = await judge.judge_trajectory_webvoyager(
            trajectory_path=args.trajectory_path,
            k=args.k_screenshots,
            temp_dir=temp_dir
        )
    else:
        raise ValueError(f"Unknown method: {args.method}")
    
    # Add metadata
    results["metadata"] = {
        "trajectory_path": args.trajectory_path,
        "method": args.method,
        "model_config": model_config,
        "temp_dir": temp_dir
    }
    
    # Save results
    if args.output_path:
        with open(args.output_path, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"Results saved to: {args.output_path}")
    else:
        print("\n" + "="*80)
        print("EVALUATION RESULTS")
        print("="*80)
        print(json.dumps(results, indent=2))
    
    print(f"\nEvaluation completed!")
    if args.temp_dir is None:
        print(f"Temporary files saved in: {temp_dir}")


if __name__ == "__main__":
    asyncio.run(main())