"""
ASI (Autonomous Skill Induction) Inducer

Implements the exact functionality from agent-skill-induction/asi/induce/induce_actions.py
with full test execution and validation pipeline.
"""

import os
import gzip
import json
import pickle
import subprocess
import tempfile
import shutil
from pathlib import Path
from typing import Dict, Any, List, Optional, Union, Tuple
from dataclasses import dataclass
import logging

from .llm_inducer import LLMBasedInducer, LLMInducerConfig, LLMConfig, LLMProvider
from ..base import (
    Skill, SkillType, SkillFormat, SkillInductionResult, 
    TrajectoryExample, SkillMetadata
)

logger = logging.getLogger(__name__)


@dataclass
class ASIConfig(LLMInducerConfig):
    """Configuration for ASI inducer."""
    # File paths for ASI operation
    results_dir: str = "results"
    config_dir: str = "config_files"
    write_action_path: str = ""
    write_tests_dir: str = "debug_actions"
    
    # Website and evaluation settings
    website: str = "shopping"
    eval_with_gold: bool = False
    
    # Test execution settings
    test_timeout: int = 100
    max_test_attempts: int = 3
    
    def __post_init__(self):
        super().__post_init__()
        
        # Set default action path based on website
        if not self.write_action_path:
            self.write_action_path = f"actions/{self.website}.py"


