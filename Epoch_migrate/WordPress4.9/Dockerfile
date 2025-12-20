FROM wordpress:4.9-php7.2-apache

# 直接跳过 apt 安装，手动安装 WP-CLI
RUN curl -O https://raw.githubusercontent.com/wp-cli/builds/gh-pages/phar/wp-cli.phar \
    && chmod +x wp-cli.phar \
    && mv wp-cli.phar /usr/local/bin/wp

# 只有这一行需要改：告诉 WP-CLI 不要用 less 分页，防止报错
ENV PAGER="cat"