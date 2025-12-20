# LLM as Judge for Digital Agent Trajectories

This module integrates LLM-based evaluation methods from Online-Mind2Web to assess trajectory data saved by the digital agent evaluation framework.

## Overview

The judge module provides three evaluation methods adapted from Online-Mind2Web:

1. **WebJudge General** - General web task evaluation with key point analysis
2. **WebJudge Online Mind2Web** - Specialized evaluation for Mind2Web-style tasks
3. **WebVoyager** - Screenshot-based trajectory evaluation

## Installation & Setup

Ensure you have the required dependencies:

```bash
# Install digital agent requirements
pip install -r requirements.txt

# Additional dependencies for judge module
pip install Pillow tqdm
```

Set up your API keys:

```bash
export OPENAI_API_KEY="your-openai-key"
# Or for Anthropic
export ANTHROPIC_API_KEY="your-anthropic-key"
```

## Usage

### Single Trajectory Evaluation

Evaluate a single trajectory file:

```bash
python judge/evaluate_trajectory.py \
  --trajectory_path path/to/trajectory.pb.xz \
  --method webjudge_general \
  --model_name gpt-4o \
  --output_path results.json
```

### Batch Evaluation

Evaluate all trajectories in a directory:

```bash
python judge/batch_evaluate.py \
  --trajectory_dir path/to/evaluation/results \
  --method webvoyager \
  --output_dir judge_results \
  --max_concurrent 3
```

### Python API

```python
import asyncio
from judge.trajectory_judge import TrajectoryJudge

# Configure model
model_config = {
    "provider": "openai",
    "name": "gpt-4o",
    "temperature": 0.0,
    "max_tokens": 2048
}

# Initialize judge
judge = TrajectoryJudge(model_config)

# Evaluate trajectory
async def evaluate():
    results = await judge.judge_trajectory_webvoyager(
        trajectory_path="path/to/trajectory.pb.xz",
        k=5  # Use final 5 screenshots
    )
    return results

# Run evaluation
results = asyncio.run(evaluate())
```

## Evaluation Methods

### WebJudge General

Best for: General web tasks with optional input context images

```bash
python judge/evaluate_trajectory.py \
  --trajectory_path trajectory.pb.xz \
  --method webjudge_general \
  --input_images context1.png context2.png
```

**Output:**
- Task description and key points
- Per-screenshot analysis
- Final response evaluation
- Success/failure assessment

### WebJudge Online Mind2Web

Best for: Mind2Web-style navigation tasks

```bash
python judge/evaluate_trajectory.py \
  --trajectory_path trajectory.pb.xz \
  --method webjudge_online_mind2web
```

**Output:**
- Task key point extraction
- Screenshot-by-screenshot evaluation
- Navigation progress assessment

### WebVoyager

Best for: End-to-end task completion assessment

```bash
python judge/evaluate_trajectory.py \
  --trajectory_path trajectory.pb.xz \
  --method webvoyager \
  --k_screenshots 5  # Use final 5 screenshots only
```

**Output:**
- Overall task completion verdict (SUCCESS/FAILURE)
- Detailed reasoning
- Final response validation

## Configuration Options

### Model Configuration

```bash
# OpenAI GPT-4
--model_provider openai --model_name gpt-4o

# Anthropic Claude
--model_provider anthropic --model_name claude-3-5-sonnet-20241022

# Temperature control
--temperature 0.0  # Deterministic
--temperature 0.7  # More creative
```

### Batch Processing

```bash
# Limit concurrent evaluations
--max_concurrent 5

# Process subset for testing
--limit 10

# Custom temporary directory
--temp_dir /path/to/temp
```

## Output Format

### Single Evaluation Results

```json
{
  "task": "Find the cheapest flight from NYC to LA",
  "final_response": "Found flight for $299 on Delta",
  "trajectory_success": true,
  "key_points": "1. Search for flights\n2. Filter by price\n3. Select cheapest option",
  "screenshot_judgments": [
    {
      "step": 0,
      "screenshot_path": "/tmp/screenshot_000.png", 
      "judgment": "Shows flight search interface..."
    }
  ],
  "metadata": {
    "trajectory_path": "trajectory.pb.xz",
    "method": "webjudge_general",
    "model_config": {...}
  }
}
```

### Batch Evaluation Summary

```json
{
  "metadata": {
    "total_trajectories": 50,
    "successful_evaluations": 48,
    "failed_evaluations": 2,
    "method": "webvoyager"
  },
  "successful_trajectories": ["task1", "task2", ...],
  "failed_trajectories": [
    {"name": "task3", "error": "Screenshot extraction failed"}
  ]
}
```

## Integration with Digital Agent

The judge module is designed to work seamlessly with trajectory data from `orby/digitalagent/evaluation/eval_loop.py`:

1. **Trajectory Format**: Reads `trajectory.pb.xz` files containing `TrajectoryData` protobuf objects
2. **Screenshot Extraction**: Automatically extracts screenshots from action data
3. **Task Information**: Uses goal and result information from trajectory
4. **Compatibility**: Works with all digital agent evaluation configurations

### Example Workflow

1. Run digital agent evaluation:
```bash
python scripts/run_eval.py scripts/eval_configs/sanity_check.yaml
```

2. Evaluate results with LLM judge:
```bash
python judge/batch_evaluate.py \
  --trajectory_dir s3://orby-llm/browsergym_eval/test_run \
  --method webvoyager \
  --output_dir judge_results
```

## Testing

Test the integration:

```bash
python judge/test_integration.py
```

This will verify:
- Model connectivity
- Key point extraction
- Utility functions
- Basic judge functionality

## Troubleshooting

### Common Issues

1. **Missing trajectory files**: Ensure evaluation completed successfully and debug_dir was specified
2. **API rate limits**: Reduce `--max_concurrent` for batch processing
3. **Memory issues**: Use `--temp_dir` on disk with sufficient space
4. **Model errors**: Check API keys and model availability

### Debug Mode

Enable verbose logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### File Locations

- Screenshots saved to temporary directories
- Individual results: `{output_dir}/{trajectory_name}_evaluation.json`
- Batch summary: `{output_dir}/evaluation_summary.json`

## Advanced Usage

### Custom Model Configuration

```python
model_config = {
    "provider": "openai",
    "name": "gpt-4o",
    "temperature": 0.1,
    "max_tokens": 4096,
    "frequency_penalty": 0.1
}
```

### Programmatic Batch Processing

```python
import asyncio
from judge.batch_evaluate import evaluate_single_trajectory
from judge.trajectory_judge import TrajectoryJudge

async def custom_evaluation():
    judge = TrajectoryJudge(model_config)
    
    results = []
    for trajectory_path in trajectory_files:
        result = await evaluate_single_trajectory(
            judge=judge,
            trajectory_path=trajectory_path,
            method="webvoyager",
            temp_dir="/tmp/judge"
        )
        results.append(result)
    
    return results
```

## Contributing

To extend the judge module:

1. Add new evaluation methods to `TrajectoryJudge` class
2. Update argument parsing in evaluation scripts
3. Add tests in `test_integration.py`
4. Update this README with new usage examples