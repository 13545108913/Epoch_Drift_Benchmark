"""
Enhanced HSM V3 ASI Agent with Skill Induction

This agent extends the existing HSM V3 ASI agent to include skill induction capabilities,
allowing it to learn and improve from successful task completions.
"""

import logging
import os
from typing import Type, Optional, Dict, Any, List, Tuple
from copy import deepcopy
from datetime import datetime

from polyskill.agent.hsm_v3_agent_asi import HsmV3ASIAgent, _ExecutorAgent
from polyskill.model import FoundationModel
from polyskill.agent.asi_utils.utils import parse_model_configs, ASIAgentMixin
from polyskill.skill_induction import SimpleSkillInducer

logger = logging.getLogger(__name__)


class SkillInducingExecutorAgent(_ExecutorAgent):
    """
    Executor agent that can use induced skills and record their usage.
    """
    
    def __init__(self, *args, skill_inducer: Optional[SimpleSkillInducer] = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.skill_inducer = skill_inducer
        self.used_skills = []  # Track which skills were used
    
    def act(self, **kwargs):
        """
        Enhanced act method that records skill usage.
        """
        action, action_description = super().act(**kwargs)
        
        # Track if any induced skills were used
        if self.skill_inducer and action:
            self._track_skill_usage(action, success=True)  # Assume success for now
        
        return action, action_description
    
    def _track_skill_usage(self, action: str, success: bool):
        """Track usage of induced skills."""
        if not self.skill_inducer:
            return
        
        # Check if action contains any known skill names
        tested_skills = self.skill_inducer.knowledge_base.get_tested_skills()
        
        for skill in tested_skills:
            if skill.name in action:
                self.skill_inducer.record_skill_usage(skill.name, success)
                self.used_skills.append({
                    'skill_name': skill.name,
                    'success': success,
                    'action': action
                })
                logger.info(f"Recorded {'successful' if success else 'failed'} usage of skill: {skill.name}")


class HsmV3ASIAgentWithInduction(HsmV3ASIAgent):
    """
    Enhanced HSM V3 ASI Agent with integrated skill induction capabilities.
    
    This agent can:
    1. Use existing induced skills during task execution
    2. Learn new skills from successful task completions
    3. Export learned skills for future use
    4. Manage a persistent skill knowledge base
    """
    
    def __init__(
        self,
        model_configs: dict,
        actions: str = "custom",
        limit_to_ctx: bool = True,
        max_call_depth: int = 3,
        executor_cls: Type = SkillInducingExecutorAgent,
        action_file_path: str = None,
        # Skill induction parameters
        enable_skill_induction: bool = True,
        skill_storage_path: str = "agent_skills",
        auto_export_skills: bool = True,
        skill_export_path: str = None,
        min_skill_complexity: int = 2,
        max_skill_complexity: int = 8,
    ):
        """
        Initialize the agent with skill induction capabilities.
        
        Args:
            model_configs: Model configuration dictionary
            actions: Action configuration
            limit_to_ctx: Whether to limit actions to context
            max_call_depth: Maximum recursive call depth
            executor_cls: Executor agent class to use
            action_file_path: Path to custom actions file
            enable_skill_induction: Whether to enable skill learning
            skill_storage_path: Path for storing learned skills
            auto_export_skills: Whether to automatically export skills as actions
            skill_export_path: Path for exporting skills (if None, uses action_file_path)
            min_skill_complexity: Minimum actions per skill
            max_skill_complexity: Maximum actions per skill
        """
        
        # Initialize the base agent
        super().__init__(
            model_configs=model_configs,
            actions=actions,
            limit_to_ctx=limit_to_ctx,
            max_call_depth=max_call_depth,
            executor_cls=executor_cls,
            action_file_path=action_file_path
        )
        
        # Skill induction setup
        self.enable_skill_induction = enable_skill_induction
        self.skill_storage_path = skill_storage_path
        self.auto_export_skills = auto_export_skills
        self.skill_export_path = skill_export_path or action_file_path
        
        # Initialize skill inducer if enabled
        self.skill_inducer = None
        if enable_skill_induction:
            try:
                self.skill_inducer = SimpleSkillInducer(
                    storage_path=skill_storage_path
                )
                
                # Load previous state if available
                self.skill_inducer.load_state()
                
                # Update executor with skill inducer reference
                if hasattr(self.executor, 'skill_inducer'):
                    self.executor.skill_inducer = self.skill_inducer
                
                logger.info(f"Skill induction enabled with storage at: {skill_storage_path}")
                
                # Load existing skills if they exist
                self._load_existing_skills()
                
            except Exception as e:
                logger.error(f"Failed to initialize skill induction: {e}")
                self.enable_skill_induction = False
        
        # Track task completion for skill induction
        self.current_task_id = None
        self.current_goal = None
        self.task_completed_successfully = False
    
    def reset(self, goal, html, screenshot, goal_image_urls=[], task_id: Optional[str] = None):
        """
        Reset the agent for a new task.
        
        Args:
            goal: Task goal description
            html: Initial HTML content
            screenshot: Initial screenshot
            goal_image_urls: Goal image URLs
            task_id: Optional task identifier for skill induction
        """
        super().reset(goal, html, screenshot, goal_image_urls)
        
        # Setup for skill induction
        self.current_task_id = task_id or f"task_{len(self.skill_inducer.induction_history) if self.skill_inducer else 0}"
        self.current_goal = goal
        self.task_completed_successfully = False
        
        # Reset skill usage tracking
        if hasattr(self.executor, 'used_skills'):
            self.executor.used_skills = []
    
    def complete_task(self, success: bool = True, screenshot_paths: Optional[List[str]] = None) -> Optional[Dict[str, Any]]:
        """
        Mark the current task as completed and potentially learn skills.
        
        Args:
            success: Whether the task was completed successfully
            screenshot_paths: Optional list of screenshot paths for enhanced validation
            
        Returns:
            Skill induction results if performed, None otherwise
        """
        self.task_completed_successfully = success
        
        if not self.enable_skill_induction or not success or not self.skill_inducer:
            return None
        
        logger.info(f"Task {self.current_task_id} completed successfully, attempting skill induction...")
        
        try:
            # Perform skill induction from current agent state
            induction_result = self.skill_inducer.induce_skills_from_agent_state(
                agent_state_dict=self.get_state_dict(),
                task_id=self.current_task_id,
                goal=self.current_goal,
                screenshot_paths=screenshot_paths
            )
            
            # Auto-export skills if enabled and new skills were learned
            if (self.auto_export_skills and 
                self.skill_export_path and 
                induction_result.get('skills_added_to_kb', 0) > 0):
                
                self._export_skills_to_action_file()
            
            # Save inducer state
            self.skill_inducer.save_state()
            
            logger.info(f"Skill induction completed: {induction_result}")
            return induction_result
            
        except Exception as e:
            logger.error(f"Skill induction failed: {e}")
            return {'error': str(e)}
    
    def get_relevant_skills(self, task_description: str, max_skills: int = 5) -> list:
        """
        Get skills relevant to a task description.
        
        Args:
            task_description: Description of the task
            max_skills: Maximum number of skills to return
            
        Returns:
            List of relevant skills
        """
        if not self.skill_inducer:
            return []
        
        return self.skill_inducer.get_skills_for_task(task_description, max_skills)
    
    def _load_existing_skills(self):
        """Load existing skills and update action set if needed."""
        if not self.skill_inducer:
            return
        
        tested_skills = self.skill_inducer.knowledge_base.get_tested_skills()
        
        if tested_skills and self.auto_export_skills and self.skill_export_path:
            logger.info(f"Found {len(tested_skills)} existing skills, updating action set...")
            self._export_skills_to_action_file()
    
    def _export_skills_to_action_file(self):
        """Export learned skills to the action file."""
        if not self.skill_inducer or not self.skill_export_path:
            return
        
        try:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(self.skill_export_path), exist_ok=True)
            
            # Export skills
            self.skill_inducer.export_skills_as_actions(self.skill_export_path)
            
            # Reload the action set to include new skills
            if hasattr(self, 'action_set'):
                from polyskill.agent.asi_utils.utils import initialize_custom_action_set
                self.action_set = initialize_custom_action_set(self.skill_export_path)
                
                # Update executor's action set too
                if hasattr(self.executor, 'action_set'):
                    self.executor.action_set = self.action_set
            
            logger.info(f"Skills exported to {self.skill_export_path} and action set updated")
            
        except Exception as e:
            logger.error(f"Failed to export skills: {e}")
    
    def get_skill_statistics(self) -> Dict[str, Any]:
        """Get comprehensive statistics about learned skills."""
        if not self.skill_inducer:
            return {'error': 'Skill induction not enabled'}
        
        return self.skill_inducer.get_comprehensive_stats()
    
    def get_state_dict(self) -> dict:
        """Enhanced state dict that includes skill induction data."""
        state_dict = super().get_state_dict()
        
        # Add skill induction specific state
        state_dict.update({
            'skill_induction_enabled': self.enable_skill_induction,
            'current_task_id': self.current_task_id,
            'current_goal': self.current_goal,
            'task_completed_successfully': self.task_completed_successfully,
        })
        
        # Add skill usage information if available
        if hasattr(self.executor, 'used_skills'):
            state_dict['used_skills'] = self.executor.used_skills
        
        return state_dict
    
    def load_state_dict(self, state_dict: dict) -> None:
        """Enhanced state loading that includes skill induction data."""
        super().load_state_dict(state_dict)
        
        # Restore skill induction state
        self.current_task_id = state_dict.get('current_task_id')
        self.current_goal = state_dict.get('current_goal')
        self.task_completed_successfully = state_dict.get('task_completed_successfully', False)
        
        # Restore skill usage tracking
        if hasattr(self.executor, 'used_skills') and 'used_skills' in state_dict:
            self.executor.used_skills = state_dict['used_skills']


# Convenience function for creating the enhanced agent
def create_skill_inducing_hsm_agent(
    model_configs: dict,
    enable_skill_induction: bool = True,
    skill_storage_path: str = "agent_skills",
    action_file_path: str = None,
    **kwargs
) -> HsmV3ASIAgentWithInduction:
    """
    Convenience function to create an HSM agent with skill induction.
    
    Args:
        model_configs: Model configuration dictionary
        enable_skill_induction: Whether to enable skill learning
        skill_storage_path: Path for storing learned skills
        action_file_path: Path to custom actions file
        **kwargs: Additional arguments for the agent
        
    Returns:
        Configured HSM agent with skill induction
    """
    
    # Set default action file path if skill induction is enabled
    if enable_skill_induction and not action_file_path:
        action_file_path = os.path.join(skill_storage_path, "induced_skills.py")
    
    agent = HsmV3ASIAgentWithInduction(
        model_configs=model_configs,
        enable_skill_induction=enable_skill_induction,
        skill_storage_path=skill_storage_path,
        action_file_path=action_file_path,
        **kwargs
    )
    
    return agent 