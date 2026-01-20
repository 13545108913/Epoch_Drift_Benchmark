import pandas as pd
import numpy as np

# ================= 配置区域 =================
# 输入文件 (M2 导出的文件)
M2_CUSTOMER_FILE = '../magento_exports/customer_20251125_101259.csv'
M2_PRODUCT_FILE = '../magento_exports/catalog_product_20251125_100152.csv'

# 输出文件 (给 M1 导入用的文件)
M1_CUSTOMER_OUTPUT = 'm1_import_customers.csv'
M1_PRODUCT_OUTPUT = 'm1_import_products.csv'

# M1 的默认密码哈希 (对应密码: 123456)
# M1 使用 MD5, 有盐无盐皆可，这里使用简单的 MD5 方便测试
# 实际上 M1 格式通常是: md5(pass + salt):salt，或者直接 md5(pass)
# 这里使用 md5('123456') = e10adc3949ba59abbe56e057f20f883e
DEFAULT_PASSWORD_HASH = 'e10adc3949ba59abbe56e057f20f883e'

# ===========================================

def fix_customers():
    print("正在修复客户数据...")
    try:
        df = pd.read_csv(M2_CUSTOMER_FILE)
    except FileNotFoundError:
        return

    # 1. 基础映射
    rename_map = {
        'email': 'email', 'website_id': 'website_id', 'store_id': 'store_id',
        'created_in': 'created_in', 'firstname': 'firstname', 'lastname': 'lastname',
        'group_id': 'group_id', 'dob': 'dob', 'gender': 'gender',
        '_website': '_website', '_store': '_store'
    }
    df = df.rename(columns=rename_map)

    # 2. 解决密码问题
    df['password_hash'] = DEFAULT_PASSWORD_HASH

    # ================= 关键修复：Reward Points 报错 =================
    # 你的 M1 需要这两个字段，设为 1 (Subscribe) 或 0
    print("  - 自动填充缺失的 Reward Notification 字段...")
    df['reward_update_notification'] = 1
    df['reward_warning_notification'] = 1
    # ============================================================

    # 3. 确保核心列存在
    final_cols = [c for c in df.columns if c in rename_map.values() or c in ['password_hash', 'reward_update_notification', 'reward_warning_notification']]
    df_final = df[final_cols]
    
    df_final.to_csv(M1_CUSTOMER_OUTPUT, index=False)
    print(f"客户数据修复完成: {M1_CUSTOMER_OUTPUT}")

def fix_products():
    print("正在执行最终修复 (Product Final Fix)...")
    try:
        df = pd.read_csv(M2_PRODUCT_FILE)
    except FileNotFoundError:
        print(f"找不到 {M2_PRODUCT_FILE}")
        return

    # 1. 基础映射 (M2 -> M1)
    rename_map = {
        'sku': 'sku', 'name': 'name', 'description': 'description',
        'short_description': 'short_description', 'price': 'price',
        'weight': 'weight', 'url_key': 'url_key', 'visibility': 'visibility',
        'tax_class_name': 'tax_class_id', 'status': 'status', 'qty': 'qty',
        'is_in_stock': 'is_in_stock', 'product_type': '_type',
        'store_view_code': '_store', 'product_websites': '_product_websites',
        'base_image': 'image', 'small_image': 'small_image', 'thumbnail_image': 'thumbnail'
    }
    
    # 2. 筛选 Simple 商品 (避免复杂商品报错)
    if 'product_type' in df.columns:
        df = df[df['product_type'] == 'simple'].copy()

    # 3. 重命名列
    df = df.rename(columns=rename_map)

    # ================= 针对报错的强力修复 =================

    # [修复 1] Short Description 为空
    # 策略：如果为空，直接复制 Name (商品名) 填进去
    print("  - 修复 Short Description...")
    df['short_description'] = df['short_description'].fillna(df['name'])
    # 如果 Name 也是空的（极端情况），填一个默认值
    df['short_description'] = df['short_description'].fillna("Product Details")

    # [修复 2] Weight 为空
    # 策略：如果为空，默认填 1.0
    print("  - 修复 Weight...")
    df['weight'] = pd.to_numeric(df['weight'], errors='coerce').fillna(1.0)

    # [修复 3] Visibility (可见性) 格式错误
    # 策略：M2 的文字描述 M1 可能不认，强制转换为数字 ID (最稳)
    # 4 = Catalog, Search (最常用)
    # 1 = Not Visible Individually
    print("  - 修复 Visibility (转换为数字 ID)...")
    def map_visibility(val):
        s = str(val).lower()
        if 'catalog' in s and 'search' in s: return 4
        if 'search' in s: return 3
        if 'catalog' in s: return 2
        return 4 # 默认全设为可见，防止出错

    df['visibility'] = df['visibility'].apply(map_visibility)

    # ================= 其他必要修复 =================
    
    # 强制 Tax Class ID (M1 通常 2=Taxable Goods, 0=None)
    df['tax_class_id'] = 2 

    # 强制 Attribute Set 为 Default
    df['_attribute_set'] = 'Default'

    # 暂时清空分类 (避免分类不存在报错)
    df['_category'] = ''
    
    # 强制状态 (1=Enabled)
    df['status'] = 1

    # 设置根分类
    df['_root_category'] = 'Default Category'

    # 导出
    target_cols = [
        'sku', '_store', '_attribute_set', '_type', '_category', '_root_category',
        '_product_websites', 'name', 'description', 'short_description', 'price',
        'weight', 'status', 'visibility', 'tax_class_id', 'qty', 'is_in_stock',
        'image', 'small_image', 'thumbnail'
    ]
    
    # 确保所有列都存在，不存在的填空
    for col in target_cols:
        if col not in df.columns:
            df[col] = ''

    # 最终导出
    df[target_cols].to_csv(M1_PRODUCT_OUTPUT, index=False)
    print(f"成功！请上传此文件: {M1_PRODUCT_OUTPUT}")

if __name__ == '__main__':
    fix_customers()
    fix_products()