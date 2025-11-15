#!/usr/bin/env python
# -*- coding: utf-8 -*-

import gitlab
import json
import sys
import subprocess
import os
import time
import shutil
from http import HTTPStatus # 导入 HTTPStatus

# --- 1. 配置 ---
# (!!) 强烈建议使用环境变量来配置 (!!)
TARGET_URL='http://localhost:8012'
TARGET_ADMIN_TOKEN=os.getenv('GITLAB_TARGET_TOKEN') 
DEFAULT_PASSWORD='a_very_secure_password_123!'

# TARGET_URL = os.getenv('GITLAB_TARGET_URL', 'http://localhost:8012') 
# TARGET_ADMIN_TOKEN = os.getenv('GITLAB_TARGET_TOKEN') 
# DEFAULT_PASSWORD = os.getenv('GITLAB_DEFAULT_PASS', 'a_very_secure_password_123!') 

INPUT_FILE = 'gitlab_data.json' # (!!) 确保这是 grabber.py 生成的文件
TEMP_GIT_DIR = './temp_repo_clones'
# ---

# 帮助函数，用于执行 Git 命令
def run_git_command(command, cwd=None):
    print(f"  [Git] 运行: {' '.join(command)}")
    try:
        result = subprocess.run(command, cwd=cwd, check=True, capture_output=True, text=True, encoding='utf-8')
        print("  [Git] ...成功。")
        return True
    except subprocess.CalledProcessError as e:
        print(f"  [Git] ❌ 失败: {e.stderr}")
        return False

def get_sudo_gitlab(username, user_map, admin_token, url):
    """辅助函数：获取一个模拟用户的Gitlab实例"""
    user = user_map.get(username)
    if not user:
        print(f"    > 警告: 找不到用户 {username}，将使用 admin。")
        user = user_map['root']
    
    # (!!) 启用自动重试
    return gitlab.Gitlab(url, private_token=admin_token, sudo=user.id, retry_transient_errors=True)

