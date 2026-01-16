#!/bin/bash

# 定义一个函数，包含：清理旧容器 -> 启动新容器 -> 配置环境 -> 运行Python -> 删除容器
run_isolated_task() {
    local drift_val=$1
    local waber_val=$2
    local out_dir=$3

    echo "========================================================"
    echo "正在初始化环境..."
    echo "Output Dir: $out_dir | Drift: $drift_val | Waber: $waber_val"
    echo "========================================================"

    # --- 步骤 0: 安全清理 (防止上一次意外中断导致容器残留) ---
    # 如果容器已存在，先强制删除，忽略不存在时的报错
    docker rm -f shopping_admin >/dev/null 2>&1

    # --- 步骤 1: 启动并配置 Docker 容器 ---
    echo "正在启动 Docker 容器 (shopping_admin)..."
    docker run --name shopping_admin -p 7780:80 -d shopping_admin_final_0719

    echo "正在配置 Magento URL..."
    # 稍微等待一下容器启动（可选，防止执行过快）
    sleep 10 

    # 执行您要求的配置指令
    docker exec shopping_admin /var/www/magento2/bin/magento setup:store-config:set --base-url="http://localhost:7780"
    docker exec shopping_admin mysql -u magentouser -pMyPassword magentodb -e 'UPDATE core_config_data SET value="http://localhost:7780/" WHERE path = "web/secure/base_url";'
    docker exec shopping_admin /var/www/magento2/bin/magento cache:flush

    sleep 200

    # --- 步骤 2: 配置 Conda 与 Python 环境 ---
    # 初始化 Conda
    eval "$(conda shell.bash hook)"
    conda activate skillweaver
    
    # 跳转路径
    cd "/Users/chenboyu/Desktop/Epoch_Drift_Benchmark/Agents_new/SkillWeaver" || { echo "路径不存在!"; docker rm -f shopping_admin; exit 1; }

    # 导出环境变量
    BASE_URL="http://172.26.116.102"                                                                                     
    export WA_SHOPPING="$BASE_URL:7770/"
    export WA_SHOPPING_ADMIN="http://localhost:7780/admin"
    export WA_REDDIT="$BASE_URL:9999"
    export WA_GITLAB="$BASE_URL:8080"
    export WA_WIKIPEDIA="$BASE_URL:8888/wikipedia_en_all_maxi_2022-05/A/User:The_other_Kiwix_guy/Landing"
    export WA_MAP="$BASE_URL:3000"
    export WA_HOMEPAGE="$BASE_URL:4399"
    export WA_WORDPRESS="http://localhost:8000"

    export SHOPPING="$BASE_URL:7770/"
    export SHOPPING_ADMIN="http://localhost:7780/admin"
    export REDDIT="$BASE_URL:9999"
    export GITLAB="$BASE_URL:8080"
    export WIKIPEDIA="$BASE_URL:8888/wikipedia_en_all_maxi_2022-05/A/User:The_other_Kiwix_guy/Landing"
    export MAP="$BASE_URL:3000"
    export HOMEPAGE="$BASE_URL:4399"
    export WORDPRESS="http://localhost:8000"

    export WA_GITLAB_V1="$BASE_URL:8080"
    export WA_GITLAB_V2="$BASE_URL:8080"
    export WA_SHOPPING_ADMIN_V1="http://localhost:7780/admin"
    export WA_SHOPPING_ADMIN_V2="http://localhost:7780/admin"
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
        --pool-size 6
    
    # 捕获 Python 的退出状态码
    EXIT_CODE=$?

    # --- 步骤 4: 清理容器 ---
    echo "任务结束，正在删除容器..."
    docker rm -f shopping_admin

    if [ $EXIT_CODE -ne 0 ]; then
        echo "警告：该任务执行失败 (Code: $EXIT_CODE)"
    fi
}

# --- 开始依次执行三个任务 ---
# 依然使用 ( ) 子 Shell 确保 Conda 环境和 Shell 变量完全隔离



# 任务 3: with_drift='false', with_waber='true'
(
    run_isolated_task "false" "true" "results/admin_with_skills_v2_waber"
)

echo "========================================================"
echo "所有任务流程已全部完成。"