#!/bin/bash

# 定义网站 URL
SITE_URL="http://localhost:8000"

# ✅ 修复 1: 改进 wp_exec 函数
# - 使用 docker-compose exec 自动查找容器
# - 设置 WP_CLI_CACHE_DIR 环境变量到 /tmp，解决 Permission denied 警告
function wp_exec() {
    docker-compose exec -T -u www-data -e WP_CLI_CACHE_DIR=/tmp/.wp-cli-cache wordpress wp "$@"
}

function init_env() {
    echo "🚀 [Epoch 0] 正在初始化环境..."
    
    # 1. 等待数据库完全就绪
    echo "⏳ 等待数据库就绪..."
    sleep 5
    
    # 2. 安装 WordPress 核心
    echo "📦 安装 WordPress..."
    # 如果已安装会报错，所以加个 || true 忽略错误，或者先检查
    wp_exec core is-installed || wp_exec core install --url="$SITE_URL" --title="Epoch & Drift Benchmark" --admin_user="admin" --admin_password="password" --admin_email="test@example.com" --skip-email

    # 3. 清理默认内容 (Hello World)
    echo "🧹 清理默认文章..."
    wp_exec post delete $(wp_exec post list --post_type=post --format=ids) --force 2>/dev/null

    # 4. 生成数据
    # ✅ 修复 2: 分离“噪音数据”和“目标数据”
    
    # A. 生成 5 篇无用的噪音文章 (Lorem Ipsum)
    # echo "📝 生成背景噪音文章..."
    # wp_exec post generate --count=5 --post_title="Noise Data" 
    
    # # B. 生成包含 Target 的核心文章 (使用 post create 避免参数截断问题)
    # echo "🎯 生成 Target 文章..."
    # TARGET_CODE="CODE-$(date +%s)"
    # wp_exec post create --post_title="The Secret Target" \
    #                     --post_status=publish \
    #                     --post_content="Target Information: The secret code is [${TARGET_CODE}]. Please find and extract this code."

    # 5. 下载不同风格的主题
    echo "🎨 下载 Drift 主题库..."
    wp_exec theme install twentytwelve --activate
    wp_exec theme install twentytwentyfour 
    wp_exec theme install news-portal
    
    # 确保切回最简单的主题作为起点
    wp_exec theme activate twentytwelve
    
    echo "✅ 初始化完成！"
    echo "🌍 访问地址: http://localhost:8000"
    echo "🔑 Target Code: ${TARGET_CODE}"
}

function trigger_drift() {
    THEME_SLUG=$1
    if [ -z "$THEME_SLUG" ]; then
        echo "❌ 错误: 请指定主题名称"
        return 1
    fi

    echo "🌊 [Drift Triggered] 正在切换至主题: $THEME_SLUG ..."
    
    # 切换主题
    wp_exec theme activate "$THEME_SLUG"
    
    # 清理缓存
    wp_exec cache flush
    
    echo "✅ 漂移完成！DOM 结构已重组。"
}

# 路由
case "$1" in
    init)
        init_env
        ;;
    drift)
        trigger_drift "$2"
        ;;
    *)
        echo "用法:"
        echo "  ./drift_manager.sh init          -> 初始化环境"
        echo "  ./drift_manager.sh drift <theme> -> 触发 UI 漂移"
        echo "  可用主题: twentytwelve (简单), twentytwentyfour (复杂Block), news-portal (杂志)"
        ;;
esac