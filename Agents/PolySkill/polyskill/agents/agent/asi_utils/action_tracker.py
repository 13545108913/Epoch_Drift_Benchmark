import json
import os
import time
import threading
from collections import defaultdict
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional, List
from datetime import datetime
import hashlib
import re

@dataclass
class ActionStats:
    """Statistics for a specific action."""
    name: str
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    error_messages: List[str] = None
    first_used: Optional[str] = None
    last_used: Optional[str] = None
    
    def __post_init__(self):
        if self.error_messages is None:
            self.error_messages = []
    
    def add_call(self, success: bool, error_message: str = None):
        """Add a call record to this action's stats."""
        now = datetime.now().isoformat()
        
        if self.first_used is None:
            self.first_used = now
        self.last_used = now
        
        self.total_calls += 1
        if success:
            self.successful_calls += 1
        else:
            self.failed_calls += 1
            if error_message:
                self.error_messages.append(error_message)

@dataclass
class ExperimentData:
    """Complete tracking data for an experiment run."""
    experiment_id: str
    config_hash: str  # Hash of the configuration for grouping similar experiments
    agent_name: str
    model_name: str
    benchmark_name: str
    start_time: str
    end_time: Optional[str] = None
    
    # Statistics
    total_examples: int = 0
    successful_examples: int = 0
    total_steps: int = 0
    
    # Action tracking
    actions: Dict[str, ActionStats] = None
    
    # Error patterns
    error_patterns: Dict[str, int] = None
    
    def __post_init__(self):
        if self.actions is None:
            self.actions = {}
        if self.error_patterns is None:
            self.error_patterns = {}


