import base64
import io
import os
import logging
import importlib.util
import inspect
from typing import List, Dict, Optional, Any

import numpy as np
from PIL import Image
from browsergym.core.action.highlevel import ACTION_SUBSETS

from polyskill.utils.image_utils import download_image_as_numpy_array
from polyskill.agent.asi_utils.custom_action import CustomActionSet

logger = logging.getLogger(__name__)


def image_to_jpg_base64_url(image: np.ndarray | Image.Image) -> str:
    """Convert a numpy array or PIL Image to a base64 encoded image URL.
    
    Args:
        image: Input image as numpy array or PIL Image
        
    Returns:
        Base64 encoded JPEG image URL string
    """
    if isinstance(image, np.ndarray):
        image = Image.fromarray(image)
    if image.mode in ("RGBA", "LA"):
        image = image.convert("RGB")

    with io.BytesIO() as buffer:
        image.save(buffer, format="JPEG")
        image_base64 = base64.b64encode(buffer.getvalue()).decode()

    return f"data:image/jpeg;base64,{image_base64}"


def load_actions_from_file(file_path: str) -> List[callable]:
    """Dynamically load action functions from a Python file.
    
    Args:
        file_path: Path to the Python file containing action functions
        
    Returns:
        List of callable action functions
        
    Raises:
        FileNotFoundError: If the action file doesn't exist
        ImportError: If the module cannot be loaded
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Action file not found: {file_path}")
    
    # Load the module from file
    spec = importlib.util.spec_from_file_location("custom_actions", file_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Failed to load module from {file_path}")
    
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    
    # Extract only functions that are actually defined in this file (not imported)
    actions = []
    for name, obj in inspect.getmembers(module):
        if (inspect.isfunction(obj) and 
            not name.startswith('_') and 
            hasattr(obj, '__doc__') and 
            obj.__doc__ is not None and
            'Examples:' in obj.__doc__ and
            obj.__module__ == module.__name__):  # Only functions defined in this module
            actions.append(obj)
    
    logger.info(f"Loaded {len(actions)} action functions from {file_path}")
    return actions


def initialize_custom_action_set(action_file_path: Optional[str] = None) -> CustomActionSet:
    """Initialize a CustomActionSet with WebArena actions and optional custom actions.
    
    Args:
        action_file_path: Optional path to file containing additional custom actions
        
    Returns:
        Configured CustomActionSet instance
    """
    custom_actions = ACTION_SUBSETS["webarena"]
    
    # Load dynamic actions from file if provided
    if action_file_path:
        try:
            new_actions = load_actions_from_file(action_file_path)
            custom_actions += new_actions
            logger.info(f"Added {len(new_actions)} custom actions from {action_file_path}")
        except (FileNotFoundError, ImportError) as e:
            logger.warning(f"Could not load custom actions: {e}")
    else:
        logger.info("No custom actions file provided, using default WebArena actions")
    
    return CustomActionSet(
        subsets=["custom"],
        custom_actions=custom_actions,
        strict=False,  # less strict on the parsing of the actions
        multiaction=True,  # enable the agent to take multiple actions at once
    )


def format_goal_object(goal: str, goal_images: Optional[List[np.ndarray]] = None) -> List[Dict[str, Any]]:
    """Format goal text and images into the expected goal_object format.
    
    Args:
        goal: Goal description text
        goal_images: Optional list of goal images as numpy arrays
        
    Returns:
        List of goal message objects in the expected format
    """
    if not goal:
        return []
    
    goal_messages = [{"type": "text", "text": goal}]
    
    # Add goal images if available
    if goal_images:
        for goal_image in goal_images:
            goal_messages.append({
                "type": "image_url", 
                "image_url": {"url": image_to_jpg_base64_url(goal_image)}
            })
    
    return goal_messages


def download_goal_images(goal_image_urls: List[str]) -> List[np.ndarray]:
    """Download goal images from URLs and convert to numpy arrays.
    
    Args:
        goal_image_urls: List of image URLs to download
        
    Returns:
        List of images as numpy arrays
    """
    return [download_image_as_numpy_array(url) for url in goal_image_urls]


def extract_last_action_error(trace: List[Any]) -> str:
    """Extract error message from the last trace entry.
    
    Args:
        trace: List of trace entries
        
    Returns:
        Error message string, empty if no error
    """
    if not trace:
        return ""
    
    # Extract error from the last trace entry
    last_trace = trace[-1]
    if isinstance(last_trace, tuple) and len(last_trace) > 1:
        return str(last_trace[1]) if last_trace[1] else ""
    return ""


def parse_model_configs(model_configs: Dict[str, Any]) -> tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    """Parse model configurations for planner and executor agents.
    
    Args:
        model_configs: Model configuration dictionary
        
    Returns:
        Tuple of (main_configs, planner_configs, executor_configs)
    """
    # Make a copy to avoid modifying the original
    main_configs = model_configs.copy()
    
    planner_configs = main_configs.pop("planner", None)
    executor_configs = main_configs.pop("executor", None)
    
    # Use main configs as fallback if specific configs not provided
    if not planner_configs:
        planner_configs = main_configs
    if not executor_configs:
        executor_configs = main_configs
        
    return main_configs, planner_configs, executor_configs


class ASIAgentMixin:
    """Mixin class providing common functionality for ASI agents."""
    
    def __init__(self):
        self.goal = None
        self.goal_images = []
        self.html_history = []
        self.screenshot_history = []
        self.trace = []
        self.action_history = []
    
    def reset_common_state(self, goal: str, html: str, screenshot: np.ndarray, goal_image_urls: List[str] = None):
        """Reset common agent state.
        
        Args:
            goal: Task goal description
            html: Initial HTML state
            screenshot: Initial screenshot
            goal_image_urls: Optional list of goal image URLs
        """
        self.goal = goal
        self.goal_images = download_goal_images(goal_image_urls or [])
        self.html_history = [html]
        self.screenshot_history = [screenshot]
        self.trace = []
        self.action_history = []
    
    def update_common_state(self, html: str, screenshot: np.ndarray, trace: List[Any]):
        """Update common agent state.
        
        Args:
            html: New HTML state
            screenshot: New screenshot
            trace: Updated trace information
        """
        self.trace = trace
        self.html_history.append(html)
        self.screenshot_history.append(screenshot)
    
    def get_common_state_dict(self) -> Dict[str, Any]:
        """Get common state dictionary for serialization.
        
        Returns:
            Dictionary containing common state information
        """
        return {
            "goal": self.goal,
            "html_history": self.html_history,
            "screenshot_history": self.screenshot_history,
            "trace": self.trace,
            "action_history": self.action_history,
        }
    
    def load_common_state_dict(self, state_dict: Dict[str, Any]):
        """Load common state from dictionary.
        
        Args:
            state_dict: State dictionary to load from
        """
        self.goal = state_dict.get("goal")
        self.html_history = state_dict.get("html_history", [])
        self.screenshot_history = state_dict.get("screenshot_history", [])
        self.trace = state_dict.get("trace", [])
        self.action_history = state_dict.get("action_history", []) 