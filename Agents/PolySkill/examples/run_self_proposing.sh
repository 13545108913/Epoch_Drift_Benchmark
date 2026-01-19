#!/bin/bash
# Run Self-Proposing Exploration with PolySkill

set -e

# Configuration
MODEL="${1:-gpt-4}"
DOMAIN="${2:-mixed}"
ITERATIONS="${3:-150}"
CONFIG="${4:-examples/configs/self_proposing_polyskill.yaml}"

echo "======================================================================"
echo " Running Self-Proposing Exploration with PolySkill"
echo "======================================================================"
echo "Model:      $MODEL"
echo "Domain:     $DOMAIN"
echo "Iterations: $ITERATIONS"
echo "Config:     $CONFIG"
echo "======================================================================"
echo ""
echo "The agent will autonomously:"
echo "  • Explore websites and propose its own goals"
echo "  • Learn polymorphic skills from successful attempts"
echo "  • Build a transferable skill library"
echo ""
echo "======================================================================"

# Run the experiment
python -m polyskill.experiments.self_proposing.run_self_proposing \
    --config "$CONFIG" \
    --domain "$DOMAIN" \
    --iterations "$ITERATIONS" \
    --model "$MODEL"

echo ""
echo "======================================================================"
echo " Exploration Complete!"
echo "======================================================================"
echo "Results saved to: ./results/self_proposing/"
echo "Learned skills saved to: ./results/self_proposing_skills/"
echo "======================================================================"
