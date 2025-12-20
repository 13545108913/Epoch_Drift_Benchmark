#!/usr/bin/env python3
"""
Batch evaluation script for multiple digital agent trajectories.

Usage:
    python judge/batch_evaluate.py --trajectory_dir <dir> --method <method> [options]
"""

import argparse
import asyncio
import json
import os
import tempfile
import traceback
from typing import List, Dict, Any
from tqdm.asyncio import tqdm

from .trajectory_judge import TrajectoryJudge


def find_trajectory_files(directory: str) -> List[str]:
    """Find all trajectory.pb.xz files in directory and subdirectories."""
    trajectory_files = []
    for root, _, files in os.walk(directory):
        for file in files:
            if file == "trajectory.pb.xz":
                trajectory_files.append(os.path.join(root, file))
    return sorted(trajectory_files)


async def evaluate_single_trajectory(judge: TrajectoryJudge,
                                   trajectory_path: str,
                                   method: str,
                                   temp_dir: str,
                                   **kwargs) -> Dict[str, Any]:
    """Evaluate a single trajectory file."""
    trajectory_name = os.path.basename(os.path.dirname(trajectory_path))
    try:
        print(f"Evaluating {trajectory_name}...")
        
        # Create subdirectory for this trajectory
        trajectory_temp_dir = os.path.join(temp_dir, trajectory_name)
        os.makedirs(trajectory_temp_dir, exist_ok=True)
        
        # Run evaluation based on method
        if method == "webjudge_general":
            results = await judge.judge_trajectory_webjudge_general(
                trajectory_path=trajectory_path,
                input_image_paths=kwargs.get('input_images'),
                temp_dir=trajectory_temp_dir
            )
        elif method == "webjudge_online_mind2web":
            results = await judge.judge_trajectory_webjudge_online_mind2web(
                trajectory_path=trajectory_path,
                temp_dir=trajectory_temp_dir
            )
        elif method == "webvoyager":
            results = await judge.judge_trajectory_webvoyager(
                trajectory_path=trajectory_path,
                k=kwargs.get('k_screenshots', 0),
                temp_dir=trajectory_temp_dir
            )
        else:
            raise ValueError(f"Unknown method: {method}")
        
        # Add trajectory metadata
        results["trajectory_file"] = trajectory_path
        results["trajectory_name"] = trajectory_name
        results["success"] = True
        
        print(f"Successfully evaluated {trajectory_name}")
        return results
        
    except Exception as e:
        error_msg = str(e)
        print(f"ERROR evaluating {trajectory_name}: {error_msg}")
        print(f"Full traceback for {trajectory_name}:")
        traceback.print_exc()
        
        return {
            "trajectory_file": trajectory_path,
            "trajectory_name": trajectory_name,
            "success": False,
            "error": error_msg,
            "full_traceback": traceback.format_exc()
        }


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Batch evaluate digital agent trajectories")
    
    parser.add_argument(
        "--trajectory_dir",
        type=str,
        required=True,
        help="Directory containing trajectory files"
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
        "--k_screenshots",
        type=int,
        default=0,
        help="Number of final screenshots to use for webvoyager (0 = all)"
    )
    
    parser.add_argument(
        "--output_dir",
        type=str,
        required=True,
        help="Directory to save evaluation results"
    )
    
    parser.add_argument(
        "--temp_dir",
        type=str,
        help="Temporary directory for screenshots"
    )
    
    parser.add_argument(
        "--max_concurrent",
        type=int,
        default=5,
        help="Maximum number of concurrent evaluations"
    )
    
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit number of trajectories to evaluate (for testing)"
    )
    
    return parser.parse_args()


async def main():
    """Main batch evaluation function."""
    args = parse_args()
    
    # Find trajectory files
    trajectory_files = find_trajectory_files(args.trajectory_dir)
    
    if not trajectory_files:
        print(f"No trajectory files found in {args.trajectory_dir}")
        return
    
    # Apply limit if specified
    if args.limit:
        trajectory_files = trajectory_files[:args.limit]
    
    print(f"Found {len(trajectory_files)} trajectory files")
    
    # Create output directory
    os.makedirs(args.output_dir, exist_ok=True)
    
    # Create temp directory if not provided
    temp_dir = args.temp_dir
    if temp_dir is None:
        temp_dir = tempfile.mkdtemp(prefix="batch_trajectory_judge_")
        print(f"Using temporary directory: {temp_dir}")
    else:
        os.makedirs(temp_dir, exist_ok=True)
    
    # Configure model
    model_config = {
        "provider": args.model_provider,
        "name": args.model_name,
        "temperature": args.temperature,
        "max_tokens": 2048,
        "use_cache": "none"
    }
    
    # Initialize judge
    judge = TrajectoryJudge(model_config)
    
    print(f"Method: {args.method}")
    print(f"Model: {args.model_provider}/{args.model_name}")
    print(f"Max concurrent: {args.max_concurrent}")
    
    # Create semaphore to limit concurrent evaluations
    semaphore = asyncio.Semaphore(args.max_concurrent)
    
    async def evaluate_with_semaphore(trajectory_path: str) -> Dict[str, Any]:
        async with semaphore:
            return await evaluate_single_trajectory(
                judge=judge,
                trajectory_path=trajectory_path,
                method=args.method,
                temp_dir=temp_dir,
                k_screenshots=args.k_screenshots
            )
    
    # Run evaluations with progress bar
    print("\\nStarting batch evaluation...")
    tasks = [evaluate_with_semaphore(path) for path in trajectory_files]
    results = await tqdm.gather(*tasks, desc="Evaluating trajectories")
    
    # Save individual results
    successful_results = []
    failed_results = []
    
    for result in results:
        trajectory_name = result.get("trajectory_name", "unknown")
        
        if result.get("success", False):
            # Save individual result
            result_file = os.path.join(args.output_dir, f"{trajectory_name}_evaluation.json")
            with open(result_file, 'w') as f:
                json.dump(result, f, indent=2)
            successful_results.append(result)
        else:
            failed_results.append(result)
    
    # Create summary
    summary = {
        "metadata": {
            "trajectory_dir": args.trajectory_dir,
            "method": args.method,
            "model_config": model_config,
            "total_trajectories": len(trajectory_files),
            "successful_evaluations": len(successful_results),
            "failed_evaluations": len(failed_results),
            "temp_dir": temp_dir
        },
        "successful_trajectories": [r["trajectory_name"] for r in successful_results],
        "failed_trajectories": [
            {"name": r["trajectory_name"], "error": r.get("error", "Unknown error")}
            for r in failed_results
        ]
    }
    
    # Save summary
    summary_file = os.path.join(args.output_dir, "evaluation_summary.json")
    with open(summary_file, 'w') as f:
        json.dump(summary, f, indent=2)
    
    print(f"\\nBatch evaluation completed!")
    print(f"Successful: {len(successful_results)}")
    print(f"Failed: {len(failed_results)}")
    print(f"Results saved in: {args.output_dir}")
    print(f"Summary saved to: {summary_file}")
    
    if failed_results:
        print("\\nFailed trajectories:")
        for result in failed_results:
            print(f"  - {result['trajectory_name']}: {result.get('error', 'Unknown error')}")


if __name__ == "__main__":
    asyncio.run(main())