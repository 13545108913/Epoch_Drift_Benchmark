"""
LLM as Judge integration for Digital Agent trajectory evaluation.

This module provides evaluation methods adapted from Online-Mind2Web to assess
trajectory data saved by the digital agent evaluation framework.
"""

from .trajectory_judge import TrajectoryJudge
from .utils import extract_screenshots_from_trajectory, load_trajectory_data

__all__ = ['TrajectoryJudge', 'extract_screenshots_from_trajectory', 'load_trajectory_data']