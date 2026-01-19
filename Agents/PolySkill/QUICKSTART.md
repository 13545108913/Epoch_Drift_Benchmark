# PolySkill Quick Start Guide

Get started with PolySkill in 5 minutes!

## Prerequisites

- Python 3.9+
- Chrome/Chromium browser
- API keys for OpenAI and/or Anthropic

## Step 1: Install

```bash
# Clone and navigate to directory
cd PolySkill

# Install dependencies
pip install -r requirements.txt

# Install PolySkill
pip install -e .
```

## Step 2: Set Up API Keys

Create a `.env` file:

```bash
cat > .env << EOF
OPENAI_API_KEY=your_openai_key_here
ANTHROPIC_API_KEY=your_anthropic_key_here
EOF
```

## Step 3: Run Your First Experiment

### Option A: Mind2Web (Recommended for First Time)

```bash
# Run on cross-task setting with GPT-4
./examples/run_mind2web.sh gpt-4 cross-task
```

This will:
1. Load Mind2Web cross-task benchmark
2. Run agent with polymorphic skill induction
3. Learn skills from successful tasks
4. Evaluate on held-out tasks
5. Show detailed metrics

Expected runtime: ~2-3 hours for full cross-task set

### Option B: WebArena Shopping

```bash
# Run on shopping category only
./examples/run_webarena.sh gpt-4 shopping
```

### Option C: Self-Proposing Exploration

```bash
# Let agent explore shopping sites autonomously
./examples/run_self_proposing_shopping.sh 50
```

## Step 4: View Results

After completion, you'll see:

```
╔═══════════════════════════════════════════════════════╗
║              PolySkill Evaluation Metrics             ║
╠═══════════════════════════════════════════════════════╣
║ Task Success Rate:      63.2% (160/252)               ║
║ Avg Steps per Task:       4.2                         ║
╠═══════════════════════════════════════════════════════╣
║ Skill Reusability:      31.0% (15/48)                 ║
║ Task Coverage:          58.0% (146/252)               ║
║ Skill Compositionality:  2.4                          ║
╚═══════════════════════════════════════════════════════╝
```

Results are saved to:
- `./results/` - Experiment logs and trajectories
- `./results/*_skills/` - Learned polymorphic skills

## Step 5: Inspect Learned Skills

```bash
# View learned abstract classes and implementations
cat ./results/mind2web_skills/AbstractShoppingSite.py
cat ./results/mind2web_skills/AmazonWebsite.py
cat ./results/mind2web_skills/TargetWebsite.py
```

You'll see polymorphic skill structures like:

```python
class AbstractShoppingSite:
    def search_product(self, query: str):
        """Abstract search interface"""
        pass

class AmazonWebsite(AbstractShoppingSite):
    def search_product(self, query: str):
        # Amazon-specific implementation
        click(search_box_id)
        fill(search_box_id, query)
        keyboard_press('Enter')
```

## Common Issues & Solutions

### Issue: "Module not found"
**Solution:** Make sure you ran `pip install -e .`

### Issue: "API key not found"
**Solution:** Check your `.env` file has correct keys

### Issue: "Browser timeout"
**Solution:** Increase timeout in config:
```yaml
runner:
  timeout_per_task: 600  # Increase from default
```

### Issue: Too slow
**Solution:** Start with fewer tasks:
```bash
# Edit config to reduce max_examples
vim examples/configs/mind2web_polyskill.yaml
# Change max_examples: 252 -> max_examples: 10
```

## Next Steps

1. **Try Different Models:**
   ```bash
   ./examples/run_mind2web.sh claude-3.7-sonnet cross-task
   ```

2. **Run All Models (Reproduce Paper):**
   ```bash
   ./examples/run_all_mind2web_models.sh cross-task
   ```

3. **Customize Experiments:**
   - Edit configs in `examples/configs/`
   - Modify prompts in `polyskill/prompts/`
   - Add new benchmarks in `polyskill/experiments/`

4. **Analyze Results:**
   ```python
   from polyskill.core.metrics import MetricsCalculator

   calc = MetricsCalculator()
   # Load your trajectories
   metrics = calc.calculate_all_metrics()
   print(metrics)
   ```

## Example Workflows

### Research Workflow
1. Run baseline (no skill induction)
2. Run PolySkill
3. Compare metrics
4. Analyze learned skills

### Development Workflow
1. Modify skill induction logic in `polyskill/core/`
2. Test on small subset (max_examples: 10)
3. Run full evaluation
4. Compare with previous results

### Exploration Workflow
1. Start self-proposing agent
2. Monitor exploration progress
3. Evaluate learned skills on held-out tasks
4. Iterate on task proposal strategy

## Getting Help

- 📖 Read full [README.md](README.md)
- 🐛 Report issues on GitHub
- 💬 Ask questions in Discussions
- 📧 Email: yu.chi@northeastern.edu

## Quick Reference

| Command | What it does |
|---------|-------------|
| `./examples/run_mind2web.sh` | Mind2Web experiment |
| `./examples/run_webarena.sh` | WebArena experiment |
| `./examples/run_self_proposing.sh` | Autonomous exploration |
| `./examples/run_all_*_models.sh` | Multi-model experiments |
| `python -m polyskill.experiments.*` | Direct Python execution |

Happy experimenting! 🚀
