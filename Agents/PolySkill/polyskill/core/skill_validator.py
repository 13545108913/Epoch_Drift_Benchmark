"""
Skill Validator

Validates induced skills by testing them on tasks.
"""

import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class SkillValidator:
    """Validates induced skills for correctness."""
    
    def validate(
        self,
        skill: Dict[str, Any],
        test_task: Dict[str, Any]
    ) -> bool:
        """
        Validate a skill against a test task.
        
        Args:
            skill: Induced skill to validate
            test_task: Task to test against
            
        Returns:
            True if skill is valid
        """
        if skill["type"] == "code":
            return self._validate_code_skill(skill, test_task)
        else:
            return self._validate_nl_workflow(skill, test_task)
    
    def _validate_code_skill(self, skill: Dict, task: Dict) -> bool:
        """Validate code skill."""
        try:
            # Check syntax
            code = skill["content"]
            compile(code, '<string>', 'exec')
            
            # Check if actions match task
            task_actions = [s["action"] for s in task.get("trajectory", {}).get("steps", [])]
            skill_actions = self._extract_actions_from_code(code)
            
            # Basic validation: at least some overlap
            overlap = set(skill_actions) & set(task_actions)
            return len(overlap) > 0
            
        except SyntaxError:
            logger.error(f"Syntax error in skill: {skill['name']}")
            return False
        except Exception as e:
            logger.error(f"Validation error: {e}")
            return False
    
    def _validate_nl_workflow(self, skill: Dict, task: Dict) -> bool:
        """Validate natural language workflow."""
        # Basic validation: check if workflow has steps
        content = skill["content"]
        return "Task:" in content and ("Step" in content or "1." in content)
    
    def _extract_actions_from_code(self, code: str) -> List[str]:
        """Extract action calls from code."""
        actions = []
        for line in code.split('\n'):
            for action in ['click', 'fill', 'scroll', 'hover', 'select_option']:
                if action + '(' in line:
                    actions.append(action)
        return actions