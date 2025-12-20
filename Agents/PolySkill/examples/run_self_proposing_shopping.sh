#!/bin/bash
# Run Self-Proposing Exploration on Shopping Sites (GPT-4.1)
# Based on paper: Section 4.3 - Shopping Domains (Amazon, Target, WebArena)

set -e

ITERATIONS="${1:-150}"

echo "======================================================================"
echo " Self-Proposing Exploration: Shopping Domain"
echo "======================================================================"
echo "Model:      GPT-4.1"
echo "Domain:     Shopping (Amazon, Target, WebArena OneStopShop)"
echo "Iterations: $ITERATIONS"
echo ""
echo "This replicates the shopping domain experiment from Table 2:"
echo "  - Agent explores multiple shopping websites"
echo "  - Learns polymorphic AbstractShoppingSite skills"
echo "  - Evaluated on held-out WebArena Shopping tasks"
echo "======================================================================"

python -m polyskill.experiments.self_proposing.run_self_proposing \
    --config examples/configs/self_proposing_shopping_gpt4.yaml \
    --domain shopping \
    --iterations "$ITERATIONS" \
    --model gpt-4.1

echo ""
echo "======================================================================"
echo " Exploration Complete!"
echo "======================================================================"
echo "Results saved to: ./results/self_proposing/shopping/"
echo "Learned skills saved to: ./results/self_proposing_skills/shopping/"
echo ""
echo "Next steps:"
echo "  1. Review learned AbstractShoppingSite class and implementations"
echo "  2. Evaluate on held-out WebArena Shopping tasks"
echo "  3. Compare skill reusability vs baseline methods"
echo "======================================================================"
