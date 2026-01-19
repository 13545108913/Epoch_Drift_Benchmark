#!/bin/bash
# Run WebArena experiments with PolySkill

set -e

# Configuration
MODEL="${1:-gpt-4}"
CATEGORY="${2:-all}"
CONFIG="${3:-examples/configs/webarena_polyskill.yaml}"

echo "======================================================================"
echo " Running WebArena Experiment with PolySkill"
echo "======================================================================"
echo "Model:    $MODEL"
echo "Category: $CATEGORY"
echo "Config:   $CONFIG"
echo "======================================================================"

# Run the experiment
python -m polyskill.experiments.webarena.run_webarena \
    --config "$CONFIG" \
    --category "$CATEGORY" \
    --model "$MODEL"

echo ""
echo "======================================================================"
echo " Experiment Complete!"
echo "======================================================================"
echo "Results saved to: ./results/webarena/"
echo "Learned skills saved to: ./results/webarena_skills/"
echo "======================================================================"
