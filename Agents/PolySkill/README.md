# PolySkill: Learning Generalizable Skills Through Polymorphic Abstraction

[![Paper](https://img.shields.io/badge/Paper-2510.15863-red?style=for-the-badge&logo=arxiv&logoColor=white)](https://arxiv.org/abs/2510.15863)
[![Python](https://img.shields.io/badge/python-3.9+-blue?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)](https://opensource.org/licenses/MIT)
[![GitHub](https://img.shields.io/badge/GitHub-PolySkill-181717?style=for-the-badge&logo=github&logoColor=white)](https://github.com/simonucl/PolySkill)

Official implementation of **PolySkill**, a framework that enables web agents to learn generalizable and compositional skills through polymorphic abstraction.

**Authors:** Simon Yu(1), Gang Li(2), Weiyan Shi(1), Peng Qi(2)
(1) Northeastern University, (2) Uniphore

> **Paper:** [PolySkill: Learning Generalizable Skills Through Polymorphic Abstraction](https://arxiv.org/abs/2510.15863)

---

## 📰 News

**[2025-11-10]** 🎉 We are excited to release the PolySkill paper and code! Check out our [arXiv paper](https://arxiv.org/abs/2510.15863) and explore the [GitHub repository](https://github.com/simonucl/PolySkill).

---

## 🎯 Overview

PolySkill introduces a novel approach to web agent skill learning inspired by polymorphism in software engineering. By separating a skill's **abstract goal** (what it accomplishes) from its **concrete implementation** (how it's executed), PolySkill enables agents to:

- Learn skills that generalize across different websites
- Compose complex behaviors from simpler, reusable components
- Improve performance with 1.3-1.8x gains over existing methods
- Self-improve through autonomous exploration

## 📦 Installation

### Prerequisites

- Python 3.9+
- Node.js 18+ (for BrowserGym)
- Chrome/Chromium browser

### Quick Install

```bash
# Clone the repository (with baseline submodules)
git clone --recursive https://github.com/simonucl/PolySkill.git
cd PolySkill

# Or if already cloned, initialize submodules
git submodule update --init --recursive

# Install dependencies
pip install -r requirements.txt

# Install in development mode
pip install -e .

# Setup BrowserGym
bash setup_browsergym.sh
```

### Environment Variables

Create a `.env` file with your API keys:

```bash
# For OpenAI models
OPENAI_API_KEY=your_openai_key

# For Anthropic models
ANTHROPIC_API_KEY=your_anthropic_key

# Optional: For other open source models in OpenRouter (Qwen3-Coder-480B-A35B, GLM-4.5)
# OPENROUTER_API_KEY=your_openrouter_key
# Skip this if you are hosting your own models via vllm/sglang
```

### Hosting Open-Source Models (Qwen3-Coder-480B-A35B, GLM-4.5)

For running experiments with **Qwen3-Coder-480B-A35B** and **GLM-4.5**, you need to host them locally using SGLang **before** starting experiments:

```bash
# Install SGLang
pip install --upgrade pip
pip install uv
uv pip install "sglang" --prerelease=allow

# Start Qwen3-Coder-480B-A35B server (runs on port 30000)
# This requires multiple GPUs (adjust TP_SIZE in the script based on your setup)
./scripts/host_qwen3_coder.sh

# In another terminal, start GLM-4.5 server (runs on port 30001)
./scripts/host_glm4.sh
```

**Important:**
- The model servers must be running before starting experiments
- Use `screen` or `tmux` to keep servers running in the background
- Adjust `TP_SIZE` (tensor parallel size) in the scripts based on your GPU count
- Default ports: Qwen3-Coder on 30000, GLM-4.5 on 30001

---

## 🚀 Quick Start

### 1. Mind2Web Experiments

Run PolySkill on Mind2Web benchmark:

```bash
# Single model, cross-task setting
./examples/run_mind2web.sh gpt-4 cross-task

# All models on all settings
./examples/run_all_mind2web_models.sh cross-task
```

Available settings:
- `cross-task`: Generalization to new tasks on seen websites
- `cross-website`: Generalization to new websites in seen domains
- `cross-domain`: Generalization to entirely new domains

### 2. WebArena Experiments

Run PolySkill on WebArena benchmark:

```bash
# Single category with GPT-4
./examples/run_webarena.sh gpt-4 shopping

# All models on all categories
./examples/run_all_webarena_models.sh all
```

Available categories:
- `shopping`: E-commerce site (187 tasks)
- `admin`: CMS admin panel (182 tasks)
- `reddit`: Forum (106 tasks)
- `gitlab`: Development platform (180 tasks)
- `map`: OpenStreetMap (109 tasks)
- `cross`: Cross-website tasks (48 tasks)
- `all`: All categories

### 3. Self-Proposing Exploration

Let the agent autonomously explore and learn skills:

```bash
# 🛒 Shopping domain (replicates Table 2 from paper)
./examples/run_self_proposing_shopping.sh 150

# 💻 Git platforms (replicates Table 8 from paper)
./examples/run_self_proposing_git.sh 100
```

---

## 📊 Reproducing Paper Results

### Mind2Web (Table 5, Table 6)

```bash
# GPT-4.1 on all settings
python -m polyskill.experiments.mind2web.run_mind2web \
    --config examples/configs/mind2web_polyskill_gpt4.yaml \
    --setting cross-task \
    --model gpt-4.1

# Claude-3.7-Sonnet
python -m polyskill.experiments.mind2web.run_mind2web \
    --config examples/configs/mind2web_polyskill_claude.yaml \
    --setting cross-website \
    --model claude-3.7-sonnet

# Open-source models (Qwen3, GLM-4.5)
python -m polyskill.experiments.mind2web.run_mind2web \
    --config examples/configs/mind2web_polyskill_qwen.yaml \
    --setting cross-domain \
    --model qwen3-coder-480b-a35b
```

### WebArena (Table 7)

```bash
# Run all models on shopping category
for model in gpt-4.1 claude-3.7-sonnet qwen3-coder-480b-a35b glm-4.5; do
    python -m polyskill.experiments.webarena.run_webarena \
        --config examples/configs/webarena_polyskill_${model}.yaml \
        --category shopping \
        --model $model
done
```

### Self-Proposing Exploration (Table 2, Table 8)

```bash
# 🛒 Shopping domain (Table 2)
python -m polyskill.experiments.self_proposing.run_self_proposing \
    --config examples/configs/self_proposing_shopping_gpt4.yaml \
    --domain shopping \
    --iterations 150 \
    --model gpt-4.1

# 💻 Developer tools (Table 8)
python -m polyskill.experiments.self_proposing.run_self_proposing \
    --config examples/configs/self_proposing_git_gpt4.yaml \
    --domain dev_tools \
    --iterations 100 \
    --model gpt-4.1
```

---

## 🔬 Running Baseline Methods

We include ASI and SkillWeaver as git submodules for comparison. To run the baselines:

```bash
# Initialize submodules
git submodule update --init --recursive

# Run ASI baseline
cd baselines/ASI
pip install -r requirements.txt
python run_experiment.py --config configs/webarena.yaml

# Run SkillWeaver baseline
cd baselines/SkillWeaver
pip install -r requirements.txt
python main.py --task webarena
```

For detailed baseline setup and comparison, see [baselines/README.md](baselines/README.md).

**Note:** PolySkill integrates and extends ASI components in:
- `polyskill/core/inducers/asi_inducer.py` - ASI-based skill induction with polymorphic extensions
- `polyskill/agents/agent/asi_utils/` - Adapted ASI utilities

---

## 🏗️ Architecture

### Core Components

```
polyskill/
├── core/                       # Skill induction engine
│   ├── core.py                # Main skill induction logic
│   ├── skill_storage.py       # Polymorphic skill storage
│   ├── inducers/              # Skill induction strategies
│   │   ├── pattern_inducer.py  # Pattern-based induction
│   │   ├── polymorphic_inducer.py  # Polymorphic abstraction
│   │   └── asi_inducer.py     # ASI-based induction (adapted)
│   └── judge/                 # Task success verification
├── agents/                    # Agent implementations
│   ├── agent/                 # Base agent architecture
│   │   ├── vlm_based.py       # Vision-language model agent
│   │   ├── llm_based.py       # Language model agent
│   │   └── asi_utils/         # ASI utilities (adapted)
│   └── planner/               # Task planning
├── experiments/               # Experiment scripts
│   ├── mind2web/              # Mind2Web experiments
│   ├── webarena/              # WebArena experiments
│   └── self_proposing/        # Autonomous exploration
├── configs/                   # Configuration files
├── prompts/                   # Prompt templates
├── utils/                     # Utility functions
└── baselines/                 # Baseline methods (git submodules)
    ├── ASI/                   # Agent Skill Induction baseline
    └── SkillWeaver/           # SkillWeaver baseline
```

### Polymorphic Skill Structure

```python
# Abstract class defines the interface
class AbstractShoppingSite:
    def search_product(self, query: str):
        """Searches for a product."""
        pass

    def add_to_cart(self, item_id: str, quantity: int):
        """Adds item to shopping cart."""
        pass

    # Compositional skill
    def find_and_purchase(self, query: str, item_id: str):
        self.search_product(query)
        self.add_to_cart(item_id)
        self.checkout()

# Concrete implementations for specific websites
class AmazonWebsite(AbstractShoppingSite):
    def search_product(self, query: str):
        # Amazon-specific implementation
        click(search_box_id)
        fill(search_box_id, query)
        keyboard_press('Enter')
```

---

## 📈 Evaluation Metrics

PolySkill introduces new metrics beyond task success rate:

1. **Skill Reusability**: Fraction of learned skills used in new tasks
2. **Task Coverage**: Percentage of tasks that benefit from skills
3. **Skill Compositionality**: How often skills build upon each other
4. **Step Reduction**: Average reduction in action steps

View metrics during evaluation:

```bash
# Results will show:
# - Task Success Rate: 63.2% (up 9.4% vs baseline)
# - Skill Reusability: 31.0% (vs 18% for ASI)
# - Task Coverage: 58% (vs 45% for baselines)
# - Avg Steps: 4.2 (vs 5.4 for baselines)
```

---

## ⚙️ Configuration

### Basic Configuration

```yaml
# examples/configs/my_experiment.yaml

skill_induction:
  enabled: true
  use_polymorphism: true          # Enable polymorphic abstraction
  abstract_class_induction: true  # Learn abstract classes
  composition_enabled: true       # Enable skill composition

  judge_method: webjudge_general
  storage_path: ./my_skills/

model_configs:
  default:
    provider: openai
    name: gpt-4.1
    temperature: 0.1

agents:
  default:
    name: hsm_v3_with_polyskill
    model_config_name: default
```

### Advanced Options

See `examples/configs/` for full configuration examples including:
- Custom skill induction strategies
- Multi-model ensemble
- Exploration strategies
- Judge customization

---

## 📝 Citation

If you use PolySkill in your research, please cite:

```bibtex
@article{yu2025polyskill,
  title={PolySkill: Learning Generalizable Skills Through Polymorphic Abstraction},
  author={Yu, Simon and Li, Gang and Shi, Weiyan and Qi, Peng},
  journal={arXiv preprint arXiv:2510.15863},
  year={2025}
}
```

---

## 🤝 Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

### Development Setup

```bash
# Install dev dependencies
pip install -r requirements-dev.txt

# Run tests
pytest tests/

# Format code
black polyskill/
flake8 polyskill/
```

---

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

We acknowledge **[Orby](https://www.orby.ai/)** (now part of Uniphore) for providing the computational resources and infrastructure support that made the experiments in this paper possible. We thank the authors of **[ASI (Agent Skill Induction)](https://github.com/zorazrw/agent-skill-induction)** and **[SkillWeaver](https://github.com/OSU-NLP-Group/SkillWeaver)** for their pioneering work on skill induction in web agents, which inspired and informed this research. We are grateful to **[SGLang](https://github.com/sgl-project/sglang)** for their exceptional day-0 support and rapid resolution of issues when hosting Qwen3-Coder and GLM-4.5 models. This work builds on **[BrowserGym](https://github.com/ServiceNow/BrowserGym)** for web agent evaluation, and leverages the **[Mind2Web](https://osu-nlp-group.github.io/Mind2Web/)** and **[WebArena](https://webarena.dev/)** benchmarks for rigorous evaluation.

---

## 📧 Contact

For questions or issues:
- **Simon Yu**: yu.chi@northeastern.edu
- **GitHub Issues**: https://github.com/simonucl/PolySkill/issues

---

## 🔗 Links

- 📄 **Paper**: https://arxiv.org/abs/2510.15863
- 💻 **Code**: https://github.com/simonucl/PolySkill
- 📊 **Mind2Web**: https://osu-nlp-group.github.io/Mind2Web/
- 🌐 **WebArena**: https://webarena.dev/

---

**Made with care by the PolySkill Team**

[Back to Top](#polyskill-learning-generalizable-skills-through-polymorphic-abstraction)
