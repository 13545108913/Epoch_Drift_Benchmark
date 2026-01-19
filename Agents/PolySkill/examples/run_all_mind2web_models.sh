#!/bin/bash
# Run Mind2Web experiments with all models (GPT-4.1, Claude-3.7-Sonnet, Qwen3-Coder, GLM-4.5)

set -e

SETTING="${1:-cross-task}"

echo "======================================================================"
echo " Running Mind2Web Experiments with All Models"
echo "======================================================================"
echo "Setting: $SETTING"
echo ""
echo "Models: GPT-4.1, Claude-3.7-Sonnet, Qwen3-Coder-480B-A35B, GLM-4.5"
echo "======================================================================"

# GPT-4.1
echo ""
echo "======================================================================"
echo " [1/4] Running with GPT-4.1"
echo "======================================================================"
python -m polyskill.experiments.mind2web.run_mind2web \
    --config examples/configs/mind2web_polyskill_gpt4.yaml \
    --setting "$SETTING" \
    --model gpt-4.1

# Claude-3.7-Sonnet
echo ""
echo "======================================================================"
echo " [2/4] Running with Claude-3.7-Sonnet"
echo "======================================================================"
python -m polyskill.experiments.mind2web.run_mind2web \
    --config examples/configs/mind2web_polyskill_claude.yaml \
    --setting "$SETTING" \
    --model claude-3.7-sonnet

# Qwen3-Coder-480B-A35B
echo ""
echo "======================================================================"
echo " [3/4] Running with Qwen3-Coder-480B-A35B"
echo "======================================================================"
python -m polyskill.experiments.mind2web.run_mind2web \
    --config examples/configs/mind2web_polyskill_qwen.yaml \
    --setting "$SETTING" \
    --model qwen3-coder-480b-a35b

# GLM-4.5
echo ""
echo "======================================================================"
echo " [4/4] Running with GLM-4.5"
echo "======================================================================"
python -m polyskill.experiments.mind2web.run_mind2web \
    --config examples/configs/mind2web_polyskill_glm.yaml \
    --setting "$SETTING" \
    --model glm-4.5

echo ""
echo "======================================================================"
echo " All Experiments Complete!"
echo "======================================================================"
echo "Results saved to:"
echo "  - ./results/mind2web/gpt4/"
echo "  - ./results/mind2web/claude/"
echo "  - ./results/mind2web/qwen/"
echo "  - ./results/mind2web/glm/"
echo "======================================================================"
