#!/usr/bin/env python3
"""
Test script to verify the LLM as Judge integration works correctly.
"""

import asyncio
import os
import tempfile
from typing import Dict, Any

from judge_old.trajectory_judge import TrajectoryJudge
from judge_old.utils import load_trajectory_data, extract_screenshots_from_trajectory


async def test_judge_integration():
    """Test the judge integration with mock data."""
    print("Testing LLM as Judge integration...")
    
    # Configure model (using a lightweight model for testing)
    model_config = {
        "provider": "openai",
        "name": "gpt-4o-mini",  # Smaller model for testing
        "temperature": 0.0,
        "max_tokens": 1024
    }
    
    # Initialize judge
    try:
        judge = TrajectoryJudge(model_config)
        print("✓ Judge initialized successfully")
    except Exception as e:
        print(f"✗ Failed to initialize judge: {e}")
        return False
    
    # Test key point identification
    try:
        test_task = "Find the cheapest flight from New York to Los Angeles on December 15th and book it."
        key_points = await judge.identify_key_points(test_task)
        print("✓ Key point identification works")
        print(f"  Key points: {key_points[:100]}...")
    except Exception as e:
        print(f"✗ Key point identification failed: {e}")
        return False
    
    print("\n✓ All basic tests passed!")
    print("\nTo test with actual trajectory data:")
    print("1. Run an evaluation to generate trajectory.pb.xz files")
    print("2. Use judge/evaluate_trajectory.py to test with real data")
    print("\nExample commands:")
    print("  # Single trajectory evaluation")
    print("  python judge/evaluate_trajectory.py --trajectory_path path/to/trajectory.pb.xz --method webjudge_general")
    print("\n  # Batch evaluation")
    print("  python judge/batch_evaluate.py --trajectory_dir path/to/results --method webvoyager --output_dir judge_results")
    
    return True


def test_utils():
    """Test utility functions."""
    print("Testing utility functions...")
    
    try:
        from judge_old.utils import encode_image
        from PIL import Image
        import io
        
        # Create a test image
        test_image = Image.new('RGB', (100, 100), color='red')
        encoded = encode_image(test_image)
        print("✓ Image encoding works")
        
    except Exception as e:
        print(f"✗ Utility functions failed: {e}")
        return False
    
    return True


def show_usage_examples():
    """Show usage examples."""
    print("\n" + "="*80)
    print("USAGE EXAMPLES")
    print("="*80)
    
    print("\n1. Evaluate a single trajectory:")
    print("   python judge/evaluate_trajectory.py \\")
    print("     --trajectory_path /path/to/trajectory.pb.xz \\")
    print("     --method webjudge_general \\")
    print("     --model_name gpt-4o \\")
    print("     --output_path results.json")
    
    print("\n2. Batch evaluate all trajectories in a directory:")
    print("   python judge/batch_evaluate.py \\")
    print("     --trajectory_dir /path/to/evaluation/results \\")
    print("     --method webvoyager \\")
    print("     --output_dir judge_results \\")
    print("     --max_concurrent 3")
    
    print("\n3. WebJudge with input images:")
    print("   python judge/evaluate_trajectory.py \\")
    print("     --trajectory_path /path/to/trajectory.pb.xz \\")
    print("     --method webjudge_general \\")
    print("     --input_images image1.png image2.png")
    
    print("\n4. WebVoyager with final screenshots only:")
    print("   python judge/evaluate_trajectory.py \\")
    print("     --trajectory_path /path/to/trajectory.pb.xz \\")
    print("     --method webvoyager \\")
    print("     --k_screenshots 5")


async def main():
    """Main test function."""
    print("LLM as Judge Integration Test")
    print("="*50)
    
    # Test utilities
    if not test_utils():
        print("✗ Utility tests failed")
        return
    
    # Test judge integration
    if not await test_judge_integration():
        print("✗ Judge integration tests failed")
        return
    
    # Show usage examples
    show_usage_examples()


if __name__ == "__main__":
    asyncio.run(main())