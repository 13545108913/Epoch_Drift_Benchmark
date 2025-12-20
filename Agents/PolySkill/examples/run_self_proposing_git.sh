#!/bin/bash
# Run Self-Proposing Exploration on Git Platforms (GPT-4.1)
# Based on paper: Section 4.3 - Coding Platforms (GitLab, GitHub) - Table 8

set -e

ITERATIONS="${1:-100}"

echo "======================================================================"
echo " Self-Proposing Exploration: Developer Tools Domain"
echo "======================================================================"
echo "Model:      GPT-4.1"
echo "Domain:     Git Platforms (GitHub, GitLab)"
echo "Iterations: $ITERATIONS"
echo ""
echo "This replicates the developer tools experiment from Table 8:"
echo "  - Agent explores GitHub and GitLab"
echo "  - Learns polymorphic AbstractDevPlatform skills"
echo "  - Evaluated on held-out GitLab tasks"
echo "======================================================================"

python -m polyskill.experiments.self_proposing.run_self_proposing \
    --config examples/configs/self_proposing_git_gpt4.yaml \
    --domain dev_tools \
    --iterations "$ITERATIONS" \
    --model gpt-4.1

echo ""
echo "======================================================================"
echo " Exploration Complete!"
echo "======================================================================"
echo "Results saved to: ./results/self_proposing/dev_tools/"
echo "Learned skills saved to: ./results/self_proposing_skills/dev_tools/"
echo ""
echo "Key findings from paper (Table 8):"
echo "  - Self-guided exploration achieves 66.2% SR on GitLab"
echo "  - Outperforms sequential curriculum (62.1%)"
echo "  - Better than single-domain specialist (65.5%)"
echo "======================================================================"
