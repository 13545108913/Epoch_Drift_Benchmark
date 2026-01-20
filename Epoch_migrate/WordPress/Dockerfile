FROM wordpress:latest

# 安装 sudo 和 less (wp-cli 需要)
RUN apt-get update && apt-get install -y sudo less

# 安装 WP-CLI
RUN curl -O https://raw.githubusercontent.com/wp-cli/builds/gh-pages/phar/wp-cli.phar \
    && chmod +x wp-cli.phar \
    && mv wp-cli.phar /usr/local/bin/wp

# 清理缓存
RUN apt-get clean && rm -rf /var/lib/apt/lists/*