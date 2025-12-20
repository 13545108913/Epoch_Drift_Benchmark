"""
Trajectory Cleaner

Cleans and filters trajectories to remove invalid steps, errors, and redundancies.
Prepares trajectories for skill induction.
"""

import re
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from polyskill.model.fm import FoundationModel

logger = logging.getLogger(__name__)


# Actions that provide information but don't change state
INFO_ACTIONS = ["send_msg_to_user", "report_infeasible"]

# Actions that typically indicate exploration or errors
SKIP_ACTIONS = ["go_back", "go_forward", "report_infeasible"]


@dataclass
class CleanedStep:
    """A cleaned trajectory step."""
    action: str
    thought: str = ""
    state_change: bool = True
    is_info_action: bool = False
    step_number: int = 0


class TrajectoryCleaner:
    """
    Cleans trajectories for skill induction.
    
    Removes:
    - Invalid/error steps
    - Redundant actions
    - Steps that don't change state
    - Unnecessary exploration
    """
    
    def __init__(self, use_llm_simplification: bool = False, model_name: str = "gpt-4"):
        """
        Initialize the trajectory cleaner.
        
        Args:
            use_llm_simplification: Whether to use LLM to simplify thoughts
            model_name: Model to use for simplification
        """
        self.use_llm_simplification = use_llm_simplification
        
        if use_llm_simplification:
            self.model = FoundationModel(
                provider="openai" if "gpt" in model_name else "anthropic",
                name=model_name,
                temperature=0.0
            )
        else:
            self.model = None
    
    def clean(
        self,
        trajectory: Dict[str, Any],
        min_length: int = 2,
        remove_errors: bool = True,
        remove_redundant: bool = True,
        simplify_thoughts: bool = False
    ) -> Optional[Dict[str, Any]]:
        """
        Clean a trajectory for skill induction.
        
        Args:
            trajectory: Raw trajectory data
            min_length: Minimum number of steps required
            remove_errors: Whether to remove error steps
            remove_redundant: Whether to remove redundant actions
            simplify_thoughts: Whether to simplify thought descriptions
            
        Returns:
            Cleaned trajectory or None if too short
        """
        # Extract steps from trajectory
        raw_steps = self._extract_steps(trajectory)
        
        if not raw_steps:
            logger.warning("No steps found in trajectory")
            return None
        
        # Filter steps
        cleaned_steps = []
        last_state = None
        
        for i, step in enumerate(raw_steps):
            # Check if step is valid
            if remove_errors and not self._is_valid_step(step):
                logger.debug(f"Removing invalid step {i}: {step.get('action', '')}")
                continue
            
            # Check for state change or info action
            is_info = self._is_info_action(step)
            has_state_change = self._has_state_change(step, last_state)
            
            if not is_info and not has_state_change and remove_redundant:
                logger.debug(f"Removing redundant step {i}: {step.get('action', '')}")
                continue
            
            # Skip certain actions
            if self._should_skip_action(step.get("action", "")):
                logger.debug(f"Skipping action {i}: {step.get('action', '')}")
                continue
            
            # Clean the step
            cleaned_step = self._clean_step(step, simplify_thoughts)
            cleaned_steps.append(cleaned_step)
            
            last_state = step.get("after_state", step.get("state"))
        
        # Check minimum length
        if len(cleaned_steps) < min_length:
            logger.info(f"Trajectory too short after cleaning: {len(cleaned_steps)} < {min_length}")
            return None
        
        # Build cleaned trajectory
        cleaned_trajectory = {
            "goal": trajectory.get("goal", ""),
            "original_length": len(raw_steps),
            "cleaned_length": len(cleaned_steps),
            "steps": cleaned_steps,
            "metadata": {
                "task_id": trajectory.get("task_id"),
                "timestamp": trajectory.get("timestamp"),
                "agent": trajectory.get("agent_config", {}).get("name") if "agent_config" in trajectory else None
            }
        }
        
        logger.info(f"Cleaned trajectory: {len(raw_steps)} -> {len(cleaned_steps)} steps")
        
        return cleaned_trajectory
    
    def _extract_steps(self, trajectory: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract steps from various trajectory formats."""
        # Try different formats
        if "steps" in trajectory:
            return trajectory["steps"]
        
        if "actions" in trajectory:
            # Convert actions to steps format
            actions = trajectory["actions"]
            states = trajectory.get("states", [None] * len(actions))
            thoughts = trajectory.get("thoughts", [""] * len(actions))
            
            steps = []
            for i, (action, state, thought) in enumerate(zip(actions, states, thoughts)):
                steps.append({
                    "action": action,
                    "state": state,
                    "thought": thought,
                    "step_number": i
                })
            return steps
        
        if "trajectory" in trajectory:
            # Nested trajectory
            return self._extract_steps(trajectory["trajectory"])
        
        # Try to extract from other formats
        logger.warning("Unknown trajectory format, attempting extraction")
        return []
    
    def _is_valid_step(self, step: Dict[str, Any]) -> bool:
        """Check if a step is valid (no errors)."""
        # Check for error indicators
        error = step.get("error", step.get("last_action_error", ""))
        
        if error and not error.startswith("TimeoutError"):
            return False
        
        # Check for empty action
        action = step.get("action", step.get("last_action", ""))
        if not action or action.strip() == "":
            return False
        
        return True
    
    def _is_info_action(self, step: Dict[str, Any]) -> bool:
        """Check if action provides information without state change."""
        action = step.get("action", "")
        return any(info_act in action for info_act in INFO_ACTIONS)
    
    def _has_state_change(self, step: Dict[str, Any], last_state: Any) -> bool:
        """Check if step causes a state change."""
        if last_state is None:
            return True  # First step
        
        current_state = step.get("after_state", step.get("state"))
        
        if current_state is None or last_state is None:
            return True  # Can't determine, assume change
        
        # Compare states (simplified comparison)
        if isinstance(current_state, dict) and isinstance(last_state, dict):
            # Check key indicators of state change
            for key in ["url", "page_title", "dom_hash", "axtree_txt"]:
                if key in current_state and key in last_state:
                    if current_state[key] != last_state[key]:
                        return True
        
        return current_state != last_state
    
    def _should_skip_action(self, action: str) -> bool:
        """Check if action should be skipped."""
        for skip_act in SKIP_ACTIONS:
            if skip_act in action:
                return True
        return False
    
    def _clean_step(self, step: Dict[str, Any], simplify_thoughts: bool) -> Dict[str, Any]:
        """Clean and format a single step."""
        action = step.get("action", step.get("last_action", ""))
        thought = step.get("thought", "")
        
        # Clean action
        action = self._clean_action(action)
        
        # Simplify thought if requested
        if simplify_thoughts and thought and self.use_llm_simplification:
            thought = self._simplify_thought(thought)
        
        return {
            "action": action,
            "thought": thought,
            "step_number": step.get("step_number", 0),
            "is_info_action": self._is_info_action(step)
        }
    
    def _clean_action(self, action: str) -> str:
        """Clean and normalize an action string."""
        # Remove extra whitespace
        action = action.strip()
        
        # Normalize quotes
        action = action.replace("'", '"')
        
        # Remove comments if present
        if "#" in action:
            action = action[:action.index("#")].strip()
        
        return action
    
    def _simplify_thought(self, thought: str) -> str:
        """Use LLM to simplify a thought description."""
        if not self.model:
            return thought
        
        prompt = f"""Simplify this thought into a concise description (max 1 sentence):

{thought}

Simplified:"""
        
        try:
            simplified = self.model.generate(
                prompt=prompt,
                max_tokens=50,
                temperature=0.0
            )
            return simplified.strip()
        except Exception as e:
            logger.error(f"Error simplifying thought: {e}")
            return thought[:100] + "..." if len(thought) > 100 else thought


class TrajectoryValidator:
    """
    Validates trajectories for skill induction readiness.
    """
    
    @staticmethod
    def validate_for_induction(
        trajectory: Dict[str, Any],
        min_steps: int = 2,
        max_steps: int = 20,
        require_success: bool = True
    ) -> tuple[bool, str]:
        """
        Validate if a trajectory is suitable for skill induction.
        
        Args:
            trajectory: Cleaned trajectory
            min_steps: Minimum required steps
            max_steps: Maximum allowed steps
            require_success: Whether trajectory must be successful
            
        Returns:
            Tuple of (is_valid, reason)
        """
        # Check if trajectory exists
        if not trajectory:
            return False, "Trajectory is empty"
        
        # Check steps
        steps = trajectory.get("steps", [])
        if len(steps) < min_steps:
            return False, f"Too few steps: {len(steps)} < {min_steps}"
        
        if len(steps) > max_steps:
            return False, f"Too many steps: {len(steps)} > {max_steps}"
        
        # Check for goal
        if not trajectory.get("goal"):
            return False, "No goal specified"
        
        # Check for success if required
        if require_success:
            # Check for success indicators
            has_info_action = any(
                step.get("is_info_action", False) 
                for step in steps
            )
            
            if not has_info_action:
                # Check for other success indicators
                last_step = steps[-1]
                if "send_msg_to_user" not in last_step.get("action", ""):
                    return False, "No clear success indicator"
        
        # Check action validity
        for i, step in enumerate(steps):
            if not step.get("action"):
                return False, f"Step {i} has no action"
        
        return True, "Valid trajectory for induction"