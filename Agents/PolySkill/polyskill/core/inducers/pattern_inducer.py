"""
Pattern-Based Skill Inducer

Refactored SimpleSkillInducer that extends from BaseSkillInducer.
Uses heuristic pattern matching without LLM dependency.
"""

import json
import logging
from typing import Dict, Any, List, Optional, Union
from pathlib import Path
from datetime import datetime

from ..base import (
    BaseSkillInducer, InducerConfig, Skill, SkillType, 
    SkillFormat, SkillInductionResult, TrajectoryExample, SkillMetadata
)
from ..utils import CodeParser, TrajectoryParser

logger = logging.getLogger(__name__)


class PatternInducer(BaseSkillInducer):
    """
    Pattern-based skill inducer using heuristic pattern matching.
    
    Refactored version of SimpleSkillInducer that extends BaseSkillInducer.
    Uses simple pattern recognition to extract reusable action sequences.
    """
    
    def __init__(self, config: InducerConfig):
        super().__init__(config)
        
        # Pattern matching parameters
        self.min_pattern_frequency = 2  # Minimum times a pattern must appear
        self.max_pattern_length = config.max_actions
        self.min_pattern_length = config.min_actions
        
        # Action similarity thresholds
        self.action_similarity_threshold = 0.7
        self.selector_similarity_threshold = 0.8
    
    def extract_skills(
        self,
        trajectories: List[Union[Dict[str, Any], TrajectoryExample]],
        task_context: Optional[str] = None
    ) -> SkillInductionResult:
        """Extract skills using pattern matching on trajectories."""
        result = SkillInductionResult(success=True)
        
        if not trajectories:
            result.add_error("No trajectories provided")
            return result
        
        try:
            # Convert trajectories to examples
            examples = []
            for traj in trajectories:
                if isinstance(traj, dict):
                    traj = self._dict_to_trajectory_example(traj)
                if traj:
                    examples.append(traj)
            
            if not examples:
                result.add_error("No valid trajectory examples")
                return result
            
            # Group similar trajectories
            grouped_trajectories = self._group_similar_trajectories(examples)
            
            # Extract patterns from each group
            for group_key, group_trajectories in grouped_trajectories.items():
                if len(group_trajectories) >= self.min_pattern_frequency:
                    pattern_skills = self._extract_patterns_from_group(
                        group_trajectories, group_key, task_context
                    )
                    result.skills.extend(pattern_skills)
            
            # Also extract individual action patterns
            action_patterns = self._extract_action_patterns(examples)
            result.skills.extend(action_patterns)
            
            # Remove duplicate skills
            result.skills = self._deduplicate_skills(result.skills)
            
            if not result.skills:
                result.add_error("No patterns found with sufficient frequency")
            
        except Exception as e:
            logger.error(f"Error in pattern skill extraction: {e}")
            result.add_error(f"Pattern extraction failed: {str(e)}")
        
        return result
    
    def _group_similar_trajectories(
        self, 
        examples: List[TrajectoryExample]
    ) -> Dict[str, List[TrajectoryExample]]:
        """Group trajectories by similarity."""
        groups = {}
        
        for example in examples:
            # Create group key based on action patterns
            group_key = self._create_group_key(example)
            
            if group_key not in groups:
                groups[group_key] = []
            groups[group_key].append(example)
        
        return groups
    
    def _create_group_key(self, example: TrajectoryExample) -> str:
        """Create a group key for trajectory similarity."""
        # Extract action types and create signature
        action_types = []
        
        for action in example.actions[:5]:  # First 5 actions for grouping
            action_str = str(action.get("action", "")).lower()
            
            if "click" in action_str:
                action_types.append("click")
            elif "fill" in action_str or "type" in action_str:
                action_types.append("fill")
            elif "select" in action_str:
                action_types.append("select")
            elif "goto" in action_str or "navigate" in action_str:
                action_types.append("navigate")
            else:
                action_types.append("other")
        
        # Include goal keywords
        goal_keywords = self._extract_goal_keywords(example.goal)
        
        return f"{'-'.join(action_types)}_{'-'.join(goal_keywords[:2])}"
    
    def _extract_goal_keywords(self, goal: str) -> List[str]:
        """Extract key words from goal for grouping."""
        goal_lower = goal.lower()
        keywords = []
        
        # Common task keywords
        task_keywords = [
            "login", "search", "add", "create", "delete", "remove", "update",
            "submit", "click", "fill", "select", "navigate", "buy", "purchase",
            "register", "signup", "checkout", "cart", "product", "user", "account"
        ]
        
        for keyword in task_keywords:
            if keyword in goal_lower:
                keywords.append(keyword)
        
        return keywords or ["general"]
    
    def _extract_patterns_from_group(
        self,
        group_trajectories: List[TrajectoryExample],
        group_key: str,
        task_context: Optional[str] = None
    ) -> List[Skill]:
        """Extract common patterns from a group of similar trajectories."""
        skills = []
        
        # Find common action sequences
        common_sequences = self._find_common_sequences(group_trajectories)
        
        for i, sequence in enumerate(common_sequences):
            if len(sequence) >= self.min_pattern_length:
                skill = self._create_pattern_skill(
                    sequence, group_trajectories, f"{group_key}_pattern_{i}"
                )
                if skill:
                    skills.append(skill)
        
        return skills
    
    def _find_common_sequences(
        self, 
        trajectories: List[TrajectoryExample]
    ) -> List[List[Dict[str, Any]]]:
        """Find common action sequences across trajectories."""
        if len(trajectories) < 2:
            return []
        
        common_sequences = []
        
        # Get action sequences
        action_sequences = []
        for traj in trajectories:
            actions = [self._normalize_action(action) for action in traj.actions]
            action_sequences.append(actions)
        
        # Find common prefixes
        min_length = min(len(seq) for seq in action_sequences)
        
        for length in range(self.min_pattern_length, min(min_length + 1, self.max_pattern_length + 1)):
            # Check if all trajectories have same pattern at this length
            first_sequence = action_sequences[0][:length]
            
            is_common = True
            for seq in action_sequences[1:]:
                if not self._sequences_similar(first_sequence, seq[:length]):
                    is_common = False
                    break
            
            if is_common:
                common_sequences.append(first_sequence)
        
        return common_sequences
    
    def _normalize_action(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize action for pattern matching."""
        action_str = str(action.get("action", ""))
        
        # Extract action type
        action_type = "other"
        if "click" in action_str.lower():
            action_type = "click"
        elif "fill" in action_str.lower() or "type" in action_str.lower():
            action_type = "fill"
        elif "select" in action_str.lower():
            action_type = "select"
        elif "goto" in action_str.lower() or "navigate" in action_str.lower():
            action_type = "navigate"
        
        # Extract potential selector
        selector = self._extract_selector(action_str)
        
        return {
            "type": action_type,
            "selector": selector,
            "original": action_str
        }
    
    def _extract_selector(self, action_str: str) -> str:
        """Extract selector from action string."""
        import re
        
        # Common selector patterns
        patterns = [
            r"['\"]([^'\"]*)['\"]",  # Quoted strings
            r"#[\w-]+",              # IDs
            r"\.[\w-]+",             # Classes
            r"\[[\w-]+[=]*['\"][^'\"]*['\"][^\]]*\]"  # Attribute selectors
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, action_str)
            if matches:
                return matches[0] if isinstance(matches[0], str) else str(matches[0])
        
        return ""
    
    def _sequences_similar(
        self, 
        seq1: List[Dict[str, Any]], 
        seq2: List[Dict[str, Any]]
    ) -> bool:
        """Check if two action sequences are similar."""
        if len(seq1) != len(seq2):
            return False
        
        for action1, action2 in zip(seq1, seq2):
            if action1["type"] != action2["type"]:
                return False
            
            # Check selector similarity for specific actions
            if action1["type"] in ["click", "fill", "select"]:
                if not self._selectors_similar(action1["selector"], action2["selector"]):
                    return False
        
        return True
    
    def _selectors_similar(self, sel1: str, sel2: str) -> bool:
        """Check if two selectors are similar."""
        if not sel1 or not sel2:
            return sel1 == sel2
        
        # Exact match
        if sel1 == sel2:
            return True
        
        # Check for similar structure
        # This is a simple heuristic - could be more sophisticated
        return self._string_similarity(sel1, sel2) >= self.selector_similarity_threshold
    
    def _string_similarity(self, s1: str, s2: str) -> float:
        """Calculate string similarity using simple character overlap."""
        if not s1 or not s2:
            return 0.0
        
        s1_chars = set(s1.lower())
        s2_chars = set(s2.lower())
        
        intersection = s1_chars.intersection(s2_chars)
        union = s1_chars.union(s2_chars)
        
        return len(intersection) / len(union) if union else 0.0
    
    def _extract_action_patterns(
        self, 
        examples: List[TrajectoryExample]
    ) -> List[Skill]:
        """Extract individual action patterns across all examples."""
        skills = []
        
        # Count action type sequences
        action_sequences = {}
        
        for example in examples:
            # Extract sliding windows of actions
            for window_size in range(self.min_pattern_length, min(len(example.actions) + 1, self.max_pattern_length + 1)):
                for i in range(len(example.actions) - window_size + 1):
                    window = example.actions[i:i + window_size]
                    
                    # Create pattern key
                    pattern_key = self._create_action_pattern_key(window)
                    
                    if pattern_key not in action_sequences:
                        action_sequences[pattern_key] = {
                            'actions': window,
                            'count': 0,
                            'examples': []
                        }
                    
                    action_sequences[pattern_key]['count'] += 1
                    action_sequences[pattern_key]['examples'].append(example.goal)
        
        # Create skills for frequent patterns
        for pattern_key, pattern_info in action_sequences.items():
            if pattern_info['count'] >= self.min_pattern_frequency:
                skill = self._create_action_pattern_skill(
                    pattern_info['actions'],
                    pattern_info['examples'],
                    pattern_key
                )
                if skill:
                    skills.append(skill)
        
        return skills
    
    def _create_action_pattern_key(self, actions: List[Dict[str, Any]]) -> str:
        """Create a key for action pattern."""
        normalized = [self._normalize_action(action) for action in actions]
        action_types = [action["type"] for action in normalized]
        return f"action_pattern_{'_'.join(action_types)}"
    
    def _create_pattern_skill(
        self,
        sequence: List[Dict[str, Any]],
        source_trajectories: List[TrajectoryExample],
        skill_id: str
    ) -> Optional[Skill]:
        """Create a skill from an action pattern sequence."""
        try:
            # Generate skill name
            skill_name = self._generate_skill_name(sequence, source_trajectories)
            
            # Create action sequence content
            action_sequence = []
            for action in sequence:
                action_sequence.append({
                    "type": action["type"],
                    "selector": action["selector"],
                    "description": f"{action['type'].title()} on {action['selector'] or 'element'}"
                })
            
            # Get task examples
            task_examples = [traj.goal for traj in source_trajectories[:3]]
            
            skill = Skill(
                id=f"pattern_{skill_id}",
                name=skill_name,
                skill_type=SkillType.PATTERN,
                format=SkillFormat.ACTION_SEQUENCE,
                content=action_sequence,
                description=f"Action pattern: {' -> '.join([a['type'] for a in sequence])}",
                task_examples=task_examples,
                metadata=SkillMetadata(
                    source='PatternInducer',
                    confidence_score=min(len(source_trajectories) / 5.0, 1.0),
                    tags=['pattern_based', 'action_sequence']
                )
            )
            
            return skill
            
        except Exception as e:
            logger.error(f"Error creating pattern skill: {e}")
            return None
    
    def _create_action_pattern_skill(
        self,
        actions: List[Dict[str, Any]],
        example_goals: List[str],
        pattern_key: str
    ) -> Optional[Skill]:
        """Create a skill from action pattern."""
        try:
            # Normalize actions
            normalized_actions = [self._normalize_action(action) for action in actions]
            
            # Generate name
            action_types = [action["type"] for action in normalized_actions]
            skill_name = f"{'_'.join(action_types)}_pattern"
            
            skill = Skill(
                id=f"action_{pattern_key}",
                name=skill_name,
                skill_type=SkillType.PATTERN,
                format=SkillFormat.ACTION_SEQUENCE,
                content=normalized_actions,
                description=f"Repeated action pattern: {' -> '.join(action_types)}",
                task_examples=example_goals[:3],
                metadata=SkillMetadata(
                    source='PatternInducer',
                    confidence_score=min(len(example_goals) / 10.0, 1.0),
                    tags=['pattern_based', 'action_sequence', 'frequent']
                )
            )
            
            return skill
            
        except Exception as e:
            logger.error(f"Error creating action pattern skill: {e}")
            return None
    
    def _generate_skill_name(
        self,
        sequence: List[Dict[str, Any]],
        trajectories: List[TrajectoryExample]
    ) -> str:
        """Generate a descriptive name for the skill."""
        # Extract action types
        action_types = []
        action_keywords = []
        
        for action in sequence:
            action_type = action["type"]
            action_types.append(action_type)
            
            # Extract keywords from selector
            selector = action.get("selector", "")
            if "button" in selector.lower():
                action_keywords.append("button")
            elif "input" in selector.lower() or "form" in selector.lower():
                action_keywords.append("form")
            elif "menu" in selector.lower() or "nav" in selector.lower():
                action_keywords.append("menu")
        
        # Extract task keywords
        task_words = []
        for traj in trajectories[:3]:  # Use first 3 trajectories
            goal_keywords = self._extract_goal_keywords(traj.goal)
            task_words.extend(goal_keywords)
        
        # Remove duplicates and take most common
        from collections import Counter
        task_word_counts = Counter(task_words)
        top_task_words = [word for word, count in task_word_counts.most_common(2)]
        
        # Combine to form skill name
        name_parts = []
        if action_types:
            unique_types = list(dict.fromkeys(action_types))  # Preserve order, remove duplicates
            name_parts.extend(unique_types[:2])
        if top_task_words:
            name_parts.extend(top_task_words[:1])
        if action_keywords:
            name_parts.extend(list(set(action_keywords))[:1])
        
        if name_parts:
            return '_'.join(name_parts)
        else:
            return f'pattern_{len(sequence)}_actions'
    
    def _deduplicate_skills(self, skills: List[Skill]) -> List[Skill]:
        """Remove duplicate skills based on similarity."""
        unique_skills = []
        
        for skill in skills:
            is_duplicate = False
            for existing_skill in unique_skills:
                if skill.is_similar_to(existing_skill, self.config.similarity_threshold):
                    # Merge information into existing skill
                    existing_skill.add_task_example(skill.task_examples[0] if skill.task_examples else "")
                    existing_skill.metadata.success_count += 1
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                unique_skills.append(skill)
        
        return unique_skills
    
    def validate_skill(self, skill: Skill) -> bool:
        """Validate that a pattern-based skill is well-formed."""
        if not skill.name or not skill.content:
            return False
        
        if skill.skill_type == SkillType.PATTERN:
            # Validate action sequence format
            if skill.format == SkillFormat.ACTION_SEQUENCE:
                try:
                    if not isinstance(skill.content, list):
                        return False
                    
                    for action in skill.content:
                        if not isinstance(action, dict) or "type" not in action:
                            return False
                    
                    return len(skill.content) >= self.min_pattern_length
                
                except Exception:
                    return False
        
        return True