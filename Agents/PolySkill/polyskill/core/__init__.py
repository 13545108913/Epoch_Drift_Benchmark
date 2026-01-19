"""
Skill Induction Module - Enhanced Architecture

Hierarchical skill induction system with multiple inducer types and enhanced capabilities.
"""

# Core base classes
from .base import (
    Skill,
    SkillType, 
    SkillFormat,
    SkillMetadata,
    SkillInductionResult,
    TrajectoryExample,
    BaseSkillInducer,
    InducerConfig,
    SkillRegistry
)

# Specific inducer implementations
from .inducers import (
    LLMBasedInducer,
    LLMInducerConfig,
    LLMConfig,
    LLMProvider,
    ASIInducer,
    ASIConfig,
    PatternInducer
)

# Enhanced storage with backward compatibility
from .skill_storage import EnhancedSkillStorage, SkillStorage

# Utility modules
from .utils import (
    CodeParser,
    TrajectoryParser,
    PromptManager,
    TestExecutor
)

# Legacy compatibility imports
from .core import (
    OnlineSkillInducer,
    SkillInductionConfig,
    Judge,
    JudgeMethod,
    SkillInducer as CoreSkillInducer  # Original simple inducer
)

# Backward compatibility aliases
SimpleSkillInducer = PatternInducer  # Alias for refactored SimpleSkillInducer

__all__ = [
    # Core base classes
    'Skill',
    'SkillType', 
    'SkillFormat',
    'SkillMetadata',
    'SkillInductionResult',
    'TrajectoryExample',
    'BaseSkillInducer',
    'InducerConfig',
    'SkillRegistry',
    
    # Specific inducers
    'LLMBasedInducer',
    'LLMInducerConfig', 
    'LLMConfig',
    'LLMProvider',
    'ASIInducer',
    'ASIConfig',
    'PatternInducer',
    'SimpleSkillInducer',  # Backward compatibility
    
    # Storage
    'SkillStorage',
    'EnhancedSkillStorage',
    
    # Utilities
    'CodeParser',
    'TrajectoryParser', 
    'PromptManager',
    'TestExecutor',
    
    # Legacy compatibility
    'OnlineSkillInducer',
    'SkillInductionConfig',
    'Judge',
    'JudgeMethod',
    'SkillInducer',  # Original from core
]

__version__ = '3.0.0'  # Enhanced architecture version


def create_inducer(inducer_type: str, config: InducerConfig = None) -> BaseSkillInducer:
    """
    Factory function to create skill inducers by type.
    
    Args:
        inducer_type: Type of inducer ('pattern', 'asi', etc.)
        config: Configuration object
        
    Returns:
        Initialized inducer instance
    """
    if config is None:
        config = InducerConfig()
    
    return SkillRegistry.create(inducer_type, config)


def list_available_inducers() -> list:
    """List all available inducer types."""
    return SkillRegistry.list_inducers()


# Register additional inducers when configs are provided
def register_asi_inducer():
    """Register ASI inducer with registry."""
    SkillRegistry.register("asi", ASIInducer)


def register_llm_inducer():
    """Register LLM inducer with registry."""
    SkillRegistry.register("llm", LLMBasedInducer)


# Auto-register inducers
register_asi_inducer()
register_llm_inducer()