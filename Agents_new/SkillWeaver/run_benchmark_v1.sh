#!/bin/bash

# --- 配置区域 ---
TIMEOUT_SECONDS=10800  # 3小时超时
CONTAINER_NAME="shopping_admin"

# 定义核心任务函数
run_isolated_task() {
    local drift_val=$1
    local waber_val=$2
    local out_dir=$3

    # 定义路径变量
    local MIGRATE_DIR="/Users/chenboyu/Desktop/Epoch_Drift_Benchmark/Epoch_migrate"
    local WORK_DIR="$MIGRATE_DIR/my-magento"
    local SKILLWEAVER_DIR="/Users/chenboyu/Desktop/Epoch_Drift_Benchmark/Agents_new/SkillWeaver"

    echo "========================================================"
    echo ">> [任务启动] Output: $out_dir | Drift: $drift_val | Waber: $waber_val"
    echo "========================================================"
    
    # --- 步骤 2: 配置 Conda 与 Python 环境 ---
    eval "$(conda shell.bash hook)"
    conda activate skillweaver
    
    cd "$SKILLWEAVER_DIR" || { echo "SkillWeaver 路径不存在!"; exit 1; }

    # 导出环境变量
    BASE_URL="http://172.26.116.102"                                                                                     
    export WA_SHOPPING="$BASE_URL:7770/"
    export WA_SHOPPING_ADMIN="http://dockerized-magento.local/admin"
    export WA_REDDIT="$BASE_URL:9999"
    export WA_GITLAB="$BASE_URL:8080"
    export WA_WIKIPEDIA="$BASE_URL:8888/wikipedia_en_all_maxi_2022-05/A/User:The_other_Kiwix_guy/Landing"
    export WA_MAP="$BASE_URL:3000"
    export WA_HOMEPAGE="$BASE_URL:4399"
    export WA_WORDPRESS="http://localhost:8000"

    export SHOPPING="$BASE_URL:7770/"
    export SHOPPING_ADMIN="http://dockerized-magento.local/admin"
    export REDDIT="$BASE_URL:9999"
    export GITLAB="$BASE_URL:8080"
    export WIKIPEDIA="$BASE_URL:8888/wikipedia_en_all_maxi_2022-05/A/User:The_other_Kiwix_guy/Landing"
    export MAP="$BASE_URL:3000"
    export HOMEPAGE="$BASE_URL:4399"
    export WORDPRESS="http://localhost:8000"

    export WA_GITLAB_V1="$BASE_URL:8080"
    export WA_GITLAB_V2="$BASE_URL:8080"
    export WA_SHOPPING_ADMIN_V1="http://dockerized-magento.local/admin"
    export WA_SHOPPING_ADMIN_V2="http://dockerized-magento.local/admin"
    export WA_WORDPRESS_V1="http://localhost:8000"
    export WA_WORDPRESS_V2="http://localhost:8000"

    export my_api_key="sk-wFOxHykWS5f5hcWXjEYwty5eriAiMvrcvHwdyVCXzvChY8g6"
    export my_base_url="https://yunwu.ai/v1"
    export my_model="gpt-5-mini-2025-08-07"
    export with_drift="$drift_val"
    export with_waber="$waber_val"

    # --- 步骤 3: 执行 Python 任务 ---
    echo "开始执行 Python 任务..."
    python -m skillweaver.evaluation.evaluate_benchmark shopping_admin "$out_dir" \
        --knowledge-base-path-prefix logs/explore-admin/iter_159/kb_post \
        --pool-size 8
    
    EXIT_CODE=$?

    # --- 步骤 4: 正常结束清理 ---
    echo "任务结束，正在清理环境..."
    

    
    if [ $EXIT_CODE -ne 0 ]; then
        echo "警告：该任务执行失败 (Code: $EXIT_CODE)"
        exit $EXIT_CODE
    fi
}

# 导出函数供子 Shell 使用
export -f run_isolated_task

# --- 核心控制函数：带超时监控的执行器 ---
execute_task_safely() {
    local p1=$1
    local p2=$2
    local p3=$3
    
    echo "--------------------------------------------------------"
    echo "启动新任务 (超时限制: 3小时)..."
    
    # 使用 bash -c 启动全新的 Shell 进程执行任务
    bash -c "run_isolated_task '$p1' '$p2' '$p3'" &
    local TASK_PID=$!
    local start_time=$(date +%s)
    
    while true; do
        # 检查任务是否完成
        if ! kill -0 $TASK_PID 2>/dev/null; then
            wait $TASK_PID
            local code=$?
            echo ">> 任务进程已结束 (Exit Code: $code)。"
            break
        fi
        
        # 检查超时
        local current_time=$(date +%s)
        local elapsed=$((current_time - start_time))
        
        if [ $elapsed -ge $TIMEOUT_SECONDS ]; then
            echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
            echo ">> [超时警告] 任务运行时间超过 3 小时，强制终止！"
            echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
            
            kill -9 $TASK_PID >/dev/null 2>&1
            
            # 超时强制清理逻辑
            echo ">> 执行强制清理..."
            docker rm -f $CONTAINER_NAME >/dev/null 2>&1
            
            local MIGRATE_DIR="/Users/chenboyu/Desktop/Epoch_Drift_Benchmark/Epoch_migrate"
            if [ -d "$MIGRATE_DIR/my-magento" ]; then
                cd "$MIGRATE_DIR/my-magento" && docker-compose down -v >/dev/null 2>&1
            fi
            
            break
        fi
        sleep 10
    done
}

# --- 执行任务队列 ---

execute_task_safely "false" "false" "results/admin_with_skills_v1"

execute_task_safely "true" "false" "results/admin_with_skills_v1_drift"

execute_task_safely "false" "true" "results/admin_with_skills_v1_waber"

echo "========================================================"
echo "所有任务流程已全部完成。"