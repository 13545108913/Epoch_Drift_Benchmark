"""
Skill Representation Classes

Defines the core data structures for representing learned skills.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, Any, List, Optional, Union
import json


class SkillType(Enum):
    """Types of skills that can be induced."""
    CODE = "code"
    PATTERN = "pattern"
    WORKFLOW = "workflow"
    NATURAL_LANGUAGE = "natural_language"


class SkillFormat(Enum):
    """Formats for skill representation."""
    PYTHON_FUNCTION = "python_function"
    ACTION_SEQUENCE = "action_sequence"
    NATURAL_LANGUAGE = "natural_language"
    JSON_PATTERN = "json_pattern"


@dataclass
class SkillMetadata:
    """Metadata associated with a skill."""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    success_count: int = 0
    failure_count: int = 0
    confidence_score: float = 0.0
    source: str = ""  # Which inducer created this skill
    version: int = 1
    tags: List[str] = field(default_factory=list)
    
    def update(self):
        """Update the updated_at timestamp."""
        self.updated_at = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'success_count': self.success_count,
            'failure_count': self.failure_count,
            'confidence_score': self.confidence_score,
            'source': self.source,
            'version': self.version,
            'tags': self.tags
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SkillMetadata':
        return cls(**data)


@dataclass
class Skill:
    """
    Core skill representation that can handle different skill types and formats.
    """
    id: str
    name: str
    skill_type: SkillType
    format: SkillFormat
    content: Union[str, Dict[str, Any], List[Dict[str, Any]]]
    description: str = ""
    task_examples: List[str] = field(default_factory=list)
    metadata: SkillMetadata = field(default_factory=SkillMetadata)
    
    def __post_init__(self):
        # Ensure skill_type and format are enums
        if isinstance(self.skill_type, str):
            self.skill_type = SkillType(self.skill_type)
        if isinstance(self.format, str):
            self.format = SkillFormat(self.format)
    
    def add_task_example(self, task: str):
        """Add a task example if not already present."""
        if task not in self.task_examples:
            self.task_examples.append(task)
            self.metadata.update()
    
    def record_success(self):
        """Record a successful use of this skill."""
        self.metadata.success_count += 1
        self.metadata.update()
        
        # Update confidence score based on success rate
        total_uses = self.metadata.success_count + self.metadata.failure_count
        if total_uses > 0:
            self.metadata.confidence_score = self.metadata.success_count / total_uses
    
    def record_failure(self):
        """Record a failed use of this skill."""
        self.metadata.failure_count += 1
        self.metadata.update()
        
        # Update confidence score based on success rate
        total_uses = self.metadata.success_count + self.metadata.failure_count
        if total_uses > 0:
            self.metadata.confidence_score = self.metadata.success_count / total_uses
    
    def is_similar_to(self, other: 'Skill', similarity_threshold: float = 0.8) -> bool:
        """Check if this skill is similar to another skill."""
        # Simple similarity check based on name and type
        if self.skill_type != other.skill_type or self.format != other.format:
            return False
        
        # Check name similarity (simple word overlap)
        self_words = set(self.name.lower().split('_'))
        other_words = set(other.name.lower().split('_'))
        
        if not self_words or not other_words:
            return False
        
        overlap = len(self_words.intersection(other_words))
        similarity = overlap / max(len(self_words), len(other_words))
        
        return similarity >= similarity_threshold
    
    def get_content_as_string(self) -> str:
        """Get content as a string regardless of format."""
        if isinstance(self.content, str):
            return self.content
        elif isinstance(self.content, (dict, list)):
            return json.dumps(self.content, indent=2)
        else:
            return str(self.content)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert skill to dictionary for serialization."""
        return {
            'id': self.id,
            'name': self.name,
            'skill_type': self.skill_type.value,
            'format': self.format.value,
            'content': self.content,
            'description': self.description,
            'task_examples': self.task_examples,
            'metadata': self.metadata.to_dict()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Skill':
        """Create skill from dictionary."""
        metadata_data = data.get('metadata', {})
        metadata = SkillMetadata.from_dict(metadata_data)
        
        return cls(
            id=data['id'],
            name=data['name'],
            skill_type=SkillType(data['skill_type']),
            format=SkillFormat(data['format']),
            content=data['content'],
            description=data.get('description', ''),
            task_examples=data.get('task_examples', []),
            metadata=metadata
        )


@dataclass
class SkillInductionResult:
    """Result of a skill induction process."""
    success: bool
    skills: List[Skill] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def add_skill(self, skill: Skill):
        """Add a skill to the result."""
        self.skills.append(skill)
    
    def add_error(self, error: str):
        """Add an error to the result."""
        self.errors.append(error)
        self.success = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'success': self.success,
            'skills': [skill.to_dict() for skill in self.skills],
            'errors': self.errors,
            'metadata': self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SkillInductionResult':
        skills = [Skill.from_dict(skill_data) for skill_data in data.get('skills', [])]
        return cls(
            success=data['success'],
            skills=skills,
            errors=data.get('errors', []),
            metadata=data.get('metadata', {})
        )


@dataclass
class TrajectoryExample:
    """A trajectory example for skill induction."""
    task_id: str
    goal: str
    actions: List[Dict[str, Any]]
    success: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'task_id': self.task_id,
            'goal': self.goal,
            'actions': self.actions,
            'success': self.success,
            'metadata': self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TrajectoryExample':
        return cls(
            task_id=data['task_id'],
            goal=data['goal'],
            actions=data['actions'],
            success=data.get('success', True),
            metadata=data.get('metadata', {})
        )