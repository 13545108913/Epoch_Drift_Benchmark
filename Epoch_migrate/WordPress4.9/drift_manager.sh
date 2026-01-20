#!/bin/bash

# 定义网站 URL
SITE_URL="http://localhost:8000"

function wp_exec() {
    # WP 4.9 也可以使用这个缓存设置
    docker-compose exec -T -u www-data -e WP_CLI_CACHE_DIR=/tmp/.wp-cli-cache wordpress wp "$@"
}

function init_env() {
    echo "🚀 [Epoch 0] 正在初始化环境 (Target: WordPress 4.9)..."
    
    echo "⏳ 等待数据库就绪..."
    sleep 10  # 旧版 WP 启动可能稍慢，多给一点时间
    
    echo "📦 安装 WordPress 4.9..."
    wp_exec core is-installed || wp_exec core install --url="$SITE_URL" --title="WP 4.9 Benchmark" --admin_user="admin" --admin_password="password" --admin_email="test@example.com" --skip-email

    echo "🧹 清理默认内容..."
    wp_exec post delete $(wp_exec post list --post_type=post --format=ids) --force 2>/dev/null

    # --- 生成数据 (记得取消注释) ---
    echo "📝 生成背景噪音文章..."
    wp_exec post generate --count=5 --post_title="Noise Data" 
    
    echo "🎯 生成 Target 文章..."
    TARGET_CODE="CODE-$(date +%s)"
    wp_exec post create --post_title="The Secret Target" \
                    --post_status=publish \
                    --post_content="Target Information: The secret code is [${TARGET_CODE}]. Please find and extract this code."
    # ----------------------------

    echo "🎨 下载适合 WP 4.9 的经典主题..."
    # ⚠️ 注意：WP 4.9 不支持 Block Themes (如 twentytwentyfour)
    wp_exec theme install twentytwelve --activate
    wp_exec theme install twentyfifteen  # 替换掉 2024
    wp_exec theme install news-portal
    
    # 确保切回起点
    wp_exec theme activate twentytwelve
    
    echo "✅ 初始化完成 (WP 4.9)！"
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
    wp_exec theme activate "$THEME_SLUG"
    wp_exec cache flush
    echo "✅ 漂移完成！"
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
        echo "  ./drift_manager.sh init"
        echo "  ./drift_manager.sh drift <theme>"
        echo "  可用主题: twentytwelve, twentyfifteen, news-portal"
        ;;
esac