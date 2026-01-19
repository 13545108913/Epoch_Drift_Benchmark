"""
LLM-Based Skill Inducer

Base class for LLM-powered skill induction with prompt management and response processing.
"""

import os
import json
import logging
from typing import Dict, Any, List, Optional, Union, Tuple
from dataclasses import dataclass
from enum import Enum
import re

from ..base import (
    BaseSkillInducer, InducerConfig, Skill, SkillType, 
    SkillFormat, SkillInductionResult, TrajectoryExample, SkillMetadata
)

logger = logging.getLogger(__name__)


class LLMProvider(Enum):
    """Supported LLM providers."""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"


@dataclass
class LLMConfig:
    """Configuration for LLM-based induction."""
    provider: LLMProvider = LLMProvider.ANTHROPIC
    model_name: str = "claude-3-5-sonnet-20241022"
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 4000
    num_responses: int = 1
    timeout: int = 120


@dataclass
class LLMInducerConfig(InducerConfig):
    """Configuration for LLM-based skill inducer."""
    llm_config: LLMConfig = None
    system_prompt_path: str = ""
    instruction_prompt_path: str = ""
    few_shot_prompt_path: str = ""
    max_examples_per_prompt: int = 5
    
    def __post_init__(self):
        if self.llm_config is None:
            self.llm_config = LLMConfig()


