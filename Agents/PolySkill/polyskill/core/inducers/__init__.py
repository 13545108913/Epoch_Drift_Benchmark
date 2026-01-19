"""
Skill Inducer Implementations

Different implementations of skill inducers.
"""

from .llm_inducer import LLMBasedInducer, LLMInducerConfig, LLMConfig, LLMProvider
from .asi_inducer import ASIInducer, ASIConfig
from .pattern_inducer import PatternInducer

# Register inducers
from ..base import SkillRegistry, InducerConfig

# Register pattern inducer
SkillRegistry.register("pattern", PatternInducer)

# Register LLM-based inducers (need configs)
# These will be registered when configs are provided

__all__ = [
    'LLMBasedInducer',
    'LLMInducerConfig', 
    'LLMConfig',
    'LLMProvider',
    'ASIInducer',
    'ASIConfig',
    'PatternInducer'
]