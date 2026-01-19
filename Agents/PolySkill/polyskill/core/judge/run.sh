METHODS=(
    webvoyager
    webjudge_general
    webjudge_online_mind2web
)

for method in "${METHODS[@]}"; do
    mkdir -p judge_results_orby_llm/$method
    python -m judge.batch_evaluate \
        --trajectory_dir orby-llm/browsergym_eval/test-onO4uZ_2025-07-25_09-38-16/webarena_qwen3_coder_qwen3_coder/browsergym \
        --method $method \
        --limit 8 \
        --model_provider openai \
        --model_name gpt-4o \
        --output_dir judge_results_orby_llm/$method \
        --max_concurrent 8
done