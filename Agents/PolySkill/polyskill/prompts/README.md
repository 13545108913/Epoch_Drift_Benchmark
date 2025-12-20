# PolySkill Prompts

This directory contains the prompt templates used by different agent implementations in PolySkill.

## Structure

```
prompts/
├── llm_based/              # Prompts for LLM-based agent (text-only)
│   ├── prompts_20241119.py  # Main prompt definitions
│   └── ...
├── default.py              # Default prompts for task executors
└── README.md               # This file
```

## Prompt Modules

### LLM-Based Agent Prompts (`llm_based/`)

Used by: `polyskill.agents.agent.llm_based.BasicCoTAgent`

Contains prompts for text-only language model agents with chain-of-thought reasoning:
- `SYSTEM_PROMPT` - System instructions for the agent
- `GROUNDING_PROMPT_BEFORE_IMG` - Instructions for visual grounding
- `GOAL_IMAGES_PROMPT` - Goal image processing prompts
- `ANSWER_PROMPT` - Task answer formatting
- `grounding_prompt_after_img()` - Dynamic grounding prompt generation

**File:** `llm_based/prompts_20241119.py`

### Default Task Executor Prompts (`default.py`)

Used by:
- `polyskill.agents.agent.task_executors.hybrid_executor_agent`
- `polyskill.agents.agent.task_executors.pixel_coord_executor_agent`

Contains template definitions for:
- `hybrid_executor` - Hybrid execution strategy prompts
- `pixel_coord_executor` - Pixel coordinate-based execution prompts

## Adding New Prompts

When creating new agent types:

1. Create a new directory named after your agent (e.g., `my_agent/`)
2. Add your prompt definitions in Python files or Jinja2 templates
3. Import them in your agent implementation
4. Update this README with documentation

## Prompt Format

Prompts can be defined as:
- **Python strings** - Simple static prompts
- **Python functions** - Dynamic prompts with parameters
- **Jinja2 templates** (`.jinja` or `.jinja2`) - Complex templated prompts

Example:
```python
from polyskill.prompts.llm_based.prompts_20241119 import SYSTEM_PROMPT

# Use in agent
agent = BasicCoTAgent(system_prompt=SYSTEM_PROMPT)
```

## Version History

- **2024-11-19** (`llm_based/prompts_20241119.py`) - LLM-based agent prompts for open source release
- **default.py** - Task executor prompts maintained from original implementation
