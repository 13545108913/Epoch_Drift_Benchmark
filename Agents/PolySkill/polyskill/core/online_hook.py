#!/usr/bin/env python3
"""
Online Skill Induction Hook

This module provides the hook that gets called after each task completes
to perform immediate skill induction based on LLM judge evaluation.
"""

import asyncio
import logging
import os
from typing import Any, Dict, Optional

from .simple_inducer import SimpleSkillInducer
from .judge.trajectory_judge import TrajectoryJudge
from .judge.utils import load_trajectory_data

logger = logging.getLogger(__name__)

# Global instances to avoid recreating components
_skill_inducer_instance = None
_judge_instance = None


def get_skill_inducer(storage_path: str = "./learned_skills/", **kwargs) -> SimpleSkillInducer:
    """Get or create skill inducer instance."""
    global _skill_inducer_instance
    
    if _skill_inducer_instance is None:
        _skill_inducer_instance = SimpleSkillInducer(
            storage_path=storage_path,
            min_actions=kwargs.get("min_actions", 2),
            max_actions=kwargs.get("max_actions", 8)
        )
        logger.info(f"Initialized skill inducer with storage: {storage_path}")
    
    return _skill_inducer_instance


def get_judge_instance(judge_config: Dict[str, Any]) -> TrajectoryJudge:
    """Get or create judge instance."""
    global _judge_instance
    
    if _judge_instance is None:
        _judge_instance = TrajectoryJudge(judge_config)
        logger.info(f"Initialized LLM judge: {judge_config.get('provider')}/{judge_config.get('name')}")
    
    return _judge_instance


async def judge_trajectory_success(trajectory_path: str, judge_config: Dict[str, Any], 
                                 judge_method: str = "webjudge_general",
                                 score_threshold: int = 3) -> bool:
    """Use LLM judge to determine if trajectory was successful."""
    try:
        judge = get_judge_instance(judge_config)
        
        print(f"judge_path: {trajectory_path}")
        if judge_method == "webjudge_online_mind2web":
            # Use WebJudge Online Mind2Web method with score threshold
            result = await judge.judge_trajectory_webjudge_online_mind2web(
                trajectory_path=trajectory_path,
                score_threshold=score_threshold
            )
            success = result.get("trajectory_success", False)
            
        elif judge_method == "webjudge_general":
            # Use webjudge_general method with score threshold
            result = await judge.judge_trajectory_webjudge_general(
                trajectory_path=trajectory_path,
                score_threshold=score_threshold
            )
            success = result.get("trajectory_success", False)
        
        elif judge_method == "webvoyager":
            # Use WebVoyager method
            result = await judge.judge_trajectory_webvoyager(trajectory_path)
            success = result.get("trajectory_success", False)
        
        else:
            logger.error(f"Unknown judge method: {judge_method}")
            success = False
            result = {"error": f"Unknown judge method: {judge_method}"}
        
        # Simple logging to trajectory folder
        _save_judge_result(trajectory_path, result, success)
        return success
    
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        logger.error(f"LLM judge failed for {trajectory_path} with method {judge_method}:")
        logger.error(f"Error: {str(e)}")
        logger.error(f"Full traceback:\n{error_details}")
        return False


def _save_judge_result(trajectory_path: str, result: dict, success: bool):
    """Save judge result to trajectory folder."""
    try:
        import json
        from pathlib import Path
        from datetime import datetime
        
        trajectory_dir = Path(trajectory_path).parent
        judge_file = trajectory_dir / "judge_result.json"
        
        # Extract key information for storage
        judge_data = {
            "timestamp": datetime.now().isoformat(),
            "success": success,
            "task": result.get("task", ""),
            "key_points": result.get("key_points", ""),
            "num_screenshots": result.get("num_screenshots", 0),
            "num_high_score": result.get("num_high_score", 0),
            "final_evaluation": result.get("final_evaluation", result.get("evaluation", "")),
            "method_used": "webjudge" if "screenshot_judgments" in result else "webvoyager"
        }
        
        with open(judge_file, 'w') as f:
            json.dump(judge_data, f, indent=2)
            
    except Exception as e:
        logger.error(f"Failed to save judge result: {e}")