def main():
    # --- 0. 检查配置 ---
    if not TARGET_ADMIN_TOKEN:
        print("❌ 错误: 环境变量 'GITLAB_TARGET_TOKEN' 未设置。")
        print("请运行: export GITLAB_TARGET_TOKEN='your_admin_token'")
        sys.exit(1)
        
    if not os.path.exists(INPUT_FILE):
        print(f"❌ 错误: 未找到 {INPUT_FILE}。")
        print("请先运行 grabber.py，或确保文件名正确。")
        sys.exit(1)

    # --- 2. 加载数据并连接 ---
    print(f"正在从 {INPUT_FILE} 加载数据...")
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    print(f"  > 成功加载 {len(data['users'])} 个用户, {len(data['groups'])} 个组, {len(data['projects'])} 个项目。")
    
    try:
        # (!!) 启用自动重试
        gl = gitlab.Gitlab(TARGET_URL, private_token=TARGET_ADMIN_TOKEN, retry_transient_errors=True)
        gl.auth()
        print(f"✅ 成功连接到目标 GitLab: {TARGET_URL}")
    except Exception as e:
        print(f"❌ 连接到目标实例失败: {e}")
        sys.exit(1)

    # 准备 Git 临时目录
    if os.path.exists(TEMP_GIT_DIR):
        shutil.rmtree(TEMP_GIT_DIR)
    os.makedirs(TEMP_GIT_DIR, exist_ok=True)
    
    # 映射: username -> user object
    created_users = {} 
    # 映射: full_path -> group object
    created_groups = {} 

    # --- 3. 阶段 1: 创建用户 ---
    print("\n--- 阶段 1: 创建用户 ---")
    try:
        created_users['root'] = gl.users.list(username='root')[0]
    except Exception as e:
        print(f"❌ 无法获取 'root' 用户: {e}")
        sys.exit(1)

    for user_data in data['users']:
        username = user_data['username']
        try:
            user = gl.users.create({
                'email': user_data['email'] or f"{username}@example.com", # 确保邮箱不为空
                'username': username,
                'name': user_data['name'],
                'password': DEFAULT_PASSWORD,
                'skip_confirmation': True
            })
            created_users[username] = user
            print(f"  > 创建用户: {username}")
        except gitlab.exceptions.GitlabCreateError as e:
            if e.response_code == HTTPStatus.CONFLICT or 'has already been taken' in str(e):
                print(f"  > 用户 {username} 已存在，正在获取...")
                created_users[username] = gl.users.list(username=username)[0]
            else:
                print(f"  > ❌ 创建用户 {username} 失败: {e}")
    
    print(f"✅ 用户创建完毕。总共 {len(created_users)} 个用户 (包括 root)。")

    # --- (新) 阶段 2: 创建组 ---
    # 满足需求 2: 解决"Group 命名空间"问题
    print("\n--- 阶段 2: 创建组 ---")
    # TODO: 目前只支持顶级组创建，后续可以迭代支持嵌套组 (通过 parent_id)
    for group_data in data['groups']:
        full_path = group_data['full_path']
        try:
            group = gl.groups.create({
                'name': group_data['name'],
                'path': group_data['path'],
                'description': group_data['description'],
                'visibility': group_data['visibility']
                # 'parent_id': group_data.get('parent_id') # 以后可以支持
            })
            created_groups[full_path] = group
            print(f"  > 创建组: {full_path}")
        except gitlab.exceptions.GitlabCreateError as e:
            if e.response_code == HTTPStatus.CONFLICT or 'has already been taken' in str(e):
                print(f"  > 组 {full_path} 已存在，正在获取...")
                created_groups[full_path] = gl.groups.get(full_path)
            else:
                print(f"  > ❌ 创建组 {full_path} 失败: {e}")
    print(f"✅ 组创建完毕。")


    # --- 4. 阶段 3: 创建项目和迁移数据 ---
    print("\n--- 阶段 3: 创建项目和迁移数据 ---")
    
    for project_data in data['projects']:
        project_name = project_data['name']
        print(f"\n处理项目: {project_name} (源路径: {project_data['namespace_full_path']}/{project_data['path']})")
        
        new_project = None
        
        try:
            # 4.1 (重构) 创建项目 (处理命名空间)
            # 满足需求 2: 解决"Group 命名空间"问题
            namespace_kind = project_data.get('namespace_kind')
            namespace_full_path = project_data.get('namespace_full_path')
            
            project_payload = {
                'name': project_data['name'],
                'path': project_data['path'],
                'visibility': project_data['visibility'],
                'description': project_data['description'],
                'wiki_enabled': project_data.get('wiki_enabled', True),
                'issues_enabled': project_data.get('issues_enabled', True),
                'merge_requests_enabled': project_data.get('merge_requests_enabled', True),
            }

            if namespace_kind == 'group':
                group = created_groups.get(namespace_full_path)
                if group:
                    project_payload['namespace_id'] = group.id
                    print(f"  > 准备在组 '{namespace_full_path}' 中创建...")
                else:
                    print(f"  > ❌ 找不到组: {namespace_full_path}，将在 Admin (root) 下创建。")
            elif namespace_kind == 'user':
                owner = created_users.get(namespace_full_path)
                if owner:
                    # 在旧版 GitLab (v12) 中，你可能需要 'user_id'
                    # 在新版 GitLab (v13+) 中，'namespace_id' 是首选
                    project_payload['namespace_id'] = owner.id
                    print(f"  > 准备在用户 '{namespace_full_path}' 中创建...")
                else:
                    print(f"  > ❌ 找不到用户: {namespace_full_path}，将在 Admin (root) 下创建。")
            
            new_project = gl.projects.create(project_payload)
            print(f"  > 4.1 项目已创建: {new_project.name_with_namespace}")

        except gitlab.exceptions.GitlabCreateError as e:
            if e.response_code == HTTPStatus.CONFLICT or 'has already been taken' in str(e):
                print(f"  > 项目 {project_name} 已存在，正在获取...")
                # 构造路径 (这可能不完美，但通常有效)
                project_path = f"{project_payload.get('namespace_id', 'root')}/{project_data['path']}"
                try:
                    new_project = gl.projects.get(f"{namespace_full_path}/{project_data['path']}")
                except:
                    print(f"  > ❌ 无法获取已存在的项目 {project_path}，跳过此项目。")
                    continue
            else:
                print(f"  > ❌ 创建项目 {project_name} 失败: {e}")
                continue
        
        # --- 4.2 迁移 Git 数据 (Clone & Push Mirror) ---
        # 满足需求 3: 解决"Git Clone 认证"问题
        print("  > 4.2 正在迁移 Git 仓库...")
        # (!!) 使用新的 'authed_http_url_to_repo'
        source_url = project_data['authed_http_url_to_repo'] 
        
        # 将 Admin Token 注入目标 URL 以进行推送
        target_url = new_project.http_url_to_repo.replace('http://', f'http://oauth2:{TARGET_ADMIN_TOKEN}@')
        local_path = os.path.join(TEMP_GIT_DIR, new_project.path)

        if not run_git_command(['git', 'clone', '--mirror', source_url, local_path]):
            print(f"  > ❌ 克隆失败 (可能为空仓库)，跳过 Git 迁移。")
            git_push_failed = True
        else:
            git_push_failed = not run_git_command(['git', 'push', '--mirror', target_url], cwd=local_path)
            print("  > Git 仓库迁移完毕。")

        # --- 4.3 (重构) 迁移项目成员 (带角色) ---
        # 满足需求 4: 解决“原始角色丢失”问题
        print("  > 4.3 正在迁移项目成员 (带原始角色)...")
        for member_data in project_data.get('members', []):
            username = member_data['username']
            user = created_users.get(username)
            if not user:
                print(f"    > 警告: 找不到成员 {username}，跳过。")
                continue
            
            # 检查是否为项目所有者 (已通过 'namespace_id' 添加)
            if new_project.owner and user.id == new_project.owner['id']:
                print(f"    > {username} 是所有者，跳过。")
                continue

            try:
                new_project.members.create({
                    'user_id': user.id,
                    'access_level': member_data['access_level'] # (!!) 使用抓取到的原始角色
                })
                print(f"    > 添加成员: {username} (Level: {member_data['access_level']})")
            except gitlab.exceptions.GitlabCreateError as e:
                if 'already exists' in str(e):
                    pass # 成员已存在，正常
                else:
                    print(f"    > ❌ 添加成员 {username} 失败: {e}")
        
        time.sleep(1) # 等待权限生效

        # --- 4.4 (新) 迁移 Labels ---
        # 满足需求 1: 填充数据
        print("  > 4.4 正在迁移 Labels...")
        for label_data in project_data.get('labels', []):
            try:
                new_project.labels.create({
                    'name': label_data['name'],
                    'color': label_data['color'],
                    'description': label_data['description']
                })
            except gitlab.exceptions.GitlabCreateError as e:
                 if 'already been taken' in str(e):
                     print(f"    > 标签 '{label_data['name']}' 已存在。")
                 else:
                     print(f"    > ❌ 创建标签 '{label_data['name']}' 失败: {e}")

        # --- 4.5 (新) 迁移 Milestones ---
        # 满足需求 1: 填充数据
        print("  > 4.5 正在迁移 Milestones...")
        for ms_data in project_data.get('milestones', []):
            try:
                new_project.milestones.create({
                    'title': ms_data['title'],
                    'description': ms_data['description'],
                    'due_date': ms_data['due_date'] or None,
                    'start_date': ms_data['start_date'] or None
                })
            except Exception as e:
                print(f"    > ❌ 创建里程碑 '{ms_data['title']}' 失败: {e}")

        # --- 4.6 (新) 迁移 Wiki Pages ---
        # 满足需求 1: 填充数据
        if project_data.get('wiki_enabled', False) and project_data.get('wiki_pages'):
            print("  > 4.6 正在迁移 Wiki Pages...")
            for page_data in project_data.get('wiki_pages', []):
                try:
                    new_project.wikis.create({
                        'title': page_data['title'],
                        'content': page_data['content'] or "(空内容)",
                        'format': page_data['format']
                    })
                except Exception as e:
                    print(f"    > ❌ 创建 Wiki 页面 '{page_data['title']}' 失败: {e}")

        # --- 4.7 迁移 Issues (带模拟) ---
        print("  > 4.7 正在迁移 Issues...")
        for issue_data in project_data.get('issues', []):
            try:
                gl_as_author = get_sudo_gitlab(issue_data['author_username'], created_users, TARGET_ADMIN_TOKEN, TARGET_URL)
                project_as_author = gl_as_author.projects.get(new_project.id, lazy=False)
                
                assignee_ids = [created_users[u].id for u in issue_data['assignee_usernames'] if u in created_users]
                
                new_issue = project_as_author.issues.create({
                    'title': issue_data['title'],
                    'description': issue_data['description'],
                    'assignee_ids': assignee_ids,
                    'labels': issue_data['labels'], # (新) 添加标签
                    'milestone': issue_data['milestone'], # (新) 添加里程碑
                    'created_at': issue_data['created_at'] # (新) 保留创建时间
                })
                print(f"    > 已创建 Issue (模拟 {issue_data['author_username']}): {new_issue.title[:30]}...")

                if issue_data['state'] == 'closed':
                    new_issue.state_event = 'close'
                    new_issue.save()

                # 迁移评论 (带模拟)
                for comment_data in issue_data['comments']:
                    gl_as_commenter = get_sudo_gitlab(comment_data['author_username'], created_users, TARGET_ADMIN_TOKEN, TARGET_URL)
                    issue_as_commenter = gl_as_commenter.projects.get(new_project.id, lazy=False).issues.get(new_issue.iid, lazy=False)
                    
                    issue_as_commenter.notes.create({
                        'body': comment_data['body'],
                        'created_at': comment_data['created_at'] # (新) 保留创建时间
                    })
                        
            except Exception as e:
                print(f"    > ❌ 迁移 Issue '{issue_data['title']}' 失败: {e}")

        # --- 4.8 迁移 Merge Requests (带模拟) ---
        if git_push_failed:
            print("  > 4.8 ❌ 跳过 Merge Requests 迁移 (因为 Git 仓库迁移失败)")
        else:
            print("  > 4.8 正在迁移 Merge Requests...")
            for mr_data in project_data.get('merge_requests', []):
                try:
                    gl_as_author = get_sudo_gitlab(mr_data['author_username'], created_users, TARGET_ADMIN_TOKEN, TARGET_URL)
                    project_as_author = gl_as_author.projects.get(new_project.id, lazy=False)

                    new_mr = project_as_author.mergerequests.create({
                        'title': mr_data['title'],
                        'description': mr_data['description'],
                        'source_branch': mr_data['source_branch'],
                        'target_branch': mr_data['target_branch'],
                        'labels': mr_data['labels'], # (新)
                        'milestone': mr_data['milestone'], # (新)
                        'created_at': mr_data['created_at'] # (新)
                    })
                    print(f"    > 已创建 MR (模拟 {mr_data['author_username']}): {new_mr.title[:30]}...")

                    # 迁移评论 (带模拟)
                    for comment_data in mr_data['comments']:
                        gl_as_commenter = get_sudo_gitlab(comment_data['author_username'], created_users, TARGET_ADMIN_TOKEN, TARGET_URL)
                        mr_as_commenter = gl_as_commenter.projects.get(new_project.id, lazy=False).mergerequests.get(new_mr.iid, lazy=False)
                        mr_as_commenter.notes.create({
                            'body': comment_data['body'],
                            'created_at': comment_data['created_at'] # (新)
                        })

                    # 处理 MR 状态 (必须在创建评论后)
                    if mr_data['state'] == 'merged':
                        try:
                            # 必须由有权限的人（例如 admin）来 merge
                            admin_mr_instance = gl.projects.get(new_project.id, lazy=False).mergerequests.get(new_mr.iid, lazy=False)
                            admin_mr_instance.merge(merge_when_pipeline_succeeds=False) # 强制合并
                            print(f"    > 已合并 MR: {new_mr.title[:30]}...")
                        except Exception as merge_error:
                             print(f"    > 警告: 自动合并 MR 失败 (可能是冲突或分支保护): {merge_error}")
                    elif mr_data['state'] == 'closed':
                        admin_mr_instance = gl.projects.get(new_project.id, lazy=False).mergerequests.get(new_mr.iid, lazy=False)
                        admin_mr_instance.state_event = 'close'
                        admin_mr_instance.save()

                except Exception as e:
                    print(f"    > ❌ 迁移 MR '{mr_data['title']}' 失败: {e}")
                    print("    > (这通常是因为源分支或目标分支在 Git 迁移中丢失)")

    print("\n--- ✅✅✅ 填充脚本执行完毕 ---")
    # 清理临时目录
    try:
        shutil.rmtree(TEMP_GIT_DIR)
        print(f"🧹 已清理临时目录: {TEMP_GIT_DIR}")
    except Exception as e:
        print(f"🧹 清理临时目录失败: {e}")

if __name__ == "__main__":
    main()