#!/usr/bin/env python3
"""
Core Skill Induction Components - Concise and Hackable

This module provides the essential components for online skill induction:
- Judge: Evaluates trajectory success with screenshot support
- Inducer: Extracts reusable skills from trajectories
- Storage: Persists and retrieves learned skills
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum
from datetime import datetime

logger = logging.getLogger(__name__)


class JudgeMethod(Enum):
    """Available judge evaluation methods."""
    SIMPLE = "simple"  # Basic success check
    VISUAL = "visual"  # With screenshot analysis
    DETAILED = "detailed"  # Step-by-step verification


@dataclass
class SkillInductionConfig:
    """Minimal configuration for skill induction."""
    enabled: bool = True
    judge_method: str = "visual"
    use_screenshots: bool = True
    storage_path: str = "./learned_skills/"
    update_frequency: int = 3  # Induce after N successful tasks
    formats: List[str] = None
    
    def __post_init__(self):
        if self.formats is None:
            self.formats = ["code", "natural_language"]


class Judge:
    """
    Evaluates trajectory success.
    Simplified version focusing on practical evaluation.
    """
    
    def __init__(self, method: JudgeMethod = JudgeMethod.VISUAL):
        self.method = method
    
    def evaluate(
        self, 
        task: str, 
        trajectory: Dict[str, Any],
        screenshots: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Evaluate if a trajectory successfully completed the task.
        
        For now, uses simple heuristics. Replace with LLM call for production.
        """
        # Simple heuristic-based evaluation
        steps = trajectory.get("steps", [])
        
        # Check basic success indicators
        has_completion = any(
            "send_msg" in str(step) or 
            "submit" in str(step) or
            "done" in str(step)
            for step in steps
        )
        
        # Visual check if screenshots provided
        visual_confidence = 0.8 if screenshots and len(screenshots) > 0 else 0.5
        
        success = has_completion and len(steps) >= 2
        
        return {
            "success": success,
            "confidence": visual_confidence if success else 0.2,
            "method": self.method.value,
            "reasoning": f"Evaluated {len(steps)} steps with {len(screenshots or [])} screenshots"
        }


