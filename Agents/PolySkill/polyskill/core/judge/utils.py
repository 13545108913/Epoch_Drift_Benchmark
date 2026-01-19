"""
Utility functions for processing digital agent trajectory data for LLM judging.
"""

import base64
import io
import os
import lzma
from typing import List, Optional, Tuple
from PIL import Image

from fm.trajectory_data_pb2 import TrajectoryData


def encode_image(image: Image.Image) -> str:
    """Convert a PIL image to base64 string."""
    if image.mode == "RGBA":
        image = image.convert("RGB")
    buffered = io.BytesIO()
    image.save(buffered, format="JPEG")
    return base64.b64encode(buffered.getvalue()).decode('utf-8')


def load_trajectory_data(trajectory_path: str) -> TrajectoryData:
    """
    Load trajectory data from protobuf file.
    
    Args:
        trajectory_path: Path to trajectory.pb.xz file
        
    Returns:
        TrajectoryData protobuf object
    """
    trajectory_data = TrajectoryData()
    
    with lzma.open(trajectory_path, 'rb') as f:
        trajectory_data.ParseFromString(f.read())
    
    return trajectory_data


def extract_screenshots_from_trajectory(trajectory_data: TrajectoryData, 
                                       save_dir: Optional[str] = None,
                                       max_images: int = 50) -> List[str]:
    """
    Extract screenshots from trajectory data and optionally save them.
    
    Args:
        trajectory_data: TrajectoryData protobuf object
        save_dir: Directory to save screenshots (optional)
        max_images: Maximum number of images to extract
        
    Returns:
        List of image paths (if save_dir provided) or base64 strings
    """
    screenshots = []
    
    for i, action_data in enumerate(trajectory_data.actions[:max_images]):
        if (action_data.after_state.viewport and 
            action_data.after_state.viewport.screenshot and
            action_data.after_state.viewport.screenshot.content):
            
            screenshot_content = action_data.after_state.viewport.screenshot.content
            
            # The content is already binary data, not base64
            image = Image.open(io.BytesIO(screenshot_content))
            
            if save_dir:
                # Save image to file
                os.makedirs(save_dir, exist_ok=True)
                image_path = os.path.join(save_dir, f"screenshot_{i:03d}.png")
                image.save(image_path)
                screenshots.append(image_path)
            else:
                # Return base64 string
                screenshots.append(encode_image(image))
    
    return screenshots


def get_final_response_from_trajectory(trajectory_data: TrajectoryData) -> str:
    """
    Extract the final response/answer from trajectory data.
    
    Args:
        trajectory_data: TrajectoryData protobuf object
        
    Returns:
        Final response string
    """
    if trajectory_data.HasField('success'):
        return trajectory_data.success.answer
    elif trajectory_data.HasField('failure'):
        failure_types = {
            0: "Unspecified failure",
            1: "Maximum steps exceeded", 
            2: "Task reported as infeasible",
            3: "Repetitive actions detected",
            4: "Unknown error occurred"
        }
        failure_msg = failure_types.get(trajectory_data.failure.failure_message, "Unknown failure")
        return f"Task failed: {failure_msg}"
    else:
        return "No result available"


def extract_task_from_trajectory(trajectory_data: TrajectoryData) -> str:
    """
    Extract the task/goal from trajectory data.
    
    Args:
        trajectory_data: TrajectoryData protobuf object
        
    Returns:
        Task description string
    """
    return trajectory_data.goal


def get_trajectory_success_status(trajectory_data: TrajectoryData) -> bool:
    """
    Determine if trajectory was successful based on result.
    
    Args:
        trajectory_data: TrajectoryData protobuf object
        
    Returns:
        True if successful, False otherwise
    """
    return trajectory_data.HasField('success')


def extract_actions_from_trajectory(trajectory_data: TrajectoryData) -> List[str]:
    """
    Extract action descriptions from trajectory data.
    
    Args:
        trajectory_data: TrajectoryData protobuf object
        
    Returns:
        List of action description strings
    """
    actions = []
    
    for action_data in trajectory_data.actions:
        if hasattr(action_data, 'action') and action_data.action:
            # Try to get a human-readable action description
            action_str = ""
            
            # Check for different action types
            if hasattr(action_data.action, 'click') and action_data.action.HasField('click'):
                click = action_data.action.click
                if hasattr(click, 'coordinate'):
                    action_str = f"Click at ({click.coordinate.x}, {click.coordinate.y})"
                elif hasattr(click, 'element_selector'):
                    action_str = f"Click element: {click.element_selector}"
                else:
                    action_str = "Click action"
                    
            elif hasattr(action_data.action, 'type') and action_data.action.HasField('type'):
                type_action = action_data.action.type
                text = getattr(type_action, 'text', '')
                action_str = f"Type: '{text}'"
                
            elif hasattr(action_data.action, 'scroll') and action_data.action.HasField('scroll'):
                scroll = action_data.action.scroll
                direction = getattr(scroll, 'direction', 'unknown')
                action_str = f"Scroll {direction}"
                
            elif hasattr(action_data.action, 'key') and action_data.action.HasField('key'):
                key_action = action_data.action.key
                key = getattr(key_action, 'key', '')
                action_str = f"Press key: {key}"
                
            else:
                # Fallback: try to get string representation
                action_str = str(action_data.action)
                
            actions.append(action_str)
    
    return actions