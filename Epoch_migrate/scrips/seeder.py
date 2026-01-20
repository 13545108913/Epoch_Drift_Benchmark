#!/usr/bin/env python
# -*- coding: utf-8 -*-

import gitlab
import json
import sys
import subprocess
import os
import time
import shutil
import random
from http import HTTPStatus
from urllib.parse import urlparse, urlunparse

# --- 1. 配置 ---
TARGET_URL = 'http://localhost:8080'
TARGET_ADMIN_TOKEN = '67_a6Zb7k9x1sdnKCoge'
DEFAULT_PASSWORD = 'a_very_secure_password_123!'

# (!!) 确保文件名正确
INPUT_FILE = 'gitlab_data_20251116_010817.json'  # (!!) grabber.py 的输出
MEMBERS_FILE = 'gitlab_member_roles_20251116_184319.json'  # (!!) [新] grabber_members.py 的输出

TEMP_GIT_DIR = './temp_repo_clones'

SOURCE_HOST_OVERRIDE = '10.22.35.100'
SOURCE_TOKEN_OVERRIDE = 'glpat-xroTqUxGzZav3qAZYo_8'

# --- [新] 断点续传配置 ---
# 如果脚本中断，请在此处填写中断项目的 'path' (!! 不是全名 !!)
# 脚本将跳过此项目【之前】的所有项目
# (!!) 确保已在 GitLab UI 上手动删除了这个中断的项目 (!!)
SKIP_UNTIL_PROJECT_PATH = 'bootstrap'  # 你的日志显示卡在 'bootstrap'
# 设为 None 或 '' 将从头开始运行
# ---

# 帮助函数，用于执行 Git 命令


def run_git_command(command, cwd=None):
    print(f"   [Git] 运行: {' '.join(command)}")
    try:
        result = subprocess.run(command, cwd=cwd, check=True, capture_output=True, text=True, encoding='utf-8')
        print("   [Git] ...成功。")
        return True
    except subprocess.CalledProcessError as e:
        print(f"   [Git] ❌ 失败: {e.stderr}")
        return False


def get_sudo_gitlab(username, user_map, admin_token, url):
    """辅助函数：获取一个模拟用户的Gitlab实例"""
    user = user_map.get(username)

    if not user:
        print(f"     > 警告: 找不到用户 {username}，将使用 admin (root)。")
        user = user_map['root']

    gl_instance = gitlab.Gitlab(url, private_token=admin_token, retry_transient_errors=True)

    if user.username != 'root':
        gl_instance.headers = {'SUDO': str(user.id)}

    return gl_instance


