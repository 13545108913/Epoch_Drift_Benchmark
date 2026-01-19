# Baseline Methods

This directory contains the baseline methods compared in the PolySkill paper.

## Included Baselines

### ASI (Agent Skill Induction)
- **Repository**: [zorazrw/agent-skill-induction](https://github.com/zorazrw/agent-skill-induction)
- **Paper**: "Agent Skill Induction: Learning Skills from Demonstrations"
- **Location**: `baselines/ASI/`

ASI is a method for inducing skills from agent trajectories. It focuses on extracting reusable action sequences from successful task completions.

### SkillWeaver
- **Repository**: [OSU-NLP-Group/SkillWeaver](https://github.com/OSU-NLP-Group/SkillWeaver)
- **Paper**: "SkillWeaver: Composing Skills from Demonstrations"
- **Location**: `baselines/SkillWeaver/`

SkillWeaver is a framework for learning compositional skills from web navigation demonstrations.

## Setup

The baselines are included as git submodules. To initialize and update them:

```bash
# Clone with submodules
git clone --recursive https://github.com/your-org/polyskill.git

# Or if already cloned, initialize submodules
git submodule update --init --recursive
```

## Running Baselines

### ASI

```bash
cd baselines/ASI
# Follow the setup instructions in ASI/README.md
pip install -r requirements.txt

# Run ASI experiments
python run_experiment.py --config configs/webarena.yaml
```

### SkillWeaver

```bash
cd baselines/SkillWeaver
# Follow the setup instructions in SkillWeaver/README.md
pip install -r requirements.txt

# Run SkillWeaver experiments
python main.py --task webarena
```

## Comparison with PolySkill

PolySkill extends these baselines by introducing:

1. **Polymorphic Abstraction**: Separates abstract skill interfaces from concrete implementations
2. **Cross-Domain Generalization**: Skills transfer across different websites and domains
3. **Compositional Skills**: Skills can call other skills, enabling hierarchical composition
4. **Task-Free Learning**: Self-proposes and learns from autonomous exploration

For detailed comparisons, see the main [README](../README.md) and our [paper](https://arxiv.org/abs/2510.15863).

## PolySkill Integration

Note that PolySkill has integrated and extended some ASI components:
- `polyskill/core/inducers/asi_inducer.py` - ASI-based skill induction
- `polyskill/agents/agent/asi_utils/` - Utilities adapted from ASI

These integrations allow for direct comparison and build upon the ASI methodology with polymorphic abstractions.

## Citation

If you use these baselines, please cite the original papers:

```bibtex
@article{asi2024,
  title={Agent Skill Induction: Learning Skills from Demonstrations},
  author={...},
  journal={arXiv preprint arXiv:...},
  year={2024}
}

@article{skillweaver2024,
  title={SkillWeaver: Composing Skills from Demonstrations},
  author={...},
  journal={arXiv preprint arXiv:...},
  year={2024}
}
```