class ActionTracker:
    """
    Thread-safe action usage and error tracking system.
    
    Flow:
    1. start_experiment() -> Creates experiment ID and tracking structure
    2. track_action() -> Records each action execution with success/failure
    3. track_example_completion() -> Records episode completion
    4. end_experiment() -> Saves data to cache file
    5. get_summary() -> Analyzes cached data
    """
    
    def __init__(self, cache_dir: str = "./action_tracking_cache"):
        self.cache_dir = os.path.abspath(cache_dir)
        self.lock = threading.Lock()
        self._ensure_cache_dir()
        
        # Current session tracking
        self.current_experiment: Optional[ExperimentData] = None
        
    def _ensure_cache_dir(self):
        """Create cache directory if it doesn't exist."""
        os.makedirs(self.cache_dir, exist_ok=True)
        print(f"Action tracking cache directory: {self.cache_dir}")
        
    def _generate_config_hash(self, agent_config: Dict, benchmark_config: Dict) -> str:
        """Generate a hash for grouping similar configurations."""
        config_key = {
            "agent": agent_config.get("name", "unknown"),
            "model": agent_config.get("model", {}).get("name", "unknown"),
            "provider": agent_config.get("model", {}).get("provider", "unknown"),
            "dataset": benchmark_config.get("dataset", "unknown"),
            "action_file": agent_config.get("action_file_path", "default"),
        }
        return hashlib.md5(json.dumps(config_key, sort_keys=True).encode()).hexdigest()[:8]
        
    def start_experiment(self, agent_config: Dict[str, Any], benchmark_config: Dict[str, Any]) -> str:
        """
        Start tracking a new experiment.
        
        Args:
            agent_config: Agent configuration dictionary
            benchmark_config: Benchmark configuration dictionary
            
        Returns:
            experiment_id: Unique identifier for this experiment
        """
        with self.lock:
            config_hash = self._generate_config_hash(agent_config, benchmark_config)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            experiment_id = f"{agent_config.get('name', 'unknown')}_{config_hash}_{timestamp}"
            
            self.current_experiment = ExperimentData(
                experiment_id=experiment_id,
                config_hash=config_hash,
                agent_name=agent_config.get("name", "unknown"),
                model_name=agent_config.get("model", {}).get("name", "unknown"),
                benchmark_name=benchmark_config.get("dataset", "unknown"),
                start_time=datetime.now().isoformat(),
            )
            
            print(f"📊 Started tracking experiment: {experiment_id}")
            return experiment_id
    
    def track_action(self, action: str, success: bool = True, error_message: str = None, step_number: int = None):
        """
        Track execution of an action.
        
        Args:
            action: The action string that was executed
            success: Whether the action was successful
            error_message: Error message if action failed
            step_number: Step number in the episode (optional)
        """
        if not self.current_experiment:
            return  # No active experiment
            
        with self.lock:
            # Extract action name from action string
            action_name = self._extract_action_name(action)
            
            # Initialize action stats if first time seeing this action
            if action_name not in self.current_experiment.actions:
                self.current_experiment.actions[action_name] = ActionStats(name=action_name)
            
            # Add the call to action stats
            full_error_msg = None
            if error_message:
                full_error_msg = f"Step {step_number}: {error_message}" if step_number else error_message
            
            self.current_experiment.actions[action_name].add_call(success, full_error_msg)
            
            # Track error patterns
            if not success and error_message:
                pattern = self._categorize_error(error_message)
                self.current_experiment.error_patterns[pattern] = \
                    self.current_experiment.error_patterns.get(pattern, 0) + 1
                    
            # Update total steps
            self.current_experiment.total_steps += 1
            
            # Log action for debugging
            status = "✅" if success else "❌"
            print(f"  {status} Step {step_number}: {action_name}" + 
                  (f" - {error_message}" if error_message else ""))
    
    def track_example_completion(self, success: bool):
        """
        Track completion of an example/episode.
        
        Args:
            success: Whether the example was completed successfully
        """
        if not self.current_experiment:
            return
            
        with self.lock:
            self.current_experiment.total_examples += 1
            if success:
                self.current_experiment.successful_examples += 1
                
            status = "🎯" if success else "💥"
            print(f"  {status} Example {self.current_experiment.total_examples} completed")
    
    def end_experiment(self) -> Optional[str]:
        """
        End the current experiment and save data to cache.
        
        Returns:
            experiment_id if successful, None otherwise
        """
        if not self.current_experiment:
            return None
            
        with self.lock:
            self.current_experiment.end_time = datetime.now().isoformat()
            
            # Convert to serializable format
            data_dict = self._experiment_to_dict(self.current_experiment)
            
            # Save to cache file
            cache_file = os.path.join(self.cache_dir, f"{self.current_experiment.experiment_id}.json")
            with open(cache_file, 'w') as f:
                json.dump(data_dict, f, indent=2)
            
            experiment_id = self.current_experiment.experiment_id
            print(f"💾 Saved experiment data: {cache_file}")
            
            # Print final summary
            self._print_experiment_summary()
            
            # Clear current experiment
            self.current_experiment = None
            
            return experiment_id
    
    def _experiment_to_dict(self, experiment: ExperimentData) -> Dict[str, Any]:
        """Convert ExperimentData to serializable dictionary."""
        return {
            "experiment_id": experiment.experiment_id,
            "config_hash": experiment.config_hash,
            "agent_name": experiment.agent_name,
            "model_name": experiment.model_name,
            "benchmark_name": experiment.benchmark_name,
            "start_time": experiment.start_time,
            "end_time": experiment.end_time,
            "total_examples": experiment.total_examples,
            "successful_examples": experiment.successful_examples,
            "total_steps": experiment.total_steps,
            "actions": {name: asdict(stats) for name, stats in experiment.actions.items()},
            "error_patterns": experiment.error_patterns,
        }
    
    def _print_experiment_summary(self):
        """Print a summary of the current experiment."""
        if not self.current_experiment:
            return
            
        exp = self.current_experiment
        success_rate = exp.successful_examples / max(exp.total_examples, 1)
        
        print(f"\n📈 Experiment Summary: {exp.experiment_id}")
        print(f"   Agent: {exp.agent_name} | Model: {exp.model_name} | Dataset: {exp.benchmark_name}")
        print(f"   Examples: {exp.successful_examples}/{exp.total_examples} ({success_rate:.1%} success)")
        print(f"   Total Steps: {exp.total_steps}")
        
        if exp.actions:
            print(f"   Actions Used: {len(exp.actions)}")
            # Show top 3 most used actions
            sorted_actions = sorted(exp.actions.items(), key=lambda x: x[1].total_calls, reverse=True)
            for name, stats in sorted_actions[:3]:
                error_rate = stats.failed_calls / max(stats.total_calls, 1)
                print(f"     • {name}: {stats.total_calls} calls ({error_rate:.1%} error rate)")
                
        if exp.error_patterns:
            print(f"   Top Errors: {dict(list(sorted(exp.error_patterns.items(), key=lambda x: x[1], reverse=True))[:3])}")
    
    def _extract_action_name(self, action: str) -> str:
        """Extract the action name from an action string."""
        action = action.strip()
        
        # Special cases
        if action.startswith('send_msg_to_user('):
            return 'send_msg_to_user'
        elif action.startswith('report_infeasible('):
            return 'report_infeasible'
        elif action.startswith('noop('):
            return 'noop'
        
        # Extract function name using regex
        match = re.match(r'^(\w+)\(', action)
        if match:
            return match.group(1)
        
        return 'unknown_action'
    
    def _categorize_error(self, error_message: str) -> str:
        """Categorize error message into common patterns."""
        if not error_message:
            return "unknown_error"
            
        error_lower = error_message.lower()
        
        if "timeout" in error_lower:
            return "timeout"
        elif "element not found" in error_lower or "no such element" in error_lower:
            return "element_not_found"
        elif "permission denied" in error_lower:
            return "permission_denied"
        elif "network" in error_lower or "connection" in error_lower:
            return "network_error"
        elif "parse" in error_lower or "syntax" in error_lower:
            return "parsing_error"
        elif "invalid" in error_lower:
            return "invalid_input"
        elif "infeasible" in error_lower:
            return "task_infeasible"
        else:
            return "other_error"
    
    def get_experiment_summary(self, experiment_id: str) -> Optional[Dict[str, Any]]:
        """
        Get summary statistics for a specific experiment.
        
        Args:
            experiment_id: ID of the experiment to analyze
            
        Returns:
            Dictionary with summary statistics or None if not found
        """
        cache_file = os.path.join(self.cache_dir, f"{experiment_id}.json")
        if not os.path.exists(cache_file):
            return None
            
        with open(cache_file, 'r') as f:
            data = json.load(f)
        
        # Calculate derived statistics
        success_rate = data["successful_examples"] / max(data["total_examples"], 1)
        
        # Calculate overall error rate
        total_calls = sum(action["total_calls"] for action in data["actions"].values())
        total_errors = sum(action["failed_calls"] for action in data["actions"].values())
        error_rate = total_errors / max(total_calls, 1)
        
        # Get most used actions
        most_used = sorted(data["actions"].items(), key=lambda x: x[1]["total_calls"], reverse=True)[:5]
        
        return {
            "experiment_id": experiment_id,
            "agent_name": data["agent_name"],
            "model_name": data["model_name"],
            "benchmark_name": data["benchmark_name"],
            "duration_minutes": self._calculate_duration(data["start_time"], data.get("end_time")),
            "success_rate": success_rate,
            "error_rate": error_rate,
            "total_examples": data["total_examples"],
            "total_steps": data["total_steps"],
            "total_actions_used": len(data["actions"]),
            "most_used_actions": [{"name": name, "calls": stats["total_calls"]} for name, stats in most_used],
            "top_error_patterns": dict(sorted(data["error_patterns"].items(), key=lambda x: x[1], reverse=True)[:5]),
        }
    
    def _calculate_duration(self, start_time: str, end_time: Optional[str]) -> float:
        """Calculate experiment duration in minutes."""
        start = datetime.fromisoformat(start_time)
        end = datetime.fromisoformat(end_time) if end_time else datetime.now()
        return (end - start).total_seconds() / 60.0
    
    def list_experiments(self, config_hash: Optional[str] = None) -> List[str]:
        """
        List cached experiments, optionally filtered by config hash.
        
        Args:
            config_hash: If provided, only return experiments with this config hash
            
        Returns:
            List of experiment IDs
        """
        experiment_files = [f for f in os.listdir(self.cache_dir) if f.endswith('.json')]
        experiment_ids = [f[:-5] for f in experiment_files]
        
        if config_hash:
            # Filter by config hash
            filtered_ids = []
            for exp_id in experiment_ids:
                if f"_{config_hash}_" in exp_id:
                    filtered_ids.append(exp_id)
            return filtered_ids
        
        return sorted(experiment_ids)
    
    def compare_experiments(self, experiment_ids: List[str]) -> Dict[str, Any]:
        """
        Compare multiple experiments and return comparison statistics.
        
        Args:
            experiment_ids: List of experiment IDs to compare
            
        Returns:
            Dictionary with comparison data
        """
        experiments = []
        for exp_id in experiment_ids:
            summary = self.get_experiment_summary(exp_id)
            if summary:
                experiments.append(summary)
        
        if not experiments:
            return {}
        
        comparison = {
            "experiments": experiments,
            "best_success_rate": max(exp["success_rate"] for exp in experiments),
            "worst_success_rate": min(exp["success_rate"] for exp in experiments),
            "average_success_rate": sum(exp["success_rate"] for exp in experiments) / len(experiments),
            "best_error_rate": min(exp["error_rate"] for exp in experiments),
            "worst_error_rate": max(exp["error_rate"] for exp in experiments),
            "average_error_rate": sum(exp["error_rate"] for exp in experiments) / len(experiments),
        }
        
        return comparison