def main():
    # --- 0. 检查配置 ---
    if not TARGET_ADMIN_TOKEN:
        print("❌ 错误: 环境变量 'GITLAB_TARGET_TOKEN' 未设置。")
        sys.exit(1)

    if not os.path.exists(INPUT_FILE):
        print(f"❌ 错误: 未找到 {INPUT_FILE}。")
        print("请先运行 grabber.py，或确保文件名正确。")
        sys.exit(1)

    # --- 2. 加载数据并连接 ---
    print(f"正在从 {INPUT_FILE} 加载数据...")
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    print(f"   > 成功加载 {len(data['users'])} 个用户, {len(data['projects'])} 个项目。")

    # --- [新] 2.b 加载成员数据 ---
    print(f"正在从 {MEMBERS_FILE} 加载成员数据...")
    all_members_data = {}
    if not os.path.exists(MEMBERS_FILE):
        print(f"⚠️ 警告: 未找到成员文件 {MEMBERS_FILE}。")
        print("         将跳过项目成员的迁移。")
    else:
        try:
            with open(MEMBERS_FILE, 'r', encoding='utf-8') as f:
                members_data_file = json.load(f)
                all_members_data = members_data_file.get('project_members', {})
                print(f"   > 成功加载 {len(all_members_data)} 个项目的成员信息。")
        except Exception as e:
            print(f"⚠️ 警告: 加载成员文件 {MEMBERS_FILE} 失败: {e}")
            print("         将跳过项目成员的迁移。")

    try:
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
                'email': user_data['email'] or f"{username}@example.com",
                'username': username,
                'name': user_data['name'],
                'password': DEFAULT_PASSWORD,
                'skip_confirmation': True
            })
            created_users[username] = user
            print(f"   > 创建用户: {username}")
        except gitlab.exceptions.GitlabCreateError as e:
            if e.response_code == HTTPStatus.CONFLICT or 'has already been taken' in str(e):
                print(f"   > 用户 {username} 已存在，正在获取...")
                created_users[username] = gl.users.list(username=username)[0]
            else:
                print(f"   > ❌ 创建用户 {username} 失败: {e}")

    print(f"✅ 用户创建完毕。总共 {len(created_users)} 个用户 (包括 root)。")

    # --- 4. 阶段 2: 创建项目和迁移数据 ---
    print("\n--- 阶段 2: 创建项目和迁移数据 ---")

    # --- [新] 恢复逻辑初始化 ---
    # 如果 SKIP_UNTIL_PROJECT_PATH 为空，则 processing_started 立即为 True
    processing_started = (SKIP_UNTIL_PROJECT_PATH is None) or (SKIP_UNTIL_PROJECT_PATH == '')
    if not processing_started:
        print(f"⚠️  恢复模式启动：将跳过所有项目，直到并包括 '{SKIP_UNTIL_PROJECT_PATH}'")
    # ---

    for project_data in data['projects']:
        project_name = project_data['name']
        project_path = project_data['path'] # 获取 project 'path'
        namespace_path = project_data.get('namespace', 'root')
        full_path_for_log = f"{namespace_path}/{project_path}"

        # --- [新] 检查是否跳过 ---
        if not processing_started:
            if project_path == SKIP_UNTIL_PROJECT_PATH:
                # 找到了我们标记的项目
                print(f"--- ⏩ 找到了 '{SKIP_UNTIL_PROJECT_PATH}'，跳过它。将从下一个项目开始处理。 ---")
                processing_started = True # 设置标志，以便下一个循环开始处理
            else:
                # 这是标记项目之前的项目
                print(f"--- ⏩ 跳过: {full_path_for_log} ---")

            # 无论哪种情况（在标记之前，或就是标记本身），都跳过当前循环
            continue
        # --- [新] 逻辑结束 ---

        # 只有在 processing_started = True 并且 project_path != SKIP_UNTIL_PROJECT_PATH 之后
        # 这里的代码才会执行
        print(f"\n--- ✅ 恢复执行: 处理 {full_path_for_log} ---")

        # 你的原始处理逻辑从这里开始
        print(f"处理项目: {project_name} (源路径: {full_path_for_log})")

        new_project = None

        try:
            # 2.1 创建项目
            project_payload = {
                'name': project_data['name'],
                'path': project_data['path'],
                'visibility': project_data['visibility'],
                'description': project_data['description'],
                'wiki_enabled': project_data.get('wiki_enabled', True),
                'issues_enabled': project_data.get('issues_enabled', True),
                'merge_requests_enabled': project_data.get('merge_requests_enabled', True),
            }

            owner = created_users.get(namespace_path)
            if owner:
                project_payload['namespace_id'] = owner.id
                print(f"   > 准备在用户 '{namespace_path}' 中创建...")
            else:
                print(f"   > 警告: 找不到用户命名空间: {namespace_path}，将在 Admin (root) 下创建。")

            new_project = gl.projects.create(project_payload)
            print(f"   > 2.1 项目已创建: {new_project.name_with_namespace}")

        except gitlab.exceptions.GitlabCreateError as e:
            if e.response_code == HTTPStatus.CONFLICT or 'has already been taken' in str(e):
                print(f"   > 项目 {project_name} 已存在，正在获取...")
                project_path = f"{namespace_path}/{project_data['path']}"
                try:
                    new_project = gl.projects.get(project_path)
                except Exception as e_get:
                    print(f"   > ❌ 无法获取已存在的项目 {project_path} (错误: {e_get})，跳过此项目。")
                    continue
            else:
                print(f"   > ❌ 创建项目 {project_name} 失败: {e}")
                continue

        # --- 2.2 迁移 Git 数据 (Clone & Push Mirror) ---
        print("   > 2.2 正在迁移 Git 仓库...")
        source_url = project_data['authed_http_url_to_repo']

        if SOURCE_HOST_OVERRIDE or SOURCE_TOKEN_OVERRIDE:
            try:
                url_parts = urlparse(source_url)
                new_netloc = url_parts.netloc

                if SOURCE_HOST_OVERRIDE and 'localhost' in new_netloc:
                    new_netloc = new_netloc.replace('localhost', SOURCE_HOST_OVERRIDE)
                    print(f"   [Git] 已重定向源 Host 到: {SOURCE_HOST_OVERRIDE}")

                if SOURCE_TOKEN_OVERRIDE:
                    try:
                        auth_part, host_part = new_netloc.split('@', 1)
                        old_token = auth_part.split(':', 1)[-1]

                        if old_token != SOURCE_TOKEN_OVERRIDE:
                            new_auth_part = f"oauth2:{SOURCE_TOKEN_OVERRIDE}"
                            new_netloc = f"{new_auth_part}@{host_part}"
                            print(f"   [Git] 已重定向源 Token。")
                    except Exception as e_token:
                        print(f"   [Git] ❌ 警告: 覆盖 Token 失败 (格式错误?): {e_token}")

                new_url_parts = (url_parts.scheme, new_netloc, url_parts.path, url_parts.params, url_parts.query, url_parts.fragment)
                source_url = urlunparse(new_url_parts)

            except Exception as e:
                print(f"   [Git] ❌ 警告: 重定向 source_url 失败: {e}")

        url_parts = urlparse(TARGET_URL)
        netloc = f'oauth2:{TARGET_ADMIN_TOKEN}@{url_parts.hostname}'
        if url_parts.port:
            netloc += f':{url_parts.port}'
        git_path = f"/{new_project.path_with_namespace}.git"
        target_url_parts = (url_parts.scheme, netloc, git_path, '', '', '')
        target_url = urlunparse(target_url_parts)
        local_path = os.path.join(TEMP_GIT_DIR, new_project.path)

        if not run_git_command(['git', 'clone', '--mirror', source_url, local_path]):
            print(f"   > ❌ 克隆失败 (可能为空仓库)，跳过 Git 迁移。")
            git_push_failed = True
        else:
            git_push_failed = not run_git_command(['git', 'push', '--mirror', target_url], cwd=local_path)
            print("   > Git 仓库迁移完毕。")

        # --- [新] 2.3 迁移项目成员 ---
        print("   > 2.3 正在迁移项目成员...")
        original_project_id = project_data.get('id')

        # 从加载的成员数据中获取此项目的成员列表
        # .get(str(original_project_id)) 因为 JSON 键总是字符串
        member_list = all_members_data.get(str(original_project_id))

        if member_list is None:
            print("     > 警告: 此项目的成员数据在源抓取时失败 (记录为 null)，跳过。")
        elif not member_list:
            print("     > (项目没有显式成员，跳过)")
        else:
            added_count = 0
            for member_info in member_list:
                username = member_info.get('username')
                access_level = member_info.get('access_level')

                if not username or not access_level:
                    print(f"     > 警告: 成员数据不完整，跳过: {member_info}")
                    continue

                # 从 'created_users' 映射中找到新目标系统中的用户
                user_to_add = created_users.get(username)

                if not user_to_add:
                    print(f"     > 警告: 找不到用户 {username}，无法添加为成员。")
                    continue

                # 检查是否是项目所有者 (Owner, 50)
                # 'Owner' (50) 通常在创建项目时自动添加，无需再次添加
                if new_project.owner and user_to_add.id == new_project.owner.get('id') and access_level == 50:
                    print(f"     > (用户 {username} 是所有者，已自动添加)")
                    continue

                try:
                    # 添加成员
                    new_project.members.create({
                        'user_id': user_to_add.id,
                        'access_level': access_level
                    })
                    added_count += 1
                except gitlab.exceptions.GitlabCreateError as e:
                    if e.response_code == HTTPStatus.CONFLICT or 'already exists' in str(e):
                        print(f"     > (用户 {username} 已是成员)")
                    else:
                        print(f"     > ❌ 添加 {username} (Level: {access_level}) 失败: {e}")
                except Exception as e:
                    print(f"     > ❌ 添加 {username} 失败 (意外错误): {e}")

            print(f"     > 成功添加 {added_count} / {len(member_list)} 个成员。")

        # --- 2.4 [重编号] 迁移 Labels ---
        print("   > 2.4 正在迁移 Labels...")
        for label_data in project_data.get('labels', []):
            try:
                new_project.labels.create({
                    'name': label_data['name'],
                    'color': label_data['color'],
                    'description': label_data['description']
                })
            except gitlab.exceptions.GitlabCreateError as e:
                if 'already been taken' in str(e):
                    print(f"     > 标签 '{label_data['name']}' 已存在。")
                else:
                    print(f"     > ❌ 创建标签 '{label_data['name']}' 失败: {e}")

        # --- 2.5 [重编号] 迁移 Milestones ---
        print("   > 2.5 正在迁移 Milestones...")
        for ms_data in project_data.get('milestones', []):
            try:
                new_project.milestones.create({
                    'title': ms_data['title'],
                    'description': ms_data['description'],
                    'due_date': ms_data['due_date'] or None,
                    'start_date': ms_data['start_date'] or None
                })
            except Exception as e:
                print(f"     > ❌ 创建里程碑 '{ms_data['title']}' 失败: {e}")

        # --- 2.6 [重编号] 迁移 Stars (模拟) ---
        print("   > 2.6 正在迁移 Stars...")
        star_count = project_data.get('stars', {}).get('star_count', 0)

        if star_count > 0:
            available_starrers = [user for username, user in created_users.items() if username != 'root']

            if not available_starrers:
                print("     > 警告: 没有可用于 star 的用户 (除 root 外)。")
            else:
                num_to_star = min(star_count, len(available_starrers))
                print(f"     > 目标 Star: {star_count}。 可用用户: {len(available_starrers)}。 将模拟 {num_to_star} 个用户。")

                users_to_star = random.sample(available_starrers, num_to_star)

                for user in users_to_star:
                    try:
                        gl_as_starer = gitlab.Gitlab(TARGET_URL, private_token=TARGET_ADMIN_TOKEN, retry_transient_errors=True)
                        gl_as_starer.headers = {'SUDO': str(user.id)}

                        project_as_starer = gl_as_starer.projects.get(new_project.id)
                        project_as_starer.star()
                        print(f"     > (模拟 {user.username}) 已 Star 项目。")
                    except Exception as e:
                        if '304 Not Modified' in str(e):
                            print(f"     > (模拟 {user.username}) 已 Star (重跑)。")
                        else:
                            print(f"     > ❌ (模拟 {user.username}) Star 失败: {e}")
        else:
            print("     > 0 Stars，跳过。")

        # --- 2.7 [重编号] 迁移 Wiki Pages ---
        if project_data.get('wiki_enabled', False) and project_data.get('wiki_pages'):
            print("   > 2.7 正在迁移 Wiki Pages...")
            for page_data in project_data.get('wiki_pages', []):
                try:
                    new_project.wikis.create({
                        'title': page_data['title'],
                        'content': page_data['content'] or "(空内容)",
                        'format': page_data['format']
                    })
                except Exception as e:
                    print(f"     > ❌ 创建 Wiki 页面 '{page_data['title']}' 失败: {e}")

        # --- 2.8 [重编号] 迁移 Issues (带模拟) ---
        print("   > 2.8 正在迁移 Issues...")
        for issue_data in project_data.get('issues', []):
            try:
                author_username = issue_data.get('author') or 'root'
                gl_as_author = get_sudo_gitlab(author_username, created_users, TARGET_ADMIN_TOKEN, TARGET_URL)
                project_as_author = gl_as_author.projects.get(new_project.id, lazy=False)

                assignee_ids = [created_users[u].id for u in issue_data.get('assignees', []) if u in created_users]

                new_issue = project_as_author.issues.create({
                    'title': issue_data['title'],
                    'description': issue_data['description'],
                    'assignee_ids': assignee_ids,
                    'labels': issue_data['labels'],
                    'milestone': issue_data['milestone'],
                    'created_at': issue_data['created_at']
                })
                print(f"     > 已创建 Issue (模拟 {author_username}): {new_issue.title[:30]}...")

                if issue_data['state'] == 'closed':
                    new_issue.state_event = 'close'
                    new_issue.save()

                # 迁移评论 (带模拟)
                for comment_data in issue_data['comments']:
                    commenter_username = comment_data.get('author') or 'root'
                    gl_as_commenter = get_sudo_gitlab(commenter_username, created_users, TARGET_ADMIN_TOKEN, TARGET_URL)
                    issue_as_commenter = gl_as_commenter.projects.get(new_project.id, lazy=False).issues.get(new_issue.iid, lazy=False)

                    issue_as_commenter.notes.create({
                        'body': comment_data['body'],
                        'created_at': comment_data['created_at']
                    })

            except Exception as e:
                print(f"     > ❌ 迁移 Issue '{issue_data['title']}' 失败: {e}")

        # --- 2.9 [重编号] 迁移 Merge Requests (带模拟) ---
        if git_push_failed:
            print("   > 2.9 ❌ 跳过 Merge Requests 迁移 (因为 Git 仓库迁移失败)")
        else:
            print("   > 2.9 正在迁移 Merge Requests...")
            for mr_data in project_data.get('merge_requests', []):
                try:
                    author_username = mr_data.get('author') or 'root'
                    gl_as_author = get_sudo_gitlab(author_username, created_users, TARGET_ADMIN_TOKEN, TARGET_URL)
                    project_as_author = gl_as_author.projects.get(new_project.id, lazy=False)

                    new_mr = project_as_author.mergerequests.create({
                        'title': mr_data['title'],
                        'description': mr_data['description'],
                        'source_branch': mr_data['source_branch'],
                        'target_branch': mr_data['target_branch'],
                        'labels': mr_data['labels'],
                        'milestone': mr_data['milestone'],
                        'created_at': mr_data['created_at']
                    })
                    print(f"     > 已创建 MR (模拟 {author_username}): {new_mr.title[:30]}...")

                    # 迁移评论 (带模拟)
                    for comment_data in mr_data['comments']:
                        commenter_username = comment_data.get('author') or 'root'
                        gl_as_commenter = get_sudo_gitlab(commenter_username, created_users, TARGET_ADMIN_TOKEN, TARGET_URL)
                        mr_as_commenter = gl_as_commenter.projects.get(new_project.id, lazy=False).mergerequests.get(new_mr.iid, lazy=False)
                        mr_as_commenter.notes.create({
                            'body': comment_data['body'],
                            'created_at': comment_data['created_at']
                        })

                    # 处理 MR 状态 (必须在创建评论后)
                    if mr_data['state'] == 'merged':
                        try:
                            admin_mr_instance = gl.projects.get(new_project.id, lazy=False).mergerequests.get(new_mr.iid, lazy=False)
                            admin_mr_instance.merge(merge_when_pipeline_succeeds=False)  # 强制合并
                            print(f"     > 已合并 MR: {new_mr.title[:30]}...")
                        except Exception as merge_error:
                            print(f"     > 警告: 自动合并 MR 失败 (可能是冲突或分支保护): {merge_error}")
                    elif mr_data['state'] == 'closed':
                        admin_mr_instance = gl.projects.get(new_project.id, lazy=False).mergerequests.get(new_mr.iid, lazy=False)
                        admin_mr_instance.state_event = 'close'
                        admin_mr_instance.save()

                except Exception as e:
                    print(f"     > ❌ 迁移 MR '{mr_data['title']}' 失败: {e}")
                    print("     > (这通常是因为源分支或目标分支在 Git 迁移中丢失)")

    print("\n--- ✅✅✅ 填充脚本执行完毕 ---")

    # 清理临时目录
    try:
        print(f"正在清理临时目录: {TEMP_GIT_DIR}")
        shutil.rmtree(TEMP_GIT_DIR)
        print("清理完毕。")
    except Exception as e:
        print(f"警告: 清理临时目录失败: {e}")


if __name__ == "__main__":
    main()