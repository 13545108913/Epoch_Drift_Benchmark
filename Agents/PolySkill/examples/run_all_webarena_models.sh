#!/bin/bash
# Run WebArena experiments with all models (GPT-4.1, Claude-3.7-Sonnet, Qwen3-Coder, GLM-4.5)

set -e

CATEGORY="${1:-all}"

echo "======================================================================"
echo " Running WebArena Experiments with All Models"
echo "======================================================================"
echo "Category: $CATEGORY"
echo ""
echo "Models: GPT-4.1, Claude-3.7-Sonnet, Qwen3-Coder-480B-A35B, GLM-4.5"
echo "======================================================================"

# GPT-4.1
echo ""
echo "======================================================================"
echo " [1/4] Running with GPT-4.1"
echo "======================================================================"
python -m polyskill.experiments.webarena.run_webarena \
    --config examples/configs/webarena_polyskill_gpt4.yaml \
    --category "$CATEGORY" \
    --model gpt-4.1

# Claude-3.7-Sonnet
echo ""
echo "======================================================================"
echo " [2/4] Running with Claude-3.7-Sonnet"
echo "======================================================================"
python -m polyskill.experiments.webarena.run_webarena \
    --config examples/configs/webarena_polyskill_claude.yaml \
    --category "$CATEGORY" \
    --model claude-3.7-sonnet

# Qwen3-Coder-480B-A35B
echo ""
echo "======================================================================"
echo " [3/4] Running with Qwen3-Coder-480B-A35B"
echo "======================================================================"
python -m polyskill.experiments.webarena.run_webarena \
    --config examples/configs/webarena_polyskill_qwen.yaml \
    --category "$CATEGORY" \
    --model qwen3-coder-480b-a35b

# GLM-4.5
echo ""
echo "======================================================================"
echo " [4/4] Running with GLM-4.5"
echo "======================================================================"
python -m polyskill.experiments.webarena.run_webarena \
    --config examples/configs/webarena_polyskill_glm.yaml \
    --category "$CATEGORY" \
    --model glm-4.5

echo ""
echo "======================================================================"
echo " All Experiments Complete!"
echo "======================================================================"
echo "Results saved to:"
echo "  - ./results/webarena/gpt4/"
echo "  - ./results/webarena/claude/"
echo "  - ./results/webarena/qwen/"
echo "  - ./results/webarena/glm/"
echo "======================================================================"
