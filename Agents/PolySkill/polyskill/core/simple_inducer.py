#!/usr/bin/env python3
"""
Simple Skill Inducer for Online Learning

A minimal, hackable implementation that extracts reusable patterns from successful trajectories.
Focus: Simplicity over optimization.
"""

import json
import os
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class Skill:
    """Simple skill representation."""
    id: str
    name: str
    pattern: List[Dict[str, Any]]  # List of actions
    task_examples: List[str]  # Tasks where this skill was used
    success_count: int = 1
    created_at: str = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'name': self.name,
            'pattern': self.pattern,
            'task_examples': self.task_examples,
            'success_count': self.success_count,
            'created_at': self.created_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Skill':
        return cls(**data)


class SimpleSkillInducer:
    """
    Simple skill inducer that extracts action patterns from trajectories.
    
    Key principles:
    - Simple pattern matching
    - No complex ML - just basic heuristics
    - Fast and hackable
    - JSON-based storage
    """
    
    def __init__(
        self,
        storage_path: str = "./learned_skills/",
        min_actions: int = 2,
        max_actions: int = 8
    ):
        self.storage_path = Path(storage_path)
        self.min_actions = min_actions
        self.max_actions = max_actions
        self.skills_file = self.storage_path / "skills.json"
        
        # Ensure storage directory exists
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        # Load existing skills
        self.skills = self._load_skills()
        
    def _load_skills(self) -> List[Skill]:
        """Load existing skills from storage."""
        if not self.skills_file.exists():
            return []
        
        try:
            with open(self.skills_file, 'r') as f:
                data = json.load(f)
            
            return [Skill.from_dict(skill_data) for skill_data in data.get('skills', [])]
        except Exception as e:
            logger.warning(f"Failed to load skills: {e}")
            return []
    
    def _save_skills(self) -> None:
        """Save skills to storage."""
        data = {
            'skills': [skill.to_dict() for skill in self.skills],
            'metadata': {
                'last_updated': datetime.now().isoformat(),
                'total_skills': len(self.skills),
                'total_tasks_processed': sum(skill.success_count for skill in self.skills)
            }
        }
        
        with open(self.skills_file, 'w') as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"Saved {len(self.skills)} skills to {self.skills_file}")
    
    def extract_actions_from_trajectory(self, trajectory_data: Any) -> List[Dict[str, Any]]:
        """Extract action sequence from trajectory data."""
        actions = []
        
        if hasattr(trajectory_data, 'actions'):
            # Protobuf trajectory
            for action_data in trajectory_data.actions:
                if hasattr(action_data, 'action') and action_data.action:
                    action_dict = {
                        'type': 'action',
                        'action': action_data.action,
                        'timestamp': getattr(action_data, 'timestamp', 0)
                    }
                    actions.append(action_dict)
        elif isinstance(trajectory_data, dict) and 'actions' in trajectory_data:
            # Dict-based trajectory
            actions = trajectory_data.get('actions', [])
        
        return actions
    
    def extract_skill_from_actions(
        self,
        actions: List[Dict[str, Any]],
        task: str
    ) -> Optional[Skill]:
        """Extract a skill from action sequence."""
        if len(actions) < self.min_actions or len(actions) > self.max_actions:
            return None
        
        # Simple pattern: take the first few meaningful actions
        meaningful_actions = []
        
        for action in actions[:self.max_actions]:
            if isinstance(action, dict):
                # Extract essential parts of the action
                action_type = action.get('type', 'unknown')
                action_content = action.get('action', '')
                
                # Skip empty or trivial actions
                if not action_content:
                    continue
                
                # Create a simplified pattern
                pattern_action = {
                    'type': action_type,
                    'action': action_content[:200]  # Limit length
                }
                meaningful_actions.append(pattern_action)
        
        if len(meaningful_actions) < self.min_actions:
            return None
        
        # Generate skill name based on actions and task
        skill_name = self._generate_skill_name(meaningful_actions, task)
        skill_id = f"skill_{len(self.skills) + 1:03d}"
        
        return Skill(
            id=skill_id,
            name=skill_name,
            pattern=meaningful_actions,
            task_examples=[task]
        )
    
    def _generate_skill_name(
        self,
        actions: List[Dict[str, Any]],
        task: str
    ) -> str:
        """Generate a descriptive name for the skill."""
        # Extract key words from actions
        action_types = []
        action_keywords = []
        
        for action in actions:
            action_str = str(action.get('action', '')).lower()
            
            # Common action patterns
            if 'click' in action_str:
                action_types.append('click')
            elif 'fill' in action_str or 'type' in action_str:
                action_types.append('fill')
            elif 'select' in action_str:
                action_types.append('select')
            elif 'navigate' in action_str or 'go' in action_str:
                action_types.append('navigate')
            
            # Extract potential element names
            if 'button' in action_str:
                action_keywords.append('button')
            elif 'form' in action_str or 'input' in action_str:
                action_keywords.append('form')
            elif 'menu' in action_str:
                action_keywords.append('menu')
        
        # Extract key words from task
        task_words = []
        task_lower = task.lower()
        if 'login' in task_lower:
            task_words.append('login')
        elif 'search' in task_lower:
            task_words.append('search')
        elif 'add' in task_lower or 'create' in task_lower:
            task_words.append('create')
        elif 'delete' in task_lower or 'remove' in task_lower:
            task_words.append('delete')
        
        # Combine to form skill name
        name_parts = []
        if action_types:
            name_parts.extend(action_types[:2])  # Max 2 action types
        if task_words:
            name_parts.extend(task_words[:1])   # Max 1 task word
        if action_keywords:
            name_parts.extend(action_keywords[:1])  # Max 1 keyword
        
        if name_parts:
            return '_'.join(name_parts)
        else:
            return f'pattern_{len(self.skills) + 1}'
    
    def induce_skill(
        self,
        trajectory_data: Any,
        task: str
    ) -> Optional[Skill]:
        """
        Main skill induction method.
        
        Args:
            trajectory_data: Trajectory data (protobuf or dict)
            task: Task description
            
        Returns:
            Induced skill or None
        """
        logger.info(f"Inducing skill from task: {task}")
        
        # Extract actions
        actions = self.extract_actions_from_trajectory(trajectory_data)
        if not actions:
            logger.warning("No actions found in trajectory")
            return None
        
        # Extract skill
        skill = self.extract_skill_from_actions(actions, task)
        if not skill:
            logger.info(f"No skill extracted (actions: {len(actions)})")
            return None
        
        # Check if similar skill already exists
        existing_skill = self._find_similar_skill(skill)
        if existing_skill:
            # Update existing skill
            existing_skill.success_count += 1
            if task not in existing_skill.task_examples:
                existing_skill.task_examples.append(task)
            logger.info(f"Updated existing skill: {existing_skill.name} (count: {existing_skill.success_count})")
            skill = existing_skill
        else:
            # Add new skill
            self.skills.append(skill)
            logger.info(f"Created new skill: {skill.name}")
        
        # Save skills
        self._save_skills()
        
        return skill
    
    def _find_similar_skill(self, new_skill: Skill) -> Optional[Skill]:
        """Find existing skill similar to the new one."""
        for existing_skill in self.skills:
            # Simple similarity: same number of actions and similar name
            if (len(existing_skill.pattern) == len(new_skill.pattern) and
                existing_skill.name == new_skill.name):
                return existing_skill
        return None
    
    def get_skills(self) -> List[Skill]:
        """Get all current skills."""
        return self.skills.copy()
    
    def get_skills_for_task(self, task: str) -> List[Skill]:
        """Get skills that might be relevant for a task."""
        # Simple relevance: check if any task example contains similar words
        relevant_skills = []
        task_lower = task.lower()
        
        for skill in self.skills:
            # Check task examples
            for example in skill.task_examples:
                example_lower = example.lower()
                # Simple word overlap
                task_words = set(task_lower.split())
                example_words = set(example_lower.split())
                overlap = task_words.intersection(example_words)
                
                if len(overlap) >= 2:  # At least 2 words in common
                    relevant_skills.append(skill)
                    break
        
        # Sort by success count (most successful first)
        relevant_skills.sort(key=lambda s: s.success_count, reverse=True)
        return relevant_skills
    
    def export_skills_summary(self) -> str:
        """Export a summary of learned skills."""
        if not self.skills:
            return "No skills learned yet."
        
        summary = f"Learned Skills Summary ({len(self.skills)} skills):\n\n"
        
        for i, skill in enumerate(self.skills, 1):
            summary += f"{i}. {skill.name} (ID: {skill.id})\n"
            summary += f"   - Success count: {skill.success_count}\n"
            summary += f"   - Actions: {len(skill.pattern)}\n"
            summary += f"   - Task examples: {', '.join(skill.task_examples[:3])}\n"
            if len(skill.task_examples) > 3:
                summary += f"     ... and {len(skill.task_examples) - 3} more\n"
            summary += "\n"
        
        return summary