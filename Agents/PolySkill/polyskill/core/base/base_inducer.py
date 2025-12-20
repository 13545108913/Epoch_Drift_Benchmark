"""
Base Skill Inducer

Abstract base class for all skill inducers with common functionality.
"""

import json
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass

from .skill_types import (
    Skill, SkillType, SkillFormat, SkillInductionResult, 
    TrajectoryExample, SkillMetadata
)

logger = logging.getLogger(__name__)


@dataclass
class InducerConfig:
    """Base configuration for skill inducers."""
    storage_path: str = "./learned_skills/"
    min_actions: int = 2
    max_actions: int = 20
    min_trajectories: int = 1
    similarity_threshold: float = 0.8
    enabled: bool = True
    
    # Trajectory processing settings
    remove_errors: bool = True
    remove_redundant: bool = True
    require_success: bool = True


class BaseSkillInducer(ABC):
    """
    Abstract base class for skill inducers.
    
    Provides common functionality:
    - Trajectory processing utilities
    - Storage interface
    - Skill validation
    - Configuration management
    """
    
    def __init__(self, config: InducerConfig):
        """Initialize the base inducer."""
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Initialize storage path
        self.storage_path = Path(config.storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        # Statistics
        self.stats = {
            'trajectories_processed': 0,
            'skills_induced': 0,
            'skills_validated': 0,
            'validation_failures': 0
        }
    
    @abstractmethod
    def extract_skills(
        self,
        trajectories: List[Union[Dict[str, Any], TrajectoryExample]],
        task_context: Optional[str] = None
    ) -> SkillInductionResult:
        """
        Extract skills from trajectories.
        
        Args:
            trajectories: List of trajectory data
            task_context: Optional context about the task
            
        Returns:
            SkillInductionResult with induced skills
        """
        pass
    
    @abstractmethod
    def validate_skill(self, skill: Skill) -> bool:
        """
        Validate that a skill is well-formed and usable.
        
        Args:
            skill: Skill to validate
            
        Returns:
            True if skill is valid
        """
        pass
    
    def process_trajectory(
        self,
        trajectory: Union[Dict[str, Any], TrajectoryExample],
        task: str = ""
    ) -> Optional[SkillInductionResult]:
        """
        Process a single trajectory and potentially induce skills.
        
        Args:
            trajectory: Trajectory data
            task: Task description
            
        Returns:
            SkillInductionResult if skills were induced, None otherwise
        """
        self.stats['trajectories_processed'] += 1
        
        # Clean and validate trajectory
        cleaned_traj = self.clean_trajectory(trajectory)
        if not cleaned_traj:
            self.logger.debug("Trajectory failed cleaning")
            return None
        
        # Check if trajectory meets minimum requirements
        if not self._meets_requirements(cleaned_traj):
            self.logger.debug("Trajectory doesn't meet requirements")
            return None
        
        # Extract skills
        result = self.extract_skills([cleaned_traj], task_context=task)
        
        if result.success and result.skills:
            self.stats['skills_induced'] += len(result.skills)
        
        return result
    
    def clean_trajectory(
        self,
        trajectory: Union[Dict[str, Any], TrajectoryExample]
    ) -> Optional[TrajectoryExample]:
        """
        Clean and normalize a trajectory.
        
        Args:
            trajectory: Raw trajectory data
            
        Returns:
            Cleaned TrajectoryExample or None if invalid
        """
        # Convert to TrajectoryExample if needed
        if isinstance(trajectory, dict):
            traj_example = self._dict_to_trajectory_example(trajectory)
        else:
            traj_example = trajectory
        
        if not traj_example:
            return None
        
        # Filter actions
        filtered_actions = []
        for action in traj_example.actions:
            if self._is_valid_action(action):
                cleaned_action = self._clean_action(action)
                if cleaned_action:
                    filtered_actions.append(cleaned_action)
        
        # Check if enough valid actions remain
        if len(filtered_actions) < self.config.min_actions:
            return None
        
        if len(filtered_actions) > self.config.max_actions:
            filtered_actions = filtered_actions[:self.config.max_actions]
        
        # Create cleaned trajectory
        return TrajectoryExample(
            task_id=traj_example.task_id,
            goal=traj_example.goal,
            actions=filtered_actions,
            success=traj_example.success,
            metadata=traj_example.metadata
        )
    
    def _dict_to_trajectory_example(self, traj_dict: Dict[str, Any]) -> Optional[TrajectoryExample]:
        """Convert dictionary trajectory to TrajectoryExample."""
        try:
            # Handle different trajectory formats
            if "steps" in traj_dict:
                actions = []
                for step in traj_dict["steps"]:
                    if isinstance(step, dict) and "action" in step:
                        actions.append({
                            "action": step["action"],
                            "thought": step.get("thought", ""),
                            "step_number": step.get("step_number", len(actions))
                        })
                    elif isinstance(step, str):
                        actions.append({"action": step, "step_number": len(actions)})
            
            elif "actions" in traj_dict:
                actions = traj_dict["actions"]
                if not isinstance(actions, list):
                    return None
            else:
                self.logger.warning("Unknown trajectory format")
                return None
            
            return TrajectoryExample(
                task_id=traj_dict.get("task_id", f"unknown_{len(actions)}"),
                goal=traj_dict.get("goal", traj_dict.get("intent", "")),
                actions=actions,
                success=traj_dict.get("success", True),
                metadata=traj_dict.get("metadata", {})
            )
        
        except Exception as e:
            self.logger.error(f"Error converting trajectory: {e}")
            return None
    
    def _is_valid_action(self, action: Dict[str, Any]) -> bool:
        """Check if an action is valid."""
        if not isinstance(action, dict):
            return False
        
        # Check for error indicators
        if self.config.remove_errors:
            error = action.get("error", action.get("last_action_error", ""))
            if error and not error.startswith("TimeoutError"):
                return False
        
        # Check for empty action
        action_content = action.get("action", action.get("last_action", ""))
        if not action_content or str(action_content).strip() == "":
            return False
        
        return True
    
    def _clean_action(self, action: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Clean and normalize an action."""
        try:
            action_content = action.get("action", action.get("last_action", ""))
            
            # Clean action string
            if isinstance(action_content, str):
                action_content = action_content.strip()
                # Remove comments
                if "#" in action_content:
                    action_content = action_content[:action_content.index("#")].strip()
            
            return {
                "action": action_content,
                "thought": action.get("thought", ""),
                "step_number": action.get("step_number", 0),
                "timestamp": action.get("timestamp", 0)
            }
        
        except Exception as e:
            self.logger.error(f"Error cleaning action: {e}")
            return None
    
    def _meets_requirements(self, trajectory: TrajectoryExample) -> bool:
        """Check if trajectory meets inducer requirements."""
        if not trajectory.actions:
            return False
        
        if len(trajectory.actions) < self.config.min_actions:
            return False
        
        if self.config.require_success and not trajectory.success:
            return False
        
        if not trajectory.goal or trajectory.goal.strip() == "":
            return False
        
        return True
    
    def find_similar_skills(self, skill: Skill, existing_skills: List[Skill]) -> List[Skill]:
        """Find skills similar to the given skill."""
        similar = []
        for existing_skill in existing_skills:
            if skill.is_similar_to(existing_skill, self.config.similarity_threshold):
                similar.append(existing_skill)
        return similar
    
    def merge_similar_skill(self, new_skill: Skill, existing_skill: Skill) -> Skill:
        """Merge a new skill with an existing similar skill."""
        # Update task examples
        existing_skill.add_task_example(new_skill.task_examples[0] if new_skill.task_examples else "")
        
        # Update metadata
        existing_skill.record_success()
        existing_skill.metadata.version += 1
        
        self.logger.info(f"Merged skill {new_skill.name} into {existing_skill.name}")
        return existing_skill
    
    def validate_skills(self, skills: List[Skill]) -> List[Skill]:
        """Validate a list of skills and return only valid ones."""
        valid_skills = []
        for skill in skills:
            if self.validate_skill(skill):
                valid_skills.append(skill)
                self.stats['skills_validated'] += 1
            else:
                self.stats['validation_failures'] += 1
                self.logger.warning(f"Skill validation failed: {skill.name}")
        
        return valid_skills
    
    def get_stats(self) -> Dict[str, Any]:
        """Get inducer statistics."""
        return self.stats.copy()
    
    def reset_stats(self):
        """Reset statistics."""
        self.stats = {
            'trajectories_processed': 0,
            'skills_induced': 0,
            'skills_validated': 0,
            'validation_failures': 0
        }


class SkillRegistry:
    """
    Registry for managing different skill inducer types.
    """
    
    _inducers: Dict[str, type] = {}
    
    @classmethod
    def register(cls, name: str, inducer_class: type):
        """Register a skill inducer class."""
        cls._inducers[name] = inducer_class
    
    @classmethod
    def create(cls, name: str, config: InducerConfig) -> BaseSkillInducer:
        """Create an inducer instance by name."""
        if name not in cls._inducers:
            raise ValueError(f"Unknown inducer type: {name}")
        
        return cls._inducers[name](config)
    
    @classmethod
    def list_inducers(cls) -> List[str]:
        """List available inducer types."""
        return list(cls._inducers.keys())