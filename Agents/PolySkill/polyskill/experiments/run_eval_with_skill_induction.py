#!/usr/bin/env python3
"""
Run Evaluation with Online Skill Induction

This script runs evaluations in single-threaded mode where each task can benefit
from skills learned from previous successful tasks.

Flow:
1. Run task n
2. Judge if successful using webjudge_general
3. If successful, induce skills
4. Skills are available for task n+1

Key: threads=1 to ensure sequential execution.
"""

import yaml
import fire
import logging

from polyskill.utils import file_utils
from polyskill.evaluation.eval_config import EvalConfig
from polyskill.skill_induction.judge.utils import load_trajectory_data, extract_task_from_trajectory

logger = logging.getLogger(__name__)


class SkillInductionEvaluator:
    """
    Handles evaluation with online skill induction.
    """
    
    def __init__(self, config_path: str):
        # Load config
        with file_utils.open(config_path, "r") as f:
            config_dict = yaml.safe_load(f.read())
        
        # Extract skill induction config
        self.skill_config = config_dict.pop("skill_induction", {})
        
        # Create eval config
        self.eval_config = EvalConfig(**config_dict)
        
        # Force single-threaded execution
        if self.eval_config.runner.threads != 1:
            print(f"WARNING: Forcing threads=1 for skill induction (was {self.eval_config.runner.threads})")
            self.eval_config.runner.threads = 1
        
        # Inject skill config into all agents (so eval_loop.py hook can access it)
        if self.skill_config.get("enabled", True):
            for agent_name, agent_config in self.eval_config.agents.items():
                agent_config.skill_induction_config = self.skill_config
                print(f"Injected skill induction config into agent: {agent_name}")
        
        # Track evaluation state for summary
        self.task_count = 0
        self.successful_tasks = 0
        self.induced_skills = 0
        
    def print_skills_summary(self):
        """Print summary of learned skills."""
        try:
            from polyskill.skill_induction.online_hook import get_skills_summary
            storage_path = self.skill_config.get("storage_path", "./learned_skills/")
            summary = get_skills_summary(storage_path)
            
            print(f"\n{'='*60}")
            print("LEARNED SKILLS SUMMARY")
            print(f"{'='*60}")
            print(summary)
        except Exception as e:
            logger.warning(f"Failed to get skills summary: {e}")
    
    def run_evaluation(self):
        """Run evaluation with true online skill induction."""
        print("="*60)
        print("RUNNING EVALUATION WITH ONLINE SKILL INDUCTION")
        print("="*60)
        print(f"Single-threaded execution: {self.eval_config.runner.threads == 1}")
        print(f"Skill induction enabled: {self.skill_config.get('enabled', True)}")
        judge_method = self.skill_config.get('judge_method', 'webjudge_general')
        print(f"Judge method: {judge_method}")
        print(f"Use reward signal: {self.skill_config.get('use_reward_signal', False)}")
        
        # Special handling for Mind2Web configuration
        if judge_method == 'webjudge_online_mind2web':
            score_threshold = self.skill_config.get('score_threshold', 3)
            print(f"✓ Using WebJudge Online Mind2Web evaluation")
            print(f"✓ Screenshot score threshold: {score_threshold} (1-5 scale)")
            print(f"✓ Mind2Web-specific criteria: filters, sorting, range requirements")
            if self.eval_config.runner.threads != 1:
                print("⚠  WARNING: Mind2Web skill induction requires threads=1 for sequential learning")
        
        if self.skill_config.get("enabled", True):
            print("✓ Skills will be induced after each successful task")
            print("✓ Each task can benefit from previously learned skills")
        
        # Import required functions for task-by-task execution
        import subprocess
        from tqdm import tqdm
        from polyskill.evaluation.eval_loop import run_example
        from polyskill.evaluation.eval_runner import get_env_ids_and_task_kwargs, wait_for_models, _get_output_dirs_for_run
        from polyskill.skill_induction.online_hook import process_task_for_skills_sync
        
        # Run each benchmark-agent combination
        all_results = []
        for benchmark_name, benchmark_config in self.eval_config.benchmarks.items():
            for agent_name, agent_config in self.eval_config.agents.items():
                print(f"\n{'='*40}")
                print(f"RUNNING: {benchmark_name} with {agent_name}")
                print(f"{'='*40}")
                
                # Resolve model config like the regular evaluation system
                if not agent_config.model_config_name:
                    raise ValueError(f"No model_config_name in agent {agent_name}. There should be exactly one model_config_name in agent.")
                if agent_config.model_config_name not in self.eval_config.model_configs:
                    raise ValueError(f"Model config {agent_config.model_config_name} not found in model_configs.")
                
                # Set the resolved model config
                agent_config.model = self.eval_config.model_configs[agent_config.model_config_name]
                
                # Get environment IDs and task kwargs for this benchmark
                env_ids, task_kwargs = get_env_ids_and_task_kwargs(
                    benchmark_config, shuffle_seed=self.eval_config.runner.seed
                )
                if task_kwargs:
                    assert len(env_ids) == len(task_kwargs), f"Expect arguments for every environment ID, found {len(env_ids)} envs and {len(task_kwargs)} args."
                
                # Wait for models to be ready
                wait_for_models(agent_config.model)
                
                # Create output directories following run_single_benchmark pattern
                output_dirs = _get_output_dirs_for_run(
                    self.eval_config,
                    benchmark_name=benchmark_name,
                    agent_name=agent_name
                )

                # Print output directory information
                if output_dirs:
                    print(f"Results will be saved to: {output_dirs[0]}")
                
                # Reset WebArena environment if needed
                if benchmark_config.reset_env and "webarena" in benchmark_config.dataset:
                    print("Resetting WebArena environment...")
                    try:
                        subprocess.run(["bash", "scripts/reset_remote_wa_vwa.sh"], check=False)
                    except Exception as e:
                        print(f"Warning: Failed to reset WebArena environment: {e}")
                
                print(f"Found {len(env_ids)} tasks to run sequentially")
                if self.skill_config.get("enabled", True):
                    storage_path = self.skill_config.get("storage_path", "./learned_skills/")
                    print(f"Skills will be stored at: {storage_path}")
                
                # Run tasks one by one with immediate skill induction
                task_rewards = []
                skills_learned = 0
                
                # Use progress bar like run_single_benchmark
                with tqdm(total=len(env_ids), desc=f"{benchmark_name}+{agent_name}") as pbar:
                    for i, env_id in enumerate(env_ids):
                        print(f"\n[Task {i+1}/{len(env_ids)}] {env_id}")
                        
                        # Inject current skills into agent config before task
                        if self.skill_config.get("enabled", True):
                            try:
                                from polyskill.skill_induction.online_hook import get_current_skills, get_skills_summary
                                
                                # Get current skills and inject them into agent config
                                current_skills = get_current_skills(storage_path)
                                skill_count = len(current_skills)
                                
                                # Update agent config with current skills for this task
                                agent_config.skill_induction_config = self.skill_config.copy()
                                agent_config.skill_induction_config['current_skills'] = current_skills
                                agent_config.skill_induction_config['storage_path'] = storage_path
                                
                                print(f"  Available skills injected into agent: {skill_count}")
                                if skill_count > 0:
                                    summary = get_skills_summary(storage_path)
                                    # Show first few lines of skills for context
                                    summary_lines = summary.split('\n')[:3]  
                                    print(f"  Recent skills: {' | '.join(line.strip() for line in summary_lines if line.strip())}")
                            except Exception as e:
                                print(f"  Available skills: 0 (error: {e})")
                        
                        # Run single task
                        reward = run_example(
                            env_id,
                            None if not task_kwargs else task_kwargs[i],
                            agent_config,
                            benchmark_config,
                            debug_dirs=output_dirs,
                            timeout=self.eval_config.runner.timeout_secs,
                        )
                        
                        task_rewards.append(reward)
                        golden_reward_success = reward > 0
                        print(f"  Golden reward: {'SUCCESS' if golden_reward_success else 'FAILED'} (reward: {reward})")
                        
                        # Immediate skill induction using LLM Judge (NOT golden reward)
                        if self.skill_config.get("enabled", True) and output_dirs:
                            import os
                            trajectory_path = os.path.join(output_dirs[0], env_id, "trajectory.pb.xz")
                            
                            if os.path.exists(trajectory_path):
                                try:
                                    # Extract task goal from trajectory or use env_id as fallback
                                    task_goal = env_id
                                    
                                    # For Mind2Web tasks, try to extract the actual goal from trajectory
                                    print(f"  Judging with LLM (method: {judge_method}, score_threshold: {score_threshold})...")
                                    
                                    # Use synchronous skill induction (handles asyncio internally)
                                    skill = process_task_for_skills_sync(
                                        trajectory_path=trajectory_path,
                                        task=task_goal,
                                        reward=reward,
                                        agent_config=agent_config,
                                        skill_config=self.skill_config
                                    )
                                    
                                    if skill:
                                        skills_learned += 1
                                        print(f"  ✓ LLM Judge: SUCCESS - Learned skill: {skill.name}")
                                        if judge_method == 'webjudge_online_mind2web':
                                            print(f"    Mind2Web evaluation passed with score threshold {score_threshold}")
                                        
                                        # Update agent with new skills immediately
                                        try:
                                            from polyskill.skill_induction.online_hook import get_current_skills
                                            updated_skills = get_current_skills(storage_path)
                                            print(f"  ✓ Skills now available for next task: {len(updated_skills)}")
                                        except Exception as e:
                                            print(f"  - Warning: Could not update skills for agent: {e}")
                                    else:
                                        if judge_method == 'webjudge_online_mind2web':
                                            print(f"  - LLM Judge: FAILED - Task did not meet Mind2Web evaluation criteria")
                                        else:
                                            print(f"  - LLM Judge: FAILED or no skill pattern found")
                                        
                                except Exception as e:
                                    print(f"  ✗ Skill induction failed: {e}")
                            else:
                                print(f"  - No trajectory file found for LLM judging")
                        
                        # Update progress bar
                        pbar.update(1)
                
                # Calculate results following run_single_benchmark format
                num_success = sum(task_rewards)
                num_total = len(task_rewards)
                success_rate = num_success / num_total if num_total > 0 else 0
                
                # Print results like run_single_benchmark
                print(f"\nSuccess rate: {success_rate:.1%} ({num_success}/{num_total})")
                print(f"Skills learned: {skills_learned}")
                if output_dirs:
                    print(f"Results saved to: {output_dirs[0]}")

                result = {
                    "benchmark": benchmark_name,
                    "agent": agent_name,
                    "num_success": num_success,
                    "num_total": num_total,
                    "success_rate": success_rate,
                    "skills_learned": skills_learned,
                    "output_dir": output_dirs[0] if output_dirs else None,
                    "rewards": task_rewards
                }
                all_results.append(result)
        
        # Print final skills summary
        if self.skill_config.get("enabled", True):
            self.print_skills_summary()
        
        return all_results


def main(config_path: str):
    """
    Run evaluation with online skill induction.
    
    Args:
        config_path: Path to YAML config file
        **kwargs: Additional arguments passed to evaluation
    """
    
    # Setup logging
    logging.basicConfig(level=logging.INFO)
    
    # Create evaluator
    evaluator = SkillInductionEvaluator(config_path)
    
    # Run evaluation with online skill induction
    results = evaluator.run_evaluation()
    
    print("\n" + "="*60)
    print("ONLINE SKILL INDUCTION COMPLETE")
    print("="*60)
    print("Skills were learned and applied during evaluation!")
    
    return results


if __name__ == "__main__":
    fire.Fire(main)