class LLMBasedInducer(BaseSkillInducer):
    """
    Base class for LLM-powered skill induction.
    
    Provides:
    - LLM integration
    - Prompt management
    - Response processing
    - Code extraction utilities
    """
    
    def __init__(self, config: LLMInducerConfig):
        super().__init__(config)
        self.llm_config = config.llm_config
        
        # Initialize LLM client
        self.llm_client = self._init_llm_client()
        
        # Load prompts
        self.system_prompt = self._load_prompt(config.system_prompt_path, "system")
        self.instruction_prompt = self._load_prompt(config.instruction_prompt_path, "instruction")
        self.few_shot_prompt = self._load_prompt(config.few_shot_prompt_path, "few_shot")
    
    def _init_llm_client(self):
        """Initialize the LLM client based on provider."""
        try:
            if self.llm_config.provider == LLMProvider.LITELLM:
                import litellm
                return litellm
            else:
                # Import and configure other providers as needed
                from polyskill.model.fm import FoundationModel
                return FoundationModel(
                    provider=self.llm_config.provider.value,
                    name=self.llm_config.model_name,
                    temperature=self.llm_config.temperature
                )
        except ImportError as e:
            self.logger.error(f"Failed to import LLM client: {e}")
            return None
    
    def _load_prompt(self, prompt_path: str, prompt_type: str) -> str:
        """Load a prompt from file."""
        if not prompt_path or not os.path.exists(prompt_path):
            return self._get_default_prompt(prompt_type)
        
        try:
            with open(prompt_path, 'r') as f:
                return f.read().strip()
        except Exception as e:
            self.logger.error(f"Failed to load {prompt_type} prompt from {prompt_path}: {e}")
            return self._get_default_prompt(prompt_type)
    
    def _get_default_prompt(self, prompt_type: str) -> str:
        """Get default prompts for different types."""
        defaults = {
            "system": """You are an expert at analyzing web automation trajectories and extracting reusable patterns.
Your task is to identify common action sequences that can be generalized into reusable functions.
Focus on creating clean, well-documented Python functions that can be easily reused.""",
            
            "instruction": """Analyze the following web automation examples and extract reusable functions.

Requirements:
1. Create Python functions that generalize the common patterns
2. Use descriptive function names and parameters
3. Add docstrings explaining the purpose and parameters
4. Handle edge cases and error conditions
5. Make functions as reusable as possible

Return only the Python functions, properly formatted with ```python blocks.""",
            
            "few_shot": """Example of good function extraction:

Input trajectories showing login actions:
- click('input[name="username"]')
- fill('input[name="username"]', 'testuser')
- click('input[name="password"]')  
- fill('input[name="password"]', 'password123')
- click('button[type="submit"]')

Output function:
```python
def login_to_site(page, username: str, password: str):
    \"\"\"
    Log in to a website using username and password.
    
    Args:
        page: Browser page object
        username: Username to enter
        password: Password to enter
    \"\"\"
    page.click('input[name="username"]')
    page.fill('input[name="username"]', username)
    page.click('input[name="password"]')
    page.fill('input[name="password"]', password)
    page.click('button[type="submit"]')
```"""
        }
        return defaults.get(prompt_type, "")
    
    def extract_skills(
        self,
        trajectories: List[Union[Dict[str, Any], TrajectoryExample]],
        task_context: Optional[str] = None
    ) -> SkillInductionResult:
        """Extract skills using LLM analysis of trajectories."""
        result = SkillInductionResult(success=True)
        
        if not trajectories:
            result.add_error("No trajectories provided")
            return result
        
        # Convert trajectories to examples
        examples = []
        for traj in trajectories:
            if isinstance(traj, dict):
                traj = self._dict_to_trajectory_example(traj)
            if traj:
                examples.append(traj)
        
        if not examples:
            result.add_error("No valid trajectory examples")
            return result
        
        # Limit number of examples per prompt
        if len(examples) > self.config.max_examples_per_prompt:
            examples = examples[:self.config.max_examples_per_prompt]
        
        try:
            # Generate query from examples
            query = self._build_query(examples, task_context)
            
            # Generate responses with LLM
            responses = self._generate_llm_responses(query)
            
            # Process responses to extract skills
            for i, response in enumerate(responses):
                extracted_skills = self._extract_skills_from_response(response, examples)
                result.skills.extend(extracted_skills)
            
            # Validate extracted skills
            valid_skills = self.validate_skills(result.skills)
            result.skills = valid_skills
            
            if not result.skills:
                result.add_error("No valid skills extracted from LLM responses")
            
        except Exception as e:
            self.logger.error(f"Error in LLM skill extraction: {e}")
            result.add_error(f"LLM extraction failed: {str(e)}")
        
        return result
    
    def _build_query(
        self, 
        examples: List[TrajectoryExample], 
        task_context: Optional[str] = None
    ) -> str:
        """Build the query string for LLM from trajectory examples."""
        query_parts = []
        
        # Add task context if provided
        if task_context:
            query_parts.append(f"## Task: {task_context}")
        
        # Add examples
        for i, example in enumerate(examples, 1):
            query_parts.append(f"### Example {i} ({example.task_id}): {example.goal}")
            
            # Format actions
            action_lines = []
            for action in example.actions:
                action_str = action.get("action", "")
                if action_str:
                    action_lines.append(action_str)
            
            if action_lines:
                query_parts.append("\n".join(action_lines))
            query_parts.append("")  # Empty line between examples
        
        return "\n".join(query_parts)
    
    def _generate_llm_responses(self, query: str) -> List[str]:
        """Generate responses from LLM."""
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": self.instruction_prompt},
            {"role": "user", "content": self.few_shot_prompt},
            {"role": "user", "content": query + "\n\n## Reusable Functions"}
        ]
        
        responses = []
        
        try:
            if hasattr(self.llm_client, 'completion'):  # litellm
                # Generate multiple responses if requested
                if self.llm_config.num_responses > 1 and "openai" in self.llm_config.model_name:
                    response = self.llm_client.completion(
                        model=self.llm_config.model_name,
                        messages=messages,
                        temperature=self.llm_config.temperature,
                        max_tokens=self.llm_config.max_tokens,
                        n=self.llm_config.num_responses
                    )
                    for choice in response.choices:
                        responses.append(choice.message.content)
                else:
                    # Generate responses one by one
                    for _ in range(self.llm_config.num_responses):
                        response = self.llm_client.completion(
                            model=self.llm_config.model_name,
                            messages=messages,
                            temperature=self.llm_config.temperature,
                            max_tokens=self.llm_config.max_tokens
                        )
                        responses.append(response.choices[0].message.content)
            
            elif hasattr(self.llm_client, 'generate'):  # FoundationModel
                for _ in range(self.llm_config.num_responses):
                    # Convert messages to single prompt for non-chat models
                    prompt = self._messages_to_prompt(messages)
                    response = self.llm_client.generate(
                        prompt=prompt,
                        max_tokens=self.llm_config.max_tokens,
                        temperature=self.llm_config.temperature
                    )
                    responses.append(response)
            
        except Exception as e:
            self.logger.error(f"Error generating LLM responses: {e}")
            raise
        
        return responses
    
    def _messages_to_prompt(self, messages: List[Dict[str, str]]) -> str:
        """Convert chat messages to a single prompt."""
        prompt_parts = []
        for msg in messages:
            role = msg["role"]
            content = msg["content"]
            
            if role == "system":
                prompt_parts.append(f"System: {content}")
            elif role == "user":
                prompt_parts.append(f"Human: {content}")
            elif role == "assistant":
                prompt_parts.append(f"Assistant: {content}")
        
        prompt_parts.append("Assistant:")
        return "\n\n".join(prompt_parts)
    
    def _extract_skills_from_response(
        self, 
        response: str, 
        examples: List[TrajectoryExample]
    ) -> List[Skill]:
        """Extract skills from LLM response."""
        skills = []
        
        # Extract Python code blocks
        code_blocks = self._extract_code_blocks(response)
        
        for i, code in enumerate(code_blocks):
            if "def " not in code:
                continue
            
            # Extract function information
            func_info = self._parse_function(code)
            if not func_info:
                continue
            
            # Create skill
            skill = Skill(
                id=f"llm_skill_{len(skills)}_{func_info['name']}",
                name=func_info['name'],
                skill_type=SkillType.CODE,
                format=SkillFormat.PYTHON_FUNCTION,
                content=code,
                description=func_info.get('docstring', ''),
                task_examples=[ex.goal for ex in examples[:3]],  # First 3 examples
                metadata=SkillMetadata(
                    source=self.__class__.__name__,
                    tags=['llm_generated', 'function']
                )
            )
            
            skills.append(skill)
        
        return skills
    
    def _extract_code_blocks(self, text: str) -> List[str]:
        """Extract Python code blocks from text."""
        # Pattern for ```python...``` blocks
        python_pattern = r'```python\n(.*?)\n```'
        matches = re.findall(python_pattern, text, re.DOTALL)
        
        # Also try generic code blocks
        if not matches:
            code_pattern = r'```\n(.*?)\n```'
            matches = re.findall(code_pattern, text, re.DOTALL)
        
        return [match.strip() for match in matches if match.strip()]
    
    def _parse_function(self, code: str) -> Optional[Dict[str, str]]:
        """Parse function information from code."""
        try:
            lines = code.split('\n')
            
            # Find function definition
            func_line = None
            for line in lines:
                if line.strip().startswith('def '):
                    func_line = line.strip()
                    break
            
            if not func_line:
                return None
            
            # Extract function name
            func_match = re.match(r'def\s+(\w+)\s*\(', func_line)
            if not func_match:
                return None
            
            func_name = func_match.group(1)
            
            # Extract docstring
            docstring = ""
            in_docstring = False
            for line in lines[1:]:  # Skip def line
                stripped = line.strip()
                if stripped.startswith('"""') or stripped.startswith("'''"):
                    if not in_docstring:
                        in_docstring = True
                        docstring = stripped[3:]
                        if stripped.endswith('"""') or stripped.endswith("'''"):
                            docstring = docstring[:-3].strip()
                            break
                    else:
                        docstring += " " + stripped[:-3].strip()
                        break
                elif in_docstring:
                    docstring += " " + stripped
            
            return {
                'name': func_name,
                'docstring': docstring.strip()
            }
        
        except Exception as e:
            self.logger.error(f"Error parsing function: {e}")
            return None
    
    def validate_skill(self, skill: Skill) -> bool:
        """Validate that a skill is well-formed."""
        if not skill.name or not skill.content:
            return False
        
        if skill.skill_type == SkillType.CODE:
            # Basic Python syntax validation
            try:
                compile(str(skill.content), '<string>', 'exec')
                return True
            except SyntaxError as e:
                self.logger.warning(f"Skill {skill.name} has syntax error: {e}")
                return False
        
        return True