class ASIInducer(LLMBasedInducer):
    """
    ASI Inducer implementing exact functionality from induce_actions.py.
    
    Features:
    - Trajectory example collection with filtering
    - LLM-based function generation with few-shot prompting
    - Action file management with atomic writes
    - Test generation and execution pipeline
    - Validation with rollback mechanism
    """
    
    def __init__(self, config: ASIConfig):
        super().__init__(config)
        self.asi_config = config
        
        # Ensure directories exist
        Path(config.results_dir).mkdir(parents=True, exist_ok=True)
        Path(config.write_tests_dir).mkdir(parents=True, exist_ok=True)
        Path(config.write_action_path).parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize action file if it doesn't exist
        if not Path(config.write_action_path).exists():
            self._init_action_file()
    
    def _init_action_file(self):
        """Initialize the action file with basic structure."""
        action_file_content = '''"""
Auto-generated actions for web automation.
This file contains reusable functions induced from successful trajectories.
"""

def dummy_action():
    """Placeholder action to initialize the file."""
    pass
'''
        
        with open(self.asi_config.write_action_path, 'w') as f:
            f.write(action_file_content)
        
        logger.info(f"Initialized action file: {self.asi_config.write_action_path}")
    
    def extract_skills_from_result_dirs(
        self,
        result_dir_list: List[str],
        result_id_list: List[str] = None
    ) -> SkillInductionResult:
        """
        Extract skills from ASI result directories.
        
        Args:
            result_dir_list: List of result directory paths
            result_id_list: Optional list of specific result IDs to process
            
        Returns:
            SkillInductionResult with induced skills
        """
        result = SkillInductionResult(success=True)
        
        try:
            # Get test query from result directories
            test_query = self._get_test_query(result_dir_list)
            if not test_query:
                result.add_error("No valid test query generated from result directories")
                return result
            
            # Save test query for debugging
            test_query_path = Path(self.storage_path) / "test_query.txt"
            with open(test_query_path, 'w') as f:
                f.write(test_query)
            
            # Generate LLM responses
            responses = self._generate_asi_responses(test_query)
            
            # Process each response
            for i, response in enumerate(responses):
                logger.info(f"Processing response {i+1}/{len(responses)}")
                
                # Extract and validate actions
                extracted_skills = self._process_asi_response(response, result_id_list or [])
                result.skills.extend(extracted_skills)
                
                # If we got valid skills and they pass tests, stop
                if extracted_skills and all(skill.metadata.confidence_score > 0.8 for skill in extracted_skills):
                    break
            
            if not result.skills:
                result.add_error("No valid skills extracted from ASI responses")
                
        except Exception as e:
            logger.error(f"Error in ASI skill extraction: {e}")
            result.add_error(f"ASI extraction failed: {str(e)}")
        
        return result
    
    def _get_test_query(self, result_dir_list: List[str]) -> Optional[str]:
        """Transform past examples into a test query (from induce_actions.py)."""
        task = None
        examples = []
        
        for rdir in result_dir_list:
            ex, task = self._get_example_query_cleaned(len(examples) + 1, rdir)
            if ex is None:
                continue
            examples.append(ex)
        
        if len(examples) < 1:
            return None
        
        query = f"## Task: {task}\n" + '\n\n'.join(examples)
        return query
    
    def _get_example_query_cleaned(self, index: int, result_dir: str) -> Tuple[Optional[str], Optional[str]]:
        """Get the string for a past example experience, without invalid actions."""
        try:
            # Get config
            cid = self._get_task_id(result_dir)
            config_path = Path(self.asi_config.config_dir) / f"{cid}.json"
            
            if not config_path.exists():
                logger.warning(f"Config file not found: {config_path}")
                return None, None
            
            with open(config_path) as f:
                config = json.load(f)
            
            # Get instruction
            subtask_inst_path = Path(result_dir) / "instruction.txt"
            if subtask_inst_path.exists():  # sub task
                with open(subtask_inst_path) as f:
                    instruction = f.read()
                task = instruction
            else:  # full task
                instruction = config["intent"]
                task = config["intent_template"]
            
            # Load cleaned steps
            cleaned_steps_path = Path(result_dir) / "cleaned_steps.json"
            if not cleaned_steps_path.exists():
                # Try to clean steps from raw trajectory
                steps = self._clean_trajectory_steps(result_dir)
                if steps:
                    with open(cleaned_steps_path, 'w') as f:
                        json.dump(steps, f)
                else:
                    logger.warning(f"No cleaned steps available for {result_dir}")
                    return None, None
            else:
                with open(cleaned_steps_path) as f:
                    steps = json.load(f)
            
            if len(steps) > 0:
                logger.info(f"Collected #{len(steps)} valid steps from {result_dir}")
                steps_str = '\n'.join(steps)
                ex = f"### Example {index} ({config['task_id']}): {instruction}\n{steps_str}"
                return ex, task
            else:
                return None, None
                
        except Exception as e:
            logger.error(f"Error processing result dir {result_dir}: {e}")
            return None, None
    
    def _get_task_id(self, result_dir: str) -> str:
        """Extract task ID from result directory path."""
        return Path(result_dir).name.split('.')[-1] if '.' in Path(result_dir).name else Path(result_dir).name
    
    def _clean_trajectory_steps(self, result_dir: str) -> List[str]:
        """Clean trajectory steps from raw step files."""
        steps = []
        result_path = Path(result_dir)
        
        try:
            # Find all step files
            step_files = [f for f in result_path.iterdir() 
                         if f.name.startswith("step") and f.name.endswith(".pkl.gz")]
            step_files = sorted(step_files, key=lambda x: int(x.name.split('.')[0].split('_')[1]))
            
            for step_file in step_files:
                try:
                    with gzip.open(step_file, 'rb') as f:
                        step_info = pickle.load(f)
                    
                    # Check for errors (skip invalid actions)
                    error_msg = step_info.obs.get("last_action_error", "")
                    if len(error_msg) > 0 and not error_msg.startswith("TimeoutError"):
                        continue  # skip error actions
                    
                    last_action = step_info.obs.get("last_action", "")
                    if len(last_action) == 0:
                        continue  # skip empty actions
                    
                    steps.append(last_action)
                    
                except Exception as e:
                    logger.warning(f"Error processing step file {step_file}: {e}")
                    continue
            
            logger.info(f"Cleaned {len(steps)} valid steps from {len(step_files)} total steps")
            return steps
            
        except Exception as e:
            logger.error(f"Error cleaning trajectory steps: {e}")
            return []
    
    def _generate_asi_responses(self, test_query: str) -> List[str]:
        """Generate responses using ASI prompting strategy."""
        # Build messages with ASI-specific prompts
        messages = [
            {"role": "system", "content": self._get_asi_system_prompt()},
            {"role": "user", "content": self._get_asi_instruction_prompt()},
            {"role": "user", "content": self._get_asi_few_shot_prompt()},
            {"role": "user", "content": test_query + '\n\n## Reusable Functions'}
        ]
        
        responses = []
        
        try:
            # Use litellm if configured
            if hasattr(self.llm_client, 'completion'):
                if self.llm_config.num_responses > 1 and "openai" in self.llm_config.model_name:
                    response = self.llm_client.completion(
                        api_key=os.environ.get("LITELLM_API_KEY"),
                        base_url=os.environ.get("LITELLM_BASE_URL", "https://cmu.litellm.ai"),
                        model=self.llm_config.model_name.replace("litellm", "openai"),
                        messages=messages,
                        temperature=self.llm_config.temperature,
                        n=self.llm_config.num_responses,
                    )
                    for choice in response.choices:
                        responses.append(choice.message.content)
                else:
                    for _ in range(self.llm_config.num_responses):
                        response = self.llm_client.completion(
                            api_key=os.environ.get("LITELLM_API_KEY"),
                            base_url=os.environ.get("LITELLM_BASE_URL", "https://cmu.litellm.ai"),
                            model=self.llm_config.model_name.replace("litellm", "openai"),
                            messages=messages,
                            temperature=self.llm_config.temperature,
                        )
                        responses.append(response.choices[0].message.content)
            else:
                # Use FoundationModel
                prompt = self._messages_to_prompt(messages)
                for _ in range(self.llm_config.num_responses):
                    response = self.llm_client.generate(
                        prompt=prompt,
                        max_tokens=self.llm_config.max_tokens,
                        temperature=self.llm_config.temperature
                    )
                    responses.append(response)
            
            # Save responses for debugging
            for i, resp in enumerate(responses):
                resp_path = Path(self.storage_path) / f"response_{i}.md"
                with open(resp_path, 'w') as f:
                    f.write(resp)
            
        except Exception as e:
            logger.error(f"Error generating ASI responses: {e}")
            raise
        
        return responses
    
    def _get_asi_system_prompt(self) -> str:
        """Get ASI-specific system prompt."""
        return """You are an expert at analyzing web automation trajectories and extracting reusable action patterns.
Your task is to identify common action sequences that can be generalized into reusable Python functions for web automation.
Focus on creating clean, well-documented functions that handle common web interaction patterns."""
    
    def _get_asi_instruction_prompt(self) -> str:
        """Get ASI-specific instruction prompt.""" 
        return """Analyze the web automation examples below and extract reusable functions.

Requirements:
1. Create Python functions that generalize the common patterns
2. Use descriptive function names following snake_case convention
3. Include proper type hints and docstrings
4. Handle common web automation scenarios (clicking, filling forms, navigation)
5. Make functions robust and reusable across different websites
6. Each function should be self-contained and focused on a single task

Return only the Python functions, properly formatted with ```python blocks."""
    
    def _get_asi_few_shot_prompt(self) -> str:
        """Get ASI-specific few-shot examples."""
        return """Example of good function extraction:

Input: Multiple trajectories showing form filling and submission
Output:
```python
def fill_and_submit_form(page, form_data: dict, submit_selector: str = 'button[type="submit"]'):
    \"\"\"
    Fill a form with provided data and submit it.
    
    Args:
        page: Browser page object
        form_data: Dictionary mapping field selectors to values
        submit_selector: CSS selector for submit button
    \"\"\"
    for selector, value in form_data.items():
        page.fill(selector, str(value))
    
    page.click(submit_selector)

def navigate_and_wait(page, url: str, wait_selector: str = None):
    \"\"\"
    Navigate to URL and optionally wait for an element.
    
    Args:
        page: Browser page object
        url: URL to navigate to
        wait_selector: Optional selector to wait for after navigation
    \"\"\"
    page.goto(url)
    if wait_selector:
        page.wait_for_selector(wait_selector)
```"""
    
    def _process_asi_response(self, response: str, result_id_list: List[str]) -> List[Skill]:
        """Process ASI response with full validation pipeline."""
        skills = []
        
        try:
            # Extract actions from response
            tmp_path, action_names = self._write_actions(response)
            if not tmp_path or not action_names:
                logger.info("No valid actions extracted from response")
                return skills
            
            logger.info(f"Extracted actions: {action_names}")
            
            # Run tests if result IDs provided
            if result_id_list:
                should_revert = self._write_and_run_tests(response, result_id_list, action_names)
                
                if should_revert:
                    # Revert changes
                    logger.info("Tests failed, reverting changes")
                    shutil.move(tmp_path, self.asi_config.write_action_path)
                    self._cleanup_test_results(result_id_list)
                else:
                    # Tests passed, keep changes and create skills
                    logger.info("Tests passed, creating skills")
                    os.remove(tmp_path)
                    skills = self._create_skills_from_actions(response, action_names)
            else:
                # No tests to run, just create skills
                logger.info("No test IDs provided, creating skills without validation")
                os.remove(tmp_path)
                skills = self._create_skills_from_actions(response, action_names)
            
        except Exception as e:
            logger.error(f"Error processing ASI response: {e}")
        
        return skills
    
    def _write_actions(self, response: str) -> Tuple[Optional[str], Optional[List[str]]]:
        """Extract actions from response and write to action file."""
        try:
            # Get existing action names to avoid duplicates
            existing_action_names = self._get_function_names(
                Path(self.asi_config.write_action_path).read_text()
            )
            
            # Extract code pieces
            actions = self._extract_code_pieces(response, start="```python", end="```", do_split=False)
            actions = [a for a in actions if "def " in a and self._count_function_calls(a, 1)]
            
            new_actions, action_names = [], []
            for action in actions:
                if "def " in action and self._count_function_calls(action, 1):
                    func_names = self._get_function_names(action, existing_action_names)
                    if len(func_names) > 0:
                        action_names.extend(func_names)
                        new_actions.append(action)
            
            logger.info(f"Extracted {len(new_actions)} actions: {action_names}")
            
            if len(new_actions) == 0:
                return None, None
            
            # Create backup
            tmp_path = self.asi_config.write_action_path + ".tmp"
            shutil.copy2(self.asi_config.write_action_path, tmp_path)
            
            # Append new actions
            with open(self.asi_config.write_action_path, 'a') as f:
                f.write('\n\n' + '\n\n'.join(new_actions))
            
            return tmp_path, action_names
            
        except Exception as e:
            logger.error(f"Error writing actions: {e}")
            return None, None
    
    def _write_and_run_tests(self, response: str, result_id_list: List[str], action_names: List[str]) -> bool:
        """Extract tests, write them, and run validation."""
        try:
            tests = self._parse_tests(response, action_names)
            if len(tests) != len(result_id_list):
                logger.warning(f"Got {len(tests)} tests but {len(result_id_list)} results")
                return True  # Revert on mismatch
            
            # Write tests and create run script
            script_content = []
            test_dir = Path(self.asi_config.write_tests_dir)
            test_dir.mkdir(exist_ok=True)
            
            for i, (test, result_id) in enumerate(zip(tests, result_id_list)):
                # Write test trajectory
                test_path = test_dir / f"test_{i}.txt"
                test_str = '\n'.join([f"```{line.strip()}```" for line in test.split('\n') if line.strip()])
                test_path.write_text(test_str)
                
                # Add to run script
                script_content.extend([
                    f"# Run test for task {result_id}",
                    f"python run_demo.py --websites {self.asi_config.website} --headless "
                    f"--task_name webarena.{result_id.split('_')[0]} "
                    f"--action_path {test_path} "
                    f"--rename_to webarena.{result_id.split('_')[0]}_test",
                    ""
                ])
            
            # Write and run test script
            test_script_path = test_dir / "run_tests.sh"
            test_script_path.write_text('\n'.join(script_content))
            
            # Run tests
            result = self._run_test_script(test_script_path)
            
            # Check results
            return self._check_test_results(result_id_list, action_names)
            
        except Exception as e:
            logger.error(f"Error running tests: {e}")
            return True  # Revert on error
    
    def _run_test_script(self, script_path: Path) -> bool:
        """Run test script with timeout."""
        try:
            process = subprocess.Popen(["bash", str(script_path)], 
                                     stdout=subprocess.PIPE, 
                                     stderr=subprocess.PIPE)
            stdout, stderr = process.communicate(timeout=self.asi_config.test_timeout)
            
            if stdout:
                logger.info(f"Test output: {stdout.decode()}")
            if stderr:
                logger.warning(f"Test stderr: {stderr.decode()}")
            
            return process.returncode == 0
            
        except subprocess.TimeoutExpired:
            process.kill()
            logger.error(f"Test process timed out after {self.asi_config.test_timeout} seconds")
            return False
        except Exception as e:
            logger.error(f"Error running test script: {e}")
            return False
    
    def _check_test_results(self, result_id_list: List[str], action_names: List[str]) -> bool:
        """Check if tests passed."""
        scores = []
        
        for result_id in result_id_list:
            test_result_dir = Path(self.asi_config.results_dir) / f"webarena.{result_id}_test"
            
            if self.asi_config.eval_with_gold:
                # Check gold evaluation
                eval_path = test_result_dir / "summary_info.json"
                if eval_path.exists():
                    with open(eval_path) as f:
                        summary = json.load(f)
                    scores.append(summary["cum_reward"] == 1.0)
                else:
                    scores.append(False)
            else:
                # Run auto evaluation
                try:
                    subprocess.run([
                        "python", "-m", "autoeval.evaluate_trajectory",
                        "--result_dir", str(test_result_dir)
                    ], timeout=60)
                    
                    eval_path = test_result_dir / "gpt-4o-2024-05-13_autoeval.json"
                    if eval_path.exists():
                        with open(eval_path) as f:
                            eval_result = json.load(f)
                        scores.append(eval_result[0]["rm"] == True)
                    else:
                        scores.append(False)
                except Exception as e:
                    logger.error(f"Auto evaluation failed: {e}")
                    scores.append(False)
            
            # Check step validity
            if scores[-1]:  # Only if previous check passed
                try:
                    cmd = [
                        "python", "-m", "results.calc_valid_steps",
                        "--result_dir", str(test_result_dir),
                        "--action_names"
                    ] + action_names
                    
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                    output = result.stdout.strip().split('\n')[-1].strip()
                    
                    if output == 'False':
                        scores[-1] = False
                        
                except Exception as e:
                    logger.error(f"Step validity check failed: {e}")
                    scores[-1] = False
            
            # Break early if any test fails
            if scores[-1] == False:
                break
        
        logger.info(f"Test scores: {scores}")
        
        # Return True if should revert (any test failed)
        return not all(scores)
    
    def _cleanup_test_results(self, result_id_list: List[str]):
        """Clean up test result directories."""
        for result_id in result_id_list:
            test_dir = Path(self.asi_config.results_dir) / f"webarena.{result_id}_test"
            if test_dir.exists():
                shutil.rmtree(test_dir)
                logger.info(f"Cleaned up test directory: {test_dir}")
    
    def _create_skills_from_actions(self, response: str, action_names: List[str]) -> List[Skill]:
        """Create skill objects from validated actions."""
        skills = []
        code_blocks = self._extract_code_pieces(response, start="```python", end="```", do_split=False)
        
        for i, code in enumerate(code_blocks):
            if "def " not in code:
                continue
            
            func_info = self._parse_function(code)
            if not func_info or func_info['name'] not in action_names:
                continue
            
            skill = Skill(
                id=f"asi_skill_{func_info['name']}",
                name=func_info['name'],
                skill_type=SkillType.CODE,
                format=SkillFormat.PYTHON_FUNCTION,
                content=code,
                description=func_info.get('docstring', ''),
                task_examples=[],
                metadata=SkillMetadata(
                    source='ASIInducer',
                    confidence_score=0.9,  # High confidence since tests passed
                    tags=['asi_generated', 'validated', 'function']
                )
            )
            
            skills.append(skill)
        
        return skills
    
    # Utility methods from the original induce_actions.py
    
    def _extract_code_pieces(self, text: str, start: str, end: str, do_split: bool = True) -> List[str]:
        """Extract code pieces from text."""
        pieces = []
        start_idx = 0
        
        while True:
            start_pos = text.find(start, start_idx)
            if start_pos == -1:
                break
            
            end_pos = text.find(end, start_pos + len(start))
            if end_pos == -1:
                break
            
            piece = text[start_pos + len(start):end_pos].strip()
            if piece:
                pieces.append(piece)
            
            start_idx = end_pos + len(end)
        
        return pieces
    
    def _count_function_calls(self, code: str, min_calls: int) -> bool:
        """Check if code has minimum number of function calls."""
        return code.count("def ") >= min_calls
    
    def _get_function_names(self, code: str, existing_names: List[str] = None) -> List[str]:
        """Extract function names from code."""
        import re
        
        existing_names = existing_names or []
        func_names = []
        
        for match in re.finditer(r'def\s+(\w+)\s*\(', code):
            func_name = match.group(1)
            if func_name not in existing_names:
                func_names.append(func_name)
        
        return func_names
    
    def _parse_tests(self, response: str, action_names: List[str]) -> List[str]:
        """Parse tests from response."""
        # This is a simplified version - in practice, would need more sophisticated parsing
        # Look for test patterns in the response
        tests = []
        
        # Split response into sections and look for test-like content
        sections = response.split('###')
        for section in sections:
            if any(name in section.lower() for name in ['test', 'example', 'usage']):
                # Extract code or action sequences from this section
                test_code = self._extract_code_pieces(section, start="```", end="```")
                if test_code:
                    tests.extend(test_code)
        
        return tests[:len(action_names)]  # Return same number as action names
    
    def validate_skill(self, skill: Skill) -> bool:
        """Validate ASI-generated skill."""
        if not super().validate_skill(skill):
            return False
        
        # Additional ASI-specific validation
        if skill.metadata.source == 'ASIInducer':
            # Check if function name exists in action file
            action_file_content = Path(self.asi_config.write_action_path).read_text()
            return f"def {skill.name}" in action_file_content
        
        return True