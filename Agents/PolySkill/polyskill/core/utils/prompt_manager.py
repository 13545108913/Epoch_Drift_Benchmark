"""
Prompt Manager

Centralized management of prompts and templates for skill induction.
"""

import os
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class PromptType(Enum):
    """Types of prompts used in skill induction."""
    SYSTEM = "system"
    INSTRUCTION = "instruction"
    FEW_SHOT = "few_shot"
    EXTRACTION = "extraction"
    VALIDATION = "validation"


@dataclass
class PromptTemplate:
    """A prompt template with placeholders."""
    name: str
    content: str
    placeholders: List[str]
    description: str = ""
    
    def render(self, **kwargs) -> str:
        """Render the template with provided values."""
        rendered = self.content
        for placeholder in self.placeholders:
            if placeholder in kwargs:
                rendered = rendered.replace(f"{{{placeholder}}}", str(kwargs[placeholder]))
        return rendered
    
    def validate_placeholders(self, **kwargs) -> List[str]:
        """Validate that all required placeholders are provided."""
        missing = []
        for placeholder in self.placeholders:
            if placeholder not in kwargs:
                missing.append(placeholder)
        return missing


class PromptManager:
    """
    Manages prompts and templates for skill induction.
    
    Supports:
    - Loading prompts from files
    - Template rendering with placeholders
    - Domain-specific prompt variations
    - Prompt validation and testing
    """
    
    def __init__(self, prompt_dir: str = "prompts/"):
        """Initialize prompt manager."""
        self.prompt_dir = Path(prompt_dir)
        self.prompts: Dict[str, PromptTemplate] = {}
        self.domain_prompts: Dict[str, Dict[str, PromptTemplate]] = {}
        
        # Load default prompts
        self._load_default_prompts()
        
        # Load custom prompts if directory exists
        if self.prompt_dir.exists():
            self._load_custom_prompts()
    
    def _load_default_prompts(self):
        """Load default built-in prompts."""
        
        # System prompts
        self.register_prompt(
            "asi_system",
            """You are an expert at analyzing web automation trajectories and extracting reusable action patterns.
Your task is to identify common action sequences that can be generalized into reusable Python functions for web automation.
Focus on creating clean, well-documented functions that handle common web interaction patterns.

Guidelines:
- Create functions that are general enough to work across different websites
- Use descriptive names that clearly indicate the function's purpose
- Include proper error handling and edge cases
- Add comprehensive docstrings with parameter descriptions
- Follow Python best practices and PEP 8 style guidelines""",
            []
        )
        
        self.register_prompt(
            "asi_instruction",
            """Analyze the web automation examples below and extract reusable functions.

Requirements:
1. Create Python functions that generalize the common patterns
2. Use descriptive function names following snake_case convention  
3. Include proper type hints and docstrings
4. Handle common web automation scenarios (clicking, filling forms, navigation)
5. Make functions robust and reusable across different websites
6. Each function should be self-contained and focused on a single task
7. Use the 'page' parameter for the browser page object

Return only the Python functions, properly formatted with ```python blocks.
Do not include explanatory text outside the code blocks.""",
            []
        )
        
        self.register_prompt(
            "asi_few_shot",
            """Example of good function extraction:

Input: Multiple trajectories showing login workflows
```
click('input[name="username"]')
fill('input[name="username"]', 'testuser')
click('input[name="password"]')  
fill('input[name="password"]', 'password123')
click('button[type="submit"]')
```

Output:
```python
def login_with_credentials(page, username: str, password: str, submit_selector: str = 'button[type="submit"]'):
    \"\"\"
    Perform login using username and password fields.
    
    Args:
        page: Browser page object
        username: Username to enter
        password: Password to enter
        submit_selector: CSS selector for submit button
    \"\"\"
    page.click('input[name="username"]')
    page.fill('input[name="username"]', username)
    page.click('input[name="password"]')
    page.fill('input[name="password"]', password)
    page.click(submit_selector)

def fill_form_fields(page, field_data: dict):
    \"\"\"
    Fill multiple form fields with provided data.
    
    Args:
        page: Browser page object
        field_data: Dictionary mapping field selectors to values
    \"\"\"
    for selector, value in field_data.items():
        page.fill(selector, str(value))
```""",
            []
        )
        
        # Pattern-based prompts
        self.register_prompt(
            "pattern_analysis",
            """Analyze the following action sequences and identify common patterns:

{action_sequences}

Please identify:
1. Repeated action patterns
2. Common element selectors
3. Workflow sequences that appear multiple times
4. Potential reusable components

Format your response as structured patterns that can be converted to reusable functions.""",
            ["action_sequences"]
        )
        
        # Domain-specific prompts
        self._load_domain_prompts()
    
    def _load_domain_prompts(self):
        """Load domain-specific prompt variations."""
        domains = {
            "shopping": {
                "context": "e-commerce and online shopping websites",
                "common_actions": ["add to cart", "checkout", "search products", "filter results"],
                "selectors": ["cart", "checkout", "product", "price", "quantity"]
            },
            "admin": {
                "context": "administrative interfaces and dashboards",
                "common_actions": ["manage users", "update settings", "view reports", "navigate menus"],
                "selectors": ["admin", "dashboard", "menu", "settings", "users"]
            },
            "reddit": {
                "context": "Reddit social media platform",
                "common_actions": ["post content", "upvote", "comment", "navigate subreddits"],
                "selectors": ["post", "comment", "upvote", "subreddit", "thread"]
            },
            "gitlab": {
                "context": "GitLab development platform",
                "common_actions": ["create issues", "manage repositories", "review code", "CI/CD"],
                "selectors": ["repo", "issue", "merge", "pipeline", "commit"]
            },
            "map": {
                "context": "mapping and navigation interfaces",
                "common_actions": ["search locations", "get directions", "zoom/pan", "set markers"],
                "selectors": ["search", "directions", "marker", "zoom", "location"]
            }
        }
        
        for domain, info in domains.items():
            domain_system = f"""You are an expert at analyzing web automation trajectories for {info['context']}.
Focus on patterns specific to {domain} websites, including common actions like {', '.join(info['common_actions'])}.
Pay special attention to selectors related to {', '.join(info['selectors'])}."""
            
            self.register_domain_prompt(domain, "system", domain_system, [])
    
    def _load_custom_prompts(self):
        """Load custom prompts from files."""
        try:
            for prompt_file in self.prompt_dir.glob("*.txt"):
                with open(prompt_file, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                
                prompt_name = prompt_file.stem
                self.register_prompt(prompt_name, content, [])
            
            # Load JSON prompt definitions
            for json_file in self.prompt_dir.glob("*.json"):
                with open(json_file, 'r', encoding='utf-8') as f:
                    prompt_data = json.load(f)
                
                if isinstance(prompt_data, dict) and 'prompts' in prompt_data:
                    for prompt_info in prompt_data['prompts']:
                        self.register_prompt(
                            prompt_info['name'],
                            prompt_info['content'],
                            prompt_info.get('placeholders', []),
                            prompt_info.get('description', '')
                        )
        
        except Exception as e:
            logger.warning(f"Error loading custom prompts: {e}")
    
    def register_prompt(
        self, 
        name: str, 
        content: str, 
        placeholders: List[str],
        description: str = ""
    ):
        """Register a new prompt template."""
        template = PromptTemplate(
            name=name,
            content=content,
            placeholders=placeholders,
            description=description
        )
        self.prompts[name] = template
    
    def register_domain_prompt(
        self,
        domain: str,
        prompt_type: str,
        content: str,
        placeholders: List[str],
        description: str = ""
    ):
        """Register a domain-specific prompt."""
        if domain not in self.domain_prompts:
            self.domain_prompts[domain] = {}
        
        template = PromptTemplate(
            name=f"{domain}_{prompt_type}",
            content=content,
            placeholders=placeholders,
            description=description
        )
        self.domain_prompts[domain][prompt_type] = template
    
    def get_prompt(
        self, 
        name: str, 
        domain: Optional[str] = None,
        **kwargs
    ) -> str:
        """Get a rendered prompt."""
        template = None
        
        # Try domain-specific first
        if domain and domain in self.domain_prompts:
            template = self.domain_prompts[domain].get(name)
        
        # Fall back to general prompts
        if not template and name in self.prompts:
            template = self.prompts[name]
        
        if not template:
            raise ValueError(f"Prompt '{name}' not found" + (f" for domain '{domain}'" if domain else ""))
        
        # Validate placeholders
        missing = template.validate_placeholders(**kwargs)
        if missing:
            logger.warning(f"Missing placeholders for prompt '{name}': {missing}")
        
        return template.render(**kwargs)
    
    def build_message_sequence(
        self,
        system_prompt: str = "asi_system",
        instruction_prompt: str = "asi_instruction", 
        few_shot_prompt: str = "asi_few_shot",
        user_content: str = "",
        domain: Optional[str] = None,
        **kwargs
    ) -> List[Dict[str, str]]:
        """Build a complete message sequence for LLM."""
        messages = []
        
        # System message
        if system_prompt:
            messages.append({
                "role": "system",
                "content": self.get_prompt(system_prompt, domain=domain, **kwargs)
            })
        
        # Instruction message
        if instruction_prompt:
            messages.append({
                "role": "user", 
                "content": self.get_prompt(instruction_prompt, domain=domain, **kwargs)
            })
        
        # Few-shot examples
        if few_shot_prompt:
            messages.append({
                "role": "user",
                "content": self.get_prompt(few_shot_prompt, domain=domain, **kwargs)
            })
        
        # User content
        if user_content:
            messages.append({
                "role": "user",
                "content": user_content
            })
        
        return messages
    
    def list_prompts(self, domain: Optional[str] = None) -> List[str]:
        """List available prompts."""
        if domain and domain in self.domain_prompts:
            return list(self.domain_prompts[domain].keys())
        return list(self.prompts.keys())
    
    def list_domains(self) -> List[str]:
        """List available domains."""
        return list(self.domain_prompts.keys())
    
    def save_prompt(self, name: str, filepath: str):
        """Save a prompt to file."""
        if name not in self.prompts:
            raise ValueError(f"Prompt '{name}' not found")
        
        template = self.prompts[name]
        
        # Save as JSON with metadata
        prompt_data = {
            "name": template.name,
            "content": template.content,
            "placeholders": template.placeholders,
            "description": template.description
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(prompt_data, f, indent=2, ensure_ascii=False)
    
    def export_prompts(self, output_dir: str):
        """Export all prompts to directory."""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Export general prompts
        general_prompts = {
            "prompts": [
                {
                    "name": template.name,
                    "content": template.content,
                    "placeholders": template.placeholders,
                    "description": template.description
                }
                for template in self.prompts.values()
            ]
        }
        
        with open(output_path / "general_prompts.json", 'w') as f:
            json.dump(general_prompts, f, indent=2)
        
        # Export domain-specific prompts
        for domain, templates in self.domain_prompts.items():
            domain_prompts = {
                "domain": domain,
                "prompts": [
                    {
                        "name": template.name,
                        "content": template.content,
                        "placeholders": template.placeholders,
                        "description": template.description
                    }
                    for template in templates.values()
                ]
            }
            
            with open(output_path / f"{domain}_prompts.json", 'w') as f:
                json.dump(domain_prompts, f, indent=2)