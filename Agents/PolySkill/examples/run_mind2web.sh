#!/bin/bash
# Run Mind2Web experiments with PolySkill

set -e

# Configuration
MODEL="${1:-gpt-4}"
SETTING="${2:-cross-task}"
CONFIG="${3:-examples/configs/mind2web_polyskill.yaml}"

echo "======================================================================"
echo " Running Mind2Web Experiment with PolySkill"
echo "======================================================================"
echo "Model:   $MODEL"
echo "Setting: $SETTING"
echo "Config:  $CONFIG"
echo "======================================================================"

# Run the experiment
python -m polyskill.experiments.mind2web.run_mind2web \
    --config "$CONFIG" \
    --setting "$SETTING" \
    --model "$MODEL"

echo ""
echo "======================================================================"
echo " Experiment Complete!"
echo "======================================================================"
echo "Results saved to: ./results/mind2web/"
echo "Learned skills saved to: ./results/mind2web_skills/"
echo "======================================================================"
