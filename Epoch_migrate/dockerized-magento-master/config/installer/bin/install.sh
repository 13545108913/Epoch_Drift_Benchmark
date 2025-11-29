#!/bin/bash

set -e

#####################################
# Update the Magento Installation
# Arguments:
#   None
# Returns:
#   None
#####################################
function updateMagento() {
    # 【修改点 1】手动模式下，跳过所有 Composer 操作
    echo "Manual Mode detected: Skipping Composer update/install."
    echo "Assuming Magento source code is already present in $MAGENTO_ROOT"
}

#####################################
# Print URLs and Logon Information
# Arguments:
#   None
# Returns:
#   None
#####################################
function printLogonInformation() {
    baseUrl="http://$DOMAIN"
    frontendUrl="$baseUrl/"
    backendUrl="$baseUrl/admin"

    echo ""
    echo "======================================================="
    echo "Magento 1.9 Manual Installation Complete"
    echo "======================================================="
    echo "phpMyAdmin: $baseUrl:8080"
    echo " - Username: ${MYSQL_USER}"
    echo " - Password: ${MYSQL_PASSWORD}"
    echo ""
    echo "Backend: $backendUrl"
    echo " - Username: ${ADMIN_USERNAME}"
    echo " - Password: ${ADMIN_PASSWORD}"
    echo ""
    echo "Frontend: $frontendUrl"
    echo "======================================================="
}


#####################################
# Fix the filesystem permissions for the magento root.
# Arguments:
#   None
# Returns:
#   None
#####################################
function fixFilesystemPermissions() {
    echo "Fixing filesystem permissions in $MAGENTO_ROOT..."
    # 确保 var 和 media 目录存在，否则权限命令会报错
    mkdir -p $MAGENTO_ROOT/var
    mkdir -p $MAGENTO_ROOT/media
    chmod -R 777 $MAGENTO_ROOT/var
    chmod -R 777 $MAGENTO_ROOT/media
    chmod -R 777 $MAGENTO_ROOT/app/etc
}

#####################################
# A never-ending while loop (which keeps the installer container alive)
# Arguments:
#   None
# Returns:
#   None
#####################################
function runForever() {
    echo "Installer is now sleeping to keep container alive..."
    while :
    do
        sleep 60
    done
}

# Fix the www-folder permissions
chgrp -R 33 /var/www/html

# Check if the MAGENTO_ROOT direcotry has been specified
if [ -z "$MAGENTO_ROOT" ]
then
    echo "Please specify the root directory of Magento via the environment variable: MAGENTO_ROOT"
    exit 1
fi

# Check if the specified MAGENTO_ROOT direcotry exists
if [ ! -d "$MAGENTO_ROOT" ]
then
    echo "Creating directory $MAGENTO_ROOT"
    mkdir -p $MAGENTO_ROOT
fi

# 【修改点 2】检测 local.xml 而不是 index.php
# 因为手动解压会有 index.php，但没有 local.xml (数据库配置)。
# 如果检测到 local.xml，才说明环境已经配置好了。
if [ -e "$MAGENTO_ROOT/app/etc/local.xml" ]
then
    echo "Magento configuration (local.xml) already exists."
    echo "Skipping installation steps."
    
    echo "Fixing filesystem permissions"
    fixFilesystemPermissions

    echo "Startup finished"
    printLogonInformation

    runForever
    exit 0
fi

# ================= 这里开始是安装流程 =================

echo "Preparing the Magerun Configuration"
substitute-env-vars.sh /etc /etc/n98-magerun.yaml.tmpl

echo "Starting Manual Installation Process..."
updateMagento # 这里现在只会打印一条消息

# 检查手动文件是否真的存在
if [ ! -e "$MAGENTO_ROOT/index.php" ]; then
    echo "ERROR: index.php not found in $MAGENTO_ROOT"
    echo "You are in Manual Mode. Please unzip Magento 1.9 files into the 'web' folder manually!"
    exit 1
fi

echo "Preparing the Magento Configuration"
substitute-env-vars.sh /etc /etc/local.xml.tmpl
substitute-env-vars.sh /etc /etc/fpc.xml.tmpl

echo "Overriding Magento Configuration"
# 确保目标目录存在
mkdir -p /var/www/html/web/app/etc
cp -v /etc/local.xml /var/www/html/web/app/etc/local.xml
cp -v /etc/fpc.xml /var/www/html/web/app/etc/fpc.xml

echo "Installing Sample Data: Media"
# 注意：如果你不想下载官方示例图片（可能很慢），注释掉下面这行
curl -s -L https://raw.githubusercontent.com/Vinai/compressed-magento-sample-data/1.9.1.0/compressed-no-mp3-magento-sample-data-1.9.1.0.tgz | tar xz -C /tmp
# 只有在下载成功后才移动，避免覆盖错误
if [ -d "/tmp/magento-sample-data-1.9.1.0" ]; then
    cp -rn /tmp/magento-sample-data-*/* $MAGENTO_ROOT/ || true
    rm -rf /tmp/magento-sample-data-*
fi

echo "Installing Sample Data: Database"
# 等待 MySQL 启动，避免连接拒绝
echo "Waiting for MySQL to start..."
sleep 10 

magerun --skip-root-check --root-dir="$MAGENTO_ROOT" db:create || echo "Database might already exist, continuing..."

# 检查目录下是否有用户自己放的 sql 文件，如果有优先用用户的，否则尝试用 sample data
databaseFilePath="$MAGENTO_ROOT/magento_sample_data_for_1.9.1.0.sql"

if [ -f "$databaseFilePath" ]; then
    echo "Importing Sample Data SQL..."
    magerun --skip-root-check --root-dir="$MAGENTO_ROOT" db:import $databaseFilePath
    # 导入后通常建议删除 SQL 减小体积，这里先保留以防万一
    # rm $databaseFilePath
else 
    echo "No sample data SQL found at $databaseFilePath. Skipping DB import (assuming empty DB or user managed)."
fi

echo "Installing Sample Data: Reindex"
magerun --skip-root-check --root-dir="$MAGENTO_ROOT" cache:clean
magerun --skip-root-check --root-dir="$MAGENTO_ROOT" index:reindex:all

echo "Creating Admin User"
# 即使 DB 已存在，重新运行此命令通常是安全的（或者会报错已存在但不会中断脚本）
magerun --skip-root-check --root-dir="$MAGENTO_ROOT" \
        admin:user:create \
        "${ADMIN_USERNAME}" \
        "${ADMIN_EMAIL}" \
        "${ADMIN_PASSWORD}" \
        "${ADMIN_FIRSTNAME}" \
        "${ADMIN_LASTNAME}" \
        "Administrators" || echo "Admin user creation skipped (maybe already exists)"

echo "Enable Fullpage Cache"
magerun --skip-root-check --root-dir="$MAGENTO_ROOT" cache:enable fpc || true

echo "Fixing filesystem permissions"
fixFilesystemPermissions

echo "Installation finished"
printLogonInformation

runForever
exit 0