async def process_task_for_skills(
    trajectory_path: str,
    task: str,
    reward: float,
    agent_config: Any = None,
    skill_config: Optional[Dict[str, Any]] = None
) -> Optional[Any]:
    """
    Process a completed task for skill induction.
    
    Args:
        trajectory_path: Path to the trajectory file
        task: Task description/goal
        reward: Task reward (may be ignored based on config)
        agent_config: Agent configuration
        skill_config: Skill induction configuration
        
    Returns:
        Induced skill or None
    """
    if not skill_config or not skill_config.get("enabled", True):
        return None
    
    # Check if trajectory file exists
    if not os.path.exists(trajectory_path):
        logger.warning(f"Trajectory file not found: {trajectory_path}")
        return None
    
    logger.info(f"Processing task for skills: {task}")
    
    try:
        # Optional reward pre-filtering (default: False - always judge)
        use_reward_signal = skill_config.get("use_reward_signal", False)
        if use_reward_signal and reward <= 0:
            logger.info(f"  Skipping (reward={reward}, use_reward_signal=True)")
            return None
        
        # Always use LLM Judge for final decision
        judge_config = skill_config.get("judge_model", {
            "provider": "openai",
            "name": "gpt-4o",
            "temperature": 0.0
        })
        
        # Get judge method and parameters
        judge_method = skill_config.get("judge_method", "webjudge_general")
        score_threshold = skill_config.get("score_threshold", 3)
        
        llm_success = await judge_trajectory_success(
            trajectory_path, 
            judge_config, 
            judge_method=judge_method,
            score_threshold=score_threshold
        )
        
        print(f"Golden reward: {reward}, LLM Judge: {llm_success}. Match: {(reward > 0) == llm_success}")
        if not llm_success:
            logger.info(f"  LLM judge: FAILED - no skill induction")
            return None
        
        logger.info(f"  LLM judge: SUCCESS - inducing skills...")
        
        # Initialize skill inducer
        storage_path = skill_config.get("storage_path", "./learned_skills/")
        skill_inducer = get_skill_inducer(
            storage_path=storage_path,
            min_actions=skill_config.get("min_actions", 2),
            max_actions=skill_config.get("max_actions", 8)
        )
        
        # Load trajectory and induce skill
        trajectory_data = load_trajectory_data(trajectory_path)
        skill = skill_inducer.induce_skill(trajectory_data, task)
        
        if skill:
            logger.info(f"  ✓ Induced skill: {skill.name} (success_count: {skill.success_count})")
            return skill
        else:
            logger.info(f"  - No skill induced from trajectory")
            return None
    
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        logger.error(f"Skill induction failed for task '{task}':")
        logger.error(f"Error: {str(e)}")
        logger.error(f"Full traceback:\n{error_details}")
        return None


def process_task_for_skills_sync(
    trajectory_path: str,
    task: str,
    reward: float,
    agent_config: Any = None,
    skill_config: Optional[Dict[str, Any]] = None
) -> Optional[Any]:
    """Synchronous wrapper for skill processing."""
    try:
        return asyncio.run(process_task_for_skills(
            trajectory_path=trajectory_path,
            task=task,
            reward=reward,
            agent_config=agent_config,
            skill_config=skill_config
        ))
    except RuntimeError as e:
        if "cannot be called from a running event loop" in str(e):
            # Handle nested event loop by running in thread
            import concurrent.futures
            
            def run_in_thread():
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                try:
                    return new_loop.run_until_complete(process_task_for_skills(
                        trajectory_path=trajectory_path,
                        task=task,
                        reward=reward,
                        agent_config=agent_config,
                        skill_config=skill_config
                    ))
                finally:
                    new_loop.close()
            
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(run_in_thread)
                return future.result()
        else:
            raise


def get_current_skills(storage_path: str = "./learned_skills/") -> list:
    """Get current skills for an agent to use."""
    try:
        skill_inducer = get_skill_inducer(storage_path=storage_path)
        skills = skill_inducer.get_skills()
        logger.info(f"Loaded {len(skills)} skills for agent")
        return skills
    except Exception as e:
        logger.error(f"Failed to load skills: {e}")
        return []


def get_skills_summary(storage_path: str = "./learned_skills/") -> str:
    """Get a summary of current skills."""
    try:
        skill_inducer = get_skill_inducer(storage_path=storage_path)
        return skill_inducer.export_skills_summary()
    except Exception as e:
        logger.error(f"Failed to get skills summary: {e}")
        return "No skills available"