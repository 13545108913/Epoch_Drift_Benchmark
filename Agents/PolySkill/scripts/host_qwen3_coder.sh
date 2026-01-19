#!/bin/bash
# Script to host Qwen3-Coder-480B-A35B model using SGLang
# This needs to be running before starting experiments with this model

set -e

# Configuration
MODEL_NAME="Qwen/Qwen2.5-Coder-32B-Instruct"  # Replace with actual model path
PORT=30000
HOST="0.0.0.0"
TP_SIZE=8  # Tensor parallel size - adjust based on your GPU count

# Check if SGLang is installed
if ! command -v python -c "import sglang" &> /dev/null; then
    echo "Error: SGLang is not installed. Please install it first:"
    echo "pip install 'sglang[all]'"
    exit 1
fi

echo "Starting Qwen3-Coder-480B-A35B model server on port ${PORT}..."
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
    2>&1 | tee qwen3_server.log

# Note: The server will run in the foreground
# To run in background, add '&' at the end or use screen/tmux