class SkillInducer:
    """
    Extracts reusable skills from successful trajectories.
    Focuses on practical pattern extraction.
    """
    
    def __init__(self):
        self.patterns = []
    
    def induce(self, trajectories: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Extract skills from trajectories.
        
        Returns both code and natural language representations.
        """
        if not trajectories:
            return []
        
        skills = []
        
        # Group similar trajectories
        grouped = self._group_by_task_type(trajectories)
        
        for task_type, group in grouped.items():
            # Extract common patterns
            pattern = self._extract_pattern(group)
            
            if pattern:
                # Generate code skill
                code_skill = self._generate_code_skill(pattern)
                skills.append(code_skill)
                
                # Generate natural language skill
                nl_skill = self._generate_nl_skill(pattern)
                skills.append(nl_skill)
        
        return skills
    
    def _group_by_task_type(self, trajectories: List[Dict[str, Any]]) -> Dict[str, List]:
        """Group trajectories by task similarity."""
        groups = {}
        
        for traj in trajectories:
            # Simple grouping by first action type
            steps = traj.get("steps", [])
            if steps:
                first_action = steps[0].get("action", {}).get("type", "unknown")
                key = first_action
            else:
                key = "unknown"
            
            if key not in groups:
                groups[key] = []
            groups[key].append(traj)
        
        return groups
    
    def _extract_pattern(self, trajectories: List[Dict[str, Any]]) -> Optional[Dict]:
        """Extract common action pattern from similar trajectories."""
        if not trajectories:
            return None
        
        # Get most common action sequence
        action_sequences = []
        for traj in trajectories:
            actions = []
            for step in traj.get("steps", []):
                action = step.get("action", {})
                actions.append({
                    "type": action.get("type", "unknown"),
                    "selector": action.get("selector", "")
                })
            action_sequences.append(actions)
        
        # Find common prefix
        if not action_sequences:
            return None
        
        common_actions = []
        min_len = min(len(seq) for seq in action_sequences)
        
        for i in range(min_len):
            actions_at_i = [seq[i] for seq in action_sequences]
            # Check if all actions at position i are similar
            if all(a["type"] == actions_at_i[0]["type"] for a in actions_at_i):
                common_actions.append(actions_at_i[0])
            else:
                break
        
        if len(common_actions) >= 2:
            return {
                "actions": common_actions,
                "task": trajectories[0].get("goal", "unknown task")
            }
        
        return None
    
    def _generate_code_skill(self, pattern: Dict) -> Dict:
        """Generate Python code representation of skill."""
        actions = pattern["actions"]
        
        # Build code string
        code_lines = ["def execute_skill(page):"]
        for action in actions:
            if action["type"] == "click":
                code_lines.append(f"    page.click('{action['selector']}')")
            elif action["type"] == "fill":
                code_lines.append(f"    page.fill('{action['selector']}', value)")
            elif action["type"] == "select":
                code_lines.append(f"    page.select('{action['selector']}', option)")
            else:
                code_lines.append(f"    # {action['type']} on {action['selector']}")
        
        code_lines.append("    return True")
        
        return {
            "name": f"skill_{len(self.patterns)}",
            "type": "code",
            "content": "\n".join(code_lines),
            "pattern": pattern,
            "created_at": datetime.now().isoformat()
        }
    
    def _generate_nl_skill(self, pattern: Dict) -> Dict:
        """Generate natural language representation of skill."""
        actions = pattern["actions"]
        
        steps = []
        for i, action in enumerate(actions, 1):
            if action["type"] == "click":
                steps.append(f"{i}. Click on {action['selector'] or 'element'}")
            elif action["type"] == "fill":
                steps.append(f"{i}. Fill in {action['selector'] or 'field'}")
            elif action["type"] == "select":
                steps.append(f"{i}. Select option in {action['selector'] or 'dropdown'}")
            else:
                steps.append(f"{i}. Perform {action['type']}")
        
        return {
            "name": f"workflow_{len(self.patterns)}",
            "type": "natural_language",
            "content": f"Task: {pattern['task']}\nSteps:\n" + "\n".join(steps),
            "pattern": pattern,
            "created_at": datetime.now().isoformat()
        }


class SkillStorage:
    """
    Simple file-based storage for learned skills.
    """
    
    def __init__(self, storage_path: str = "./learned_skills"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.skills_file = self.storage_path / "skills.json"
        self.skills = self._load_skills()
    
    def _load_skills(self) -> List[Dict]:
        """Load existing skills from storage."""
        if self.skills_file.exists():
            with open(self.skills_file, 'r') as f:
                return json.load(f)
        return []
    
    def store(self, skill: Dict) -> bool:
        """Store a new skill."""
        try:
            self.skills.append(skill)
            with open(self.skills_file, 'w') as f:
                json.dump(self.skills, f, indent=2)
            
            # Also save individual skill file
            skill_file = self.storage_path / f"{skill['name']}.json"
            with open(skill_file, 'w') as f:
                json.dump(skill, f, indent=2)
            
            logger.info(f"Stored skill: {skill['name']}")
            return True
        except Exception as e:
            logger.error(f"Failed to store skill: {e}")
            return False
    
    def retrieve(self, skill_type: Optional[str] = None) -> List[Dict]:
        """Retrieve skills, optionally filtered by type."""
        if skill_type:
            return [s for s in self.skills if s.get("type") == skill_type]
        return self.skills
    
    def clear(self):
        """Clear all stored skills."""
        self.skills = []
        if self.skills_file.exists():
            self.skills_file.unlink()
        logger.info("Cleared all skills")


class OnlineSkillInducer:
    """
    Main orchestrator for online skill induction.
    Simple, clean interface for integration with evaluation loop.
    """
    
    def __init__(self, config: SkillInductionConfig):
        self.config = config
        self.judge = Judge(JudgeMethod[config.judge_method.upper()])
        self.inducer = SkillInducer()
        self.storage = SkillStorage(config.storage_path)
        
        self.trajectory_buffer = []
        self.successful_count = 0
        
        logger.info(f"Online skill inducer initialized: {config.storage_path}")
    
    def process_trajectory(
        self,
        task: str,
        trajectory: Dict[str, Any],
        screenshots: Optional[List[str]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Process a trajectory and potentially induce skills.
        
        Returns skill induction result if skills were learned, None otherwise.
        """
        if not self.config.enabled:
            return None
        
        # Evaluate trajectory
        result = self.judge.evaluate(task, trajectory, screenshots)
        
        if not result["success"]:
            logger.debug(f"Task unsuccessful: {result['reasoning']}")
            return None
        
        # Add to buffer
        self.successful_count += 1
        self.trajectory_buffer.append({
            "goal": task,
            "steps": trajectory.get("steps", []),
            "screenshots": screenshots
        })
        
        logger.info(f"Buffered successful trajectory ({len(self.trajectory_buffer)} total)")
        
        # Check if time to induce
        if len(self.trajectory_buffer) >= self.config.update_frequency:
            return self._induce_and_store()
        
        return None
    
    def _induce_and_store(self) -> Dict[str, Any]:
        """Induce skills from buffer and store them."""
        logger.info(f"Inducing skills from {len(self.trajectory_buffer)} trajectories")
        
        # Induce skills
        skills = self.inducer.induce(self.trajectory_buffer)
        
        # Store skills
        stored_count = 0
        for skill in skills:
            if self.storage.store(skill):
                stored_count += 1
        
        # Clear buffer
        self.trajectory_buffer.clear()
        
        result = {
            "induced": len(skills),
            "stored": stored_count,
            "total_successful": self.successful_count
        }
        
        logger.info(f"Skill induction complete: {result}")
        return result
    
    def get_skills(self, skill_type: Optional[str] = None) -> List[Dict]:
        """Get available skills."""
        return self.storage.retrieve(skill_type)
    
    def finalize(self) -> Dict[str, Any]:
        """Process any remaining trajectories and return final stats."""
        result = None
        if self.trajectory_buffer:
            result = self._induce_and_store()
        
        stats = {
            "total_successful": self.successful_count,
            "total_skills": len(self.storage.retrieve()),
            "final_induction": result
        }
        
        logger.info(f"Finalized with stats: {stats}")
        return stats