# Global tracker instance
_global_tracker: Optional[ActionTracker] = None

def get_tracker() -> ActionTracker:
    """Get the global action tracker instance."""
    global _global_tracker
    if _global_tracker is None:
        _global_tracker = ActionTracker()
    return _global_tracker

# Convenience functions for the global tracker
def start_tracking(agent_config: Dict[str, Any], benchmark_config: Dict[str, Any]) -> str:
    """Start tracking a new experiment."""
    return get_tracker().start_experiment(agent_config, benchmark_config)

def track_action(action: str, success: bool = True, error_message: str = None, step_number: int = None):
    """Track an action execution."""
    get_tracker().track_action(action, success, error_message, step_number)

def track_completion(success: bool):
    """Track example completion."""
    get_tracker().track_example_completion(success)

def end_tracking() -> Optional[str]:
    """End current experiment tracking."""
    return get_tracker().end_experiment()

def get_summary(experiment_id: str) -> Optional[Dict[str, Any]]:
    """Get experiment summary."""
    return get_tracker().get_experiment_summary(experiment_id)

def list_experiments(config_hash: Optional[str] = None) -> List[str]:
    """List cached experiments."""
    return get_tracker().list_experiments(config_hash)

def compare_experiments(experiment_ids: List[str]) -> Dict[str, Any]:
    """Compare multiple experiments."""
    return get_tracker().compare_experiments(experiment_ids) 