import gitlab
import json
import sys
import time
from datetime import datetime

# --- 配置 (与你的主脚本一致) ---
V14_URL = 'http://10.22.35.100:8023'
V14_ADMIN_TOKEN = 'glpat-p4hoV7_pysTddVZgWVnL'
OUTPUT_FILE = f'gitlab_member_roles_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
MAX_RETRIES = 3  # 最大重试次数
RETRY_DELAY = 5  # 重试延迟（秒）
# ---

# --- 角色等级映射 ---
ACCESS_LEVEL_MAP = {
    10: 'Guest',
    20: 'Reporter',
    30: 'Developer',
    40: 'Maintainer',
    50: 'Owner'
}

def get_role_name(access_level):
    """将 access_level 转换为角色名称"""
    return ACCESS_LEVEL_MAP.get(access_level, f'Unknown ({access_level})')

# --- 辅助函数 (来自你的原脚本) ---

def safe_get(obj, attr, default=None):
    """安全获取对象属性，处理空值"""
    try:
        value = getattr(obj, attr, default)
        return value if value is not None else default
    except:
        return default

def retry_with_backoff(func, *args, **kwargs):
    """重试装饰器函数，带有指数退避"""
    last_exception = None
    for attempt in range(MAX_RETRIES):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            last_exception = e
            if attempt < MAX_RETRIES - 1:
                wait_time = RETRY_DELAY * (2 ** attempt)
                print(f"    重试 {attempt + 1}/{MAX_RETRIES} 在 {wait_time} 秒后... 错误: {e}")
                time.sleep(wait_time)
    
    print(f"    ❌ 在 {MAX_RETRIES} 次重试后失败: {last_exception}")
    raise last_exception

# --- 核心抓取函数 ---

def get_project_members(project):
    """获取项目所有成员（包括继承的）及其角色"""
    
    def _get_members():
        # 使用 members_all.list() 来获取包括继承成员在内的所有成员
        # 这是获取项目有效成员的最准确方法
        members = project.members_all.list(all=True)
        member_data = []
        
        for member in members:
            access_level = safe_get(member, 'access_level', 0)
            member_data.append({
                "id": safe_get(member, 'id'),
                "username": safe_get(member, 'username', 'unknown_user'),
                "name": safe_get(member, 'name', ''),
                "access_level": access_level,
                "role": get_role_name(access_level)
            })
        return member_data

    try:
        # 使用重试逻辑包装抓取函数
        return retry_with_backoff(_get_members)
    except Exception as e:
        # 如果所有重试都失败，打印错误并返回空列表
        print(f"    ❌ 最终抓取成员失败: {e}", end="")
        return []

# --- 主函数 ---

def main():
    try:
        gl = gitlab.Gitlab(V14_URL, private_token=V14_ADMIN_TOKEN)
        gl.auth()
        print(f"✅ 成功连接到源 GitLab: {V14_URL}")
    except Exception as e:
        print(f"❌ 连接到 v14 实例失败: {e}")
        sys.exit(1)

    print("\n📋 抓取项目成员角色...")
    
    try:
        projects = gl.projects.list(all=True)
        print(f"  📊 发现了 {len(projects)} 个项目，开始抓取成员信息...")
    except Exception as e:
        print(f"❌ 抓取项目列表失败: {e}")
        sys.exit(1)

    # 使用字典存储，键为项目ID，值为成员列表
    all_members_data = {}
    total_projects = len(projects)
    successful_projects = 0
    failed_projects = 0

    for i, project in enumerate(projects):
        project_name = safe_get(project, 'name_with_namespace', f'Unknown (ID: {project.id})')
        print(f"\n[{i+1}/{total_projects}] 正在处理项目: {project_name}")
        
        try:
            # 获取完整项目对象（有时需要）
            full_project = gl.projects.get(project.id)
            
            print("    👥 抓取成员...", end="")
            members = get_project_members(full_project)
            
            # 无论成员列表是否为空，都记录
            all_members_data[project.id] = members
            print(f" 找到 {len(members)} 个成员")
            successful_projects += 1
        
        except Exception as e:
            print(f"    ❌ 处理项目 {project_name} 失败: {e}")
            # 记录失败，键为项目ID，值为null或错误信息
            all_members_data[project.id] = None
            failed_projects += 1

    print(f"\n📊 项目处理完成统计:")
    print(f"  ✅ 成功: {successful_projects} 个")
    print(f"  ❌ 失败: {failed_projects} 个")

    # --- 保存到文件 ---
    print(f"\n💾 正在将数据保存到 {OUTPUT_FILE}...")
    
    final_export = {
        "export_info": {
            "source_url": V14_URL,
            "export_time": datetime.now().isoformat(),
            "description": "Export of project members and their roles."
        },
        "project_members": all_members_data
    }

    try:
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(final_export, f, indent=2, ensure_ascii=False)
        print(f"🎉 成功保存！数据已写入: {OUTPUT_FILE}")
    except Exception as e:
        print(f"❌ 写入文件失败: {e}")

if __name__ == "__main__":
    main()