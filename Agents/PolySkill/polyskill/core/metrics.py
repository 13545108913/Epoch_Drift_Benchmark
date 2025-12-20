"""
Evaluation Metrics for PolySkill

This module implements the metrics described in Appendix C.1 of the paper:
- Task Success Rate (SR)
- Number of Steps
- Skill Reusability
- Skill Adoption Rate (Task Coverage)
- Skill Compositionality
"""

from typing import List, Dict, Set, Any
from dataclasses import dataclass
import numpy as np


@dataclass
class EvaluationMetrics:
    """Container for all evaluation metrics"""

    # Primary metrics
    task_success_rate: float
    num_steps_avg: float

    # Skill usage metrics
    skill_reusability: float
    skill_adoption_rate: float
    skill_compositionality: float

    # Raw counts for reference
    total_tasks: int
    successful_tasks: int
    total_skills: int
    reused_skills: int
    tasks_with_skills: int

    def __repr__(self):
        return f"""
╔═══════════════════════════════════════════════════════╗
║              PolySkill Evaluation Metrics             ║
╠═══════════════════════════════════════════════════════╣
║ Task Success Rate:      {self.task_success_rate:>6.1%} ({self.successful_tasks}/{self.total_tasks})      ║
║ Avg Steps per Task:     {self.num_steps_avg:>6.2f}                     ║
╠═══════════════════════════════════════════════════════╣
║ Skill Reusability:      {self.skill_reusability:>6.1%} ({self.reused_skills}/{self.total_skills})      ║
║ Task Coverage:          {self.skill_adoption_rate:>6.1%} ({self.tasks_with_skills}/{self.total_tasks})      ║
║ Skill Compositionality: {self.skill_compositionality:>6.2f}                     ║
╚═══════════════════════════════════════════════════════╝
        """.strip()


