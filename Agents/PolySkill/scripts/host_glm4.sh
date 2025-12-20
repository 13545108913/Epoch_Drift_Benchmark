#!/bin/bash
# Script to host GLM-4.5 model using SGLang
# This needs to be running before starting experiments with this model

set -e

# Configuration
MODEL_NAME="THUDM/glm-4-9b-chat"  # Replace with actual model path
PORT=30001
HOST="0.0.0.0"
TP_SIZE=4  # Tensor parallel size - adjust based on your GPU count

# Check if SGLang is installed
if ! command -v python -c "import sglang" &> /dev/null; then
    echo "Error: SGLang is not installed. Please install it first:"
    echo "pip install 'sglang[all]'"
    exit 1
fi

echo "Starting GLM-4.5 model server on port ${PORT}..."
echo "Model: ${MODEL_NAME}"
echo "Tensor Parallel Size: ${TP_SIZE}"

# Start the SGLang server
python -m sglang.launch_server \
    --model-path "${MODEL_NAME}" \
    --host "${HOST}" \
    --port "${PORT}" \
    --tp "${TP_SIZE}" \
    --trust-remote-code \
    --mem-fraction-static 0.85 \
    2>&1 | tee glm4_server.log

# Note: The server will run in the foreground
# To run in background, add '&' at the end or use screen/tmux
