"""
PolySkill: Learning Generalizable Skills Through Polymorphic Abstraction

Official implementation of the PolySkill framework for web agent skill learning.
"""

__version__ = "0.1.0"
__author__ = "Simon Yu, Gang Li, Weiyan Shi, Peng Qi"
__email__ = "yu.chi@northeastern.edu"

from .core import SkillInductionCore
from .core.skill_storage import PolySkillStorage

__all__ = [
    "SkillInductionCore",
    "PolySkillStorage",
    "__version__",
]