class MetricsCalculator:
    """
    Calculates evaluation metrics for PolySkill experiments.

    Implements the formal definitions from Appendix C.1 of the paper.
    """

    def __init__(self):
        self.trajectories = []
        self.skills_library = {}
        self.skill_creation_order = []

    def add_trajectory(self, trajectory: Dict[str, Any]):
        """
        Add a completed trajectory for metrics calculation.

        Args:
            trajectory: Dict containing:
                - 'success': bool, whether task succeeded
                - 'actions': List[str], sequence of actions
                - 'skills_used': List[str], skills invoked in this trajectory
                - 'num_steps': int, total number of steps
        """
        self.trajectories.append(trajectory)

    def add_skill(self, skill_name: str, skill_body: List[str]):
        """
        Add a learned skill to the library.

        Args:
            skill_name: Unique identifier for the skill
            skill_body: List of action/skill names that comprise this skill
        """
        self.skills_library[skill_name] = skill_body
        self.skill_creation_order.append(skill_name)

    def calculate_task_success_rate(self) -> tuple[float, int, int]:
        """
        Calculate Task Success Rate (SR).

        SR = (1/|T_test|) * Σ I(task T_j is successful)

        Returns:
            (success_rate, num_successful, num_total)
        """
        if not self.trajectories:
            return 0.0, 0, 0

        successful = sum(1 for t in self.trajectories if t.get('success', False))
        total = len(self.trajectories)

        return successful / total, successful, total

    def calculate_avg_steps(self) -> float:
        """
        Calculate average Number of Steps.

        Number of Steps = (1/|D_success|) * Σ |τ|

        Only calculated over successful trajectories.

        Returns:
            Average number of steps per successful task
        """
        successful_trajectories = [
            t for t in self.trajectories if t.get('success', False)
        ]

        if not successful_trajectories:
            return 0.0

        total_steps = sum(t.get('num_steps', 0) for t in successful_trajectories)
        return total_steps / len(successful_trajectories)

    def calculate_skill_reusability(self) -> tuple[float, int, int]:
        """
        Calculate Skill Reusability.

        Skill Reusability = |{k ∈ K | ∃τ ∈ D_test, k ∈ τ}| / |K|

        Measures the fraction of learned skills that were used at least once.

        Returns:
            (reusability_rate, num_reused_skills, total_skills)
        """
        if not self.skills_library:
            return 0.0, 0, 0

        # Collect all skills used across all test trajectories
        used_skills = set()
        for trajectory in self.trajectories:
            skills_in_traj = trajectory.get('skills_used', [])
            used_skills.update(skills_in_traj)

        num_reused = len(used_skills)
        total_skills = len(self.skills_library)

        reusability = num_reused / total_skills if total_skills > 0 else 0.0

        return reusability, num_reused, total_skills

    def calculate_skill_adoption_rate(self) -> tuple[float, int, int]:
        """
        Calculate Skill Adoption Rate (also called Task Coverage in the paper).

        Skill Adoption Rate = |{τ ∈ D_test | ∃k ∈ K, k ∈ τ}| / |D_test|

        Measures the fraction of trajectories that used at least one skill.

        Returns:
            (adoption_rate, num_tasks_with_skills, total_tasks)
        """
        if not self.trajectories:
            return 0.0, 0, 0

        tasks_with_skills = sum(
            1 for t in self.trajectories
            if t.get('skills_used', [])
        )
        total_tasks = len(self.trajectories)

        adoption_rate = tasks_with_skills / total_tasks if total_tasks > 0 else 0.0

        return adoption_rate, tasks_with_skills, total_tasks

    def calculate_skill_compositionality(self) -> float:
        """
        Calculate Skill Compositionality.

        Skill Compositionality = (1/N) * Σ |{k_j ∈ body(k_i) | j < i}|

        Measures how often new skills reuse previously learned skills.

        Returns:
            Average number of previously learned skills reused per new skill
        """
        if not self.skill_creation_order:
            return 0.0

        total_reuse = 0
        N = len(self.skill_creation_order)

        for i, skill_name in enumerate(self.skill_creation_order):
            skill_body = self.skills_library.get(skill_name, [])

            # Count how many actions in this skill's body are previously learned skills
            previously_learned = set(self.skill_creation_order[:i])
            reused_count = sum(1 for action in skill_body if action in previously_learned)

            total_reuse += reused_count

        return total_reuse / N if N > 0 else 0.0

    def calculate_all_metrics(self) -> EvaluationMetrics:
        """
        Calculate all evaluation metrics.

        Returns:
            EvaluationMetrics object containing all computed metrics
        """
        # Task success metrics
        sr, num_successful, num_total = self.calculate_task_success_rate()
        avg_steps = self.calculate_avg_steps()

        # Skill usage metrics
        reusability, num_reused, total_skills = self.calculate_skill_reusability()
        adoption, tasks_with_skills, _ = self.calculate_skill_adoption_rate()
        compositionality = self.calculate_skill_compositionality()

        return EvaluationMetrics(
            task_success_rate=sr,
            num_steps_avg=avg_steps,
            skill_reusability=reusability,
            skill_adoption_rate=adoption,
            skill_compositionality=compositionality,
            total_tasks=num_total,
            successful_tasks=num_successful,
            total_skills=total_skills,
            reused_skills=num_reused,
            tasks_with_skills=tasks_with_skills,
        )

    def print_comparison(self, baseline_metrics: EvaluationMetrics, method_name: str = "PolySkill"):
        """
        Print a comparison table between baseline and our method.

        Args:
            baseline_metrics: Metrics from baseline method
            method_name: Name of our method
        """
        current = self.calculate_all_metrics()

        def format_delta(current_val, baseline_val, is_percentage=True):
            delta = current_val - baseline_val
            if is_percentage:
                sign = "+" if delta > 0 else ""
                return f"{sign}{delta:.1%}"
            else:
                sign = "+" if delta > 0 else ""
                return f"{sign}{delta:.2f}"

        print(f"""
╔════════════════════════════════════════════════════════════════╗
║              Method Comparison: {method_name:^20}              ║
╠════════════════════════════════════════════════════════════════╣
║ Metric                 │ Baseline │ {method_name:^12} │ Delta    ║
╠════════════════════════════════════════════════════════════════╣
║ Task Success Rate      │  {baseline_metrics.task_success_rate:>5.1%}   │   {current.task_success_rate:>5.1%}   │ {format_delta(current.task_success_rate, baseline_metrics.task_success_rate):>7} ║
║ Avg Steps              │  {baseline_metrics.num_steps_avg:>5.2f}   │   {current.num_steps_avg:>5.2f}   │ {format_delta(current.num_steps_avg, baseline_metrics.num_steps_avg, False):>7} ║
╠════════════════════════════════════════════════════════════════╣
║ Skill Reusability      │  {baseline_metrics.skill_reusability:>5.1%}   │   {current.skill_reusability:>5.1%}   │ {format_delta(current.skill_reusability, baseline_metrics.skill_reusability):>7} ║
║ Task Coverage          │  {baseline_metrics.skill_adoption_rate:>5.1%}   │   {current.skill_adoption_rate:>5.1%}   │ {format_delta(current.skill_adoption_rate, baseline_metrics.skill_adoption_rate):>7} ║
║ Skill Compositionality │  {baseline_metrics.skill_compositionality:>5.2f}   │   {current.skill_compositionality:>5.2f}   │ {format_delta(current.skill_compositionality, baseline_metrics.skill_compositionality, False):>7} ║
╚════════════════════════════════════════════════════════════════╝
        """.strip())


# Example usage
if __name__ == "__main__":
    # Example: Calculate metrics for a simple experiment
    calculator = MetricsCalculator()

    # Add some example trajectories
    calculator.add_trajectory({
        'success': True,
        'num_steps': 5,
        'skills_used': ['search_product', 'add_to_cart']
    })
    calculator.add_trajectory({
        'success': True,
        'num_steps': 3,
        'skills_used': ['search_product']
    })
    calculator.add_trajectory({
        'success': False,
        'num_steps': 10,
        'skills_used': []
    })

    # Add some skills
    calculator.add_skill('search_product', ['click', 'type', 'enter'])
    calculator.add_skill('add_to_cart', ['click', 'search_product'])  # Compositional!
    calculator.add_skill('checkout', ['click', 'confirm'])

    # Calculate and print metrics
    metrics = calculator.calculate_all_metrics()
    print(metrics)
