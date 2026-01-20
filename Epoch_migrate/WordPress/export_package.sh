#!/bin/bash

# 1. 创建打包目录
DIST_DIR="dist_package"
# 清理旧的（如果存在）以免冲突
rm -rf $DIST_DIR
mkdir -p $DIST_DIR/db_init
mkdir -p $DIST_DIR/wp_content

echo "📦 开始打包..."

# 2. 导出数据库 (修复版)
echo "💾 正在导出数据库..."
# 解释：我们直接调用 'db' 容器的 mysqldump 工具，并将结果直接流式写入到宿主机的文件中
# 注意：这里使用的是 docker-compose.yml 里配置的密码 wp_password
docker-compose exec -T db mysqldump -u wp_user -pwp_password wordpress > ./$DIST_DIR/db_init/init.sql

if [ $? -eq 0 ]; then
    echo "✅ 数据库导出成功 (./$DIST_DIR/db_init/init.sql)"
else
    echo "❌ 数据库导出失败，请检查容器是否正在运行"
    exit 1
fi

# 3. 导出 wp-content (主题、插件、上传的图片)
echo "📂 正在导出 wp-content..."
# 获取 wordpress 容器 ID
WP_CONTAINER_ID=$(docker-compose ps -q wordpress)

# 从容器复制文件到宿主机
# 注意：排除 cache 目录以减小体积（可选，这里先全量复制）
docker cp $WP_CONTAINER_ID:/var/www/html/wp-content/. ./$DIST_DIR/wp_content/

# 4. 复制必要的基础文件
echo "Cc 正在复制脚本和配置文件..."
cp Dockerfile ./$DIST_DIR/
cp drift_manager.sh ./$DIST_DIR/
chmod +x ./$DIST_DIR/drift_manager.sh

# 5. 生成适用于分发的 docker-compose.yml
echo "📝 生成分发版 docker-compose.yml..."
cat > ./$DIST_DIR/docker-compose.yml <<EOF
version: '3.8'

services:
  db:
    image: mariadb:10.6
    environment:
      MYSQL_ROOT_PASSWORD: rootpassword
      MYSQL_DATABASE: wordpress
      MYSQL_USER: wp_user
      MYSQL_PASSWORD: wp_password
    volumes:
      # 【分发关键】自动导入 SQL
      - ./db_init:/docker-entrypoint-initdb.d
      # 数据持久化
      - db_data_local:/var/lib/mysql
    restart: always

  wordpress:
    build: .
    depends_on:
      - db
    ports:
      - "8000:80"
    environment:
      WORDPRESS_DB_HOST: db
      WORDPRESS_DB_USER: wp_user
      WORDPRESS_DB_PASSWORD: wp_password
      WORDPRESS_DB_NAME: wordpress
    volumes:
      # 【分发关键】直接使用本地文件夹
      - ./wp_content:/var/www/html/wp-content
      # 这是一个空挂载，用于防止脚本报错，实际不需要数据
      - ./temp_import:/tmp/import_data
    restart: always

volumes:
  db_data_local:
EOF

# 创建一个空的 temp_import 目录防止报错
mkdir -p $DIST_DIR/temp_import

echo "✅ 打包完成！"
echo "👉 请压缩 '$DIST_DIR' 文件夹并发送给对方。"