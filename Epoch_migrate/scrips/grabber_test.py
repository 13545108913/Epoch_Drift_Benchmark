#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import gitlab
import json
import sys
from datetime import datetime

# --- 配置 ---
V14_URL = 'http://localhost:8023' 
V14_ADMIN_TOKEN = os.getenv('V14_ADMIN_TOKEN')
# --- 

OUTPUT_FILE = f'gitlab_data_TEST_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'

# 测试配置
TEST_CONFIG = {
    "max_projects": 2,           # 最多抓取2个项目
    "max_issues_per_project": 3,  # 每个项目最多3个issue
    "max_mrs_per_project": 2,     # 每个项目最多2个MR
    "max_pipelines_per_project": 2, # 每个项目最多2个流水线
    "max_wiki_pages_per_project": 2, # 每个项目最多2个wiki页面
    "max_comments_per_issue": 2,  # 每个issue最多2条评论
    "max_comments_per_mr": 2,     # 每个MR最多2条评论
    "skip_large_data": True       # 跳过大数据量抓取
}

def safe_get(obj, attr, default=None):
    """安全获取对象属性，处理空值"""
    try:
        value = getattr(obj, attr, default)
        return value if value is not None else default
    except:
        return default

def safe_dict_get(dictionary, key, default=None):
    """安全获取字典值，处理空值"""
    try:
        value = dictionary.get(key, default)
        return value if value is not None else default
    except:
        return default

# --- 抓取器函数 (测试版本) ---

def get_labels(project):
    """获取项目标签 (测试版本)"""
    try:
        labels = project.labels.list(all=True)
        # 限制数量
        limited_labels = list(labels)[:5]
        return [
            {
                "id": safe_get(label, 'id'),
                "name": safe_get(label, 'name', ''),
                "color": safe_get(label, 'color', ''),
                "description": safe_get(label, 'description', '')
            }
            for label in limited_labels
        ]
    except Exception as e:
        print(f" [标签错误: {e}]", end="")
        return []

def get_milestones(project):
    """获取项目里程碑 (测试版本)"""
    try:
        milestones = project.milestones.list(all=True)
        # 限制数量
        limited_milestones = list(milestones)[:3]
        return [
            {
                "id": safe_get(milestone, 'id'),
                "title": safe_get(milestone, 'title', ''),
                "description": safe_get(milestone, 'description', ''),
                "state": safe_get(milestone, 'state', 'active'),
                "due_date": safe_get(milestone, 'due_date', ''),
                "start_date": safe_get(milestone, 'start_date', '')
            }
            for milestone in limited_milestones
        ]
    except Exception as e:
        print(f" [里程碑错误: {e}]", end="")
        return []

def get_members(project):
    """获取项目成员 (测试版本)"""
    try:
        members = project.members.list(all=True)
        # 限制数量
        limited_members = list(members)[:5]
        return [
            {
                "id": safe_get(member, 'id'),
                "username": safe_get(member, 'username', ''),
                "name": safe_get(member, 'name', ''),
                "access_level": safe_get(member, 'access_level', 0)
            }
            for member in limited_members
        ]
    except Exception as e:
        print(f" [成员错误: {e}]", end="")
        return []

def get_pipelines(project):
    """获取CI/CD流水线 (测试版本)"""
    if TEST_CONFIG["skip_large_data"]:
        print(" [跳过流水线]", end="")
        return []
        
    try:
        pipelines = project.pipelines.list(all=True, per_page=TEST_CONFIG["max_pipelines_per_project"])
        pipeline_data = []
        
        for pipeline in pipelines[:TEST_CONFIG["max_pipelines_per_project"]]:
            jobs = []
            try:
                full_pipeline = project.pipelines.get(safe_get(pipeline, 'id'))
                pipeline_jobs = full_pipeline.jobs.list(all=True)
                # 限制job数量
                for job in list(pipeline_jobs)[:3]:
                    jobs.append({
                        "id": safe_get(job, 'id'),
                        "name": safe_get(job, 'name', ''),
                        "stage": safe_get(job, 'stage', ''),
                        "status": safe_get(job, 'status', ''),
                    })
            except Exception as job_error:
                print(f" [任务错误: {job_error}]", end="")
            
            pipeline_data.append({
                "id": safe_get(pipeline, 'id'),
                "status": safe_get(pipeline, 'status', ''),
                "ref": safe_get(pipeline, 'ref', ''),
                "sha": safe_get(pipeline, 'sha', ''),
                "jobs": jobs
            })
        
        return pipeline_data
    except Exception as e:
        print(f" [流水线错误: {e}]", end="")
        return []

def get_wiki_pages(project):
    """获取Wiki页面 (测试版本)"""
    try:
        if not safe_get(project, 'wiki_enabled', False):
            return []
            
        wiki_pages = project.wikis.list(all=True)
        # 限制数量
        limited_wiki_pages = list(wiki_pages)[:TEST_CONFIG["max_wiki_pages_per_project"]]
        wiki_data = []
        
        for wiki_page in limited_wiki_pages:
            try:
                full_page = project.wikis.get(safe_get(wiki_page, 'slug'))
                wiki_data.append({
                    "slug": safe_get(full_page, 'slug', ''),
                    "title": safe_get(full_page, 'title', ''),
                    "format": safe_get(full_page, 'format', 'markdown'),
                    "content": safe_get(full_page, 'content', '')[:500] + "..." if len(safe_get(full_page, 'content', '')) > 500 else safe_get(full_page, 'content', ''),  # 限制内容长度
                })
            except Exception as page_error:
                print(f" [Wiki页面错误: {page_error}]", end="")
                continue
        
        return wiki_data
    except Exception as e:
        print(f" [Wiki错误: {e}]", end="")
        return []

# --- 主函数 ---

def main():
    print("🚀 开始测试数据抓取...")
    print(f"📋 测试配置: {TEST_CONFIG}")
    
    try:
        gl = gitlab.Gitlab(V14_URL, private_token=V14_ADMIN_TOKEN, retry_transient_errors=True)
        gl.auth()
        
        current_user = gl.user
        print(f"✅ 成功连接到源 GitLab (v14): {V14_URL}")
        print(f"✅ 当前用户: {safe_get(current_user, 'username', 'Unknown')}")
        
    except Exception as e:
        print(f"❌ 连接到 v14 实例失败: {e}")
        sys.exit(1)

    data = {
        "export_info": {
            "source_url": V14_URL,
            "export_time": datetime.now().isoformat(),
            "gitlab_version": None,
            "test_config": TEST_CONFIG  # 记录测试配置
        },
        "users": [],
        "groups": [],
        "projects": []
    }

    # 获取GitLab版本信息
    try:
        data["export_info"]["gitlab_version"] = gl.version()
        print(f"✅ GitLab 版本: {data['export_info']['gitlab_version']}")
    except:
        print("⚠️  无法获取GitLab版本信息")

    # --- 抓取用户 (限制数量) ---
    print("\n📋 抓取用户 (测试模式)...")
    try:
        users = gl.users.list(all=True, per_page=10)  # 限制每页数量
        active_users = [u for u in users if safe_get(u, 'state') == 'active' and safe_get(u, 'username') != 'root']
        
        # 限制用户数量
        limited_users = list(active_users)[:5]
        
        for user in limited_users:
            data['users'].append({
                "id": safe_get(user, 'id'),
                "username": safe_get(user, 'username', 'unknown_username'),
                "name": safe_get(user, 'name', ''),
                "email": safe_get(user, 'email', ''),
                "state": safe_get(user, 'state', 'unknown')
            })
        print(f"  ✅ 抓取了 {len(data['users'])} 个活动用户 (测试限制)")
        
    except Exception as e:
        print(f"❌ 抓取用户时出错: {e}")

    # --- 抓取组 (限制数量) ---
    print("\n🏢 抓取组 (测试模式)...")
    try:
        groups = gl.groups.list(all=True, per_page=5)  # 限制数量
        limited_groups = list(groups)[:3]
        
        for group in limited_groups:
            data['groups'].append({
                "id": safe_get(group, 'id'),
                "name": safe_get(group, 'name', ''),
                "path": safe_get(group, 'path', ''),
                "full_path": safe_get(group, 'full_path', ''),
                "description": safe_get(group, 'description', ''),
                "visibility": safe_get(group, 'visibility', 'private'),
                "parent_id": safe_get(group, 'parent_id')
            })
        print(f"  ✅ 抓取了 {len(data['groups'])} 个组 (测试限制)")
    except Exception as e:
        print(f"❌ 抓取组时出错: {e}")

    # --- 抓取项目 (限制数量) ---
    print("\n📦 抓取项目 (测试模式)...")
    try:
        projects = gl.projects.list(all=True, per_page=TEST_CONFIG["max_projects"] + 2)
        limited_projects = list(projects)[:TEST_CONFIG["max_projects"]]
        
        print(f"  📊 发现了 {len(projects)} 个项目，测试抓取 {len(limited_projects)} 个...")

        for i, project in enumerate(limited_projects):
            print(f"\n[{i+1}/{len(limited_projects)}] 正在处理项目: {safe_get(project, 'name_with_namespace', 'Unknown Project')}")
            
            try:
                full_project = gl.projects.get(project.id, lazy=False)
                
                # 构造认证URL
                authed_source_url = full_project.http_url_to_repo.replace('http://', f'http://oauth2:{V14_ADMIN_TOKEN}@')
                
                namespace_info = safe_get(full_project, 'namespace', {})
                namespace_kind = safe_dict_get(namespace_info, 'kind', 'user')
                namespace_full_path = safe_dict_get(namespace_info, 'full_path', 'unknown_namespace')

                project_data = {
                    "id": safe_get(full_project, 'id'),
                    "name": safe_get(full_project, 'name', 'unknown_project'),
                    "path": safe_get(full_project, 'path', 'unknown_path'),
                    "namespace_kind": namespace_kind,
                    "namespace_full_path": namespace_full_path,
                    "visibility": safe_get(full_project, 'visibility', 'private'),
                    "description": safe_get(full_project, 'description', ''),
                    "web_url": safe_get(full_project, 'web_url', ''),
                    "authed_http_url_to_repo": authed_source_url,
                    "http_url_to_repo": safe_get(full_project, 'http_url_to_repo', ''),
                    "created_at": safe_get(full_project, 'created_at', ''),
                    "labels": [],
                    "milestones": [],
                    "members": [],
                    "pipelines": [],
                    "wiki_pages": [],
                    "issues": [],
                    "merge_requests": []
                }

                # 快速抓取各种数据 (都有限制)
                print(f"  🏷️  抓取 Labels...", end="")
                project_data['labels'] = get_labels(full_project)
                print(f" {len(project_data['labels'])} 个")

                print(f"  🎯 抓取 Milestones...", end="")
                project_data['milestones'] = get_milestones(full_project)
                print(f" {len(project_data['milestones'])} 个")
                
                print(f"  👥 抓取 Members...", end="")
                project_data['members'] = get_members(full_project)
                print(f" {len(project_data['members'])} 个")

                print(f"  🔧 抓取 CI/CD Pipelines...", end="")
                project_data['pipelines'] = get_pipelines(full_project)
                print(f" {len(project_data['pipelines'])} 个")

                print(f"  📚 抓取 Wiki Pages...", end="")
                project_data['wiki_pages'] = get_wiki_pages(full_project)
                print(f" {len(project_data['wiki_pages'])} 个")

                # 抓取 Issues (限制数量)
                print(f"  📝 抓取 Issues...", end="")
                try:
                    issues = full_project.issues.list(all=True, per_page=TEST_CONFIG["max_issues_per_project"] + 2)
                    limited_issues = list(issues)[:TEST_CONFIG["max_issues_per_project"]]
                    
                    for issue in limited_issues:
                        author_info = safe_get(issue, 'author', {})
                        author_username = safe_dict_get(author_info, 'username', 'unknown_author')
                        
                        assignees = safe_get(issue, 'assignees', [])
                        assignee_usernames = [safe_dict_get(a, 'username') for a in assignees if safe_dict_get(a, 'username')]
                        
                        issue_data = {
                            "iid": safe_get(issue, 'iid'),
                            "title": safe_get(issue, 'title', 'Untitled Issue'),
                            "description": safe_get(issue, 'description', '')[:200] + "..." if len(safe_get(issue, 'description', '')) > 200 else safe_get(issue, 'description', ''),  # 限制描述长度
                            "state": safe_get(issue, 'state', 'opened'),
                            "author_username": author_username,
                            "assignee_usernames": assignee_usernames,
                            "labels": [label for label in safe_get(issue, 'labels', [])][:3],  # 限制标签数量
                            "milestone": safe_dict_get(safe_get(issue, 'milestone', {}), 'title', ''),
                            "created_at": safe_get(issue, 'created_at', ''),
                            "comments": []
                        }
                        
                        try:
                            notes = issue.notes.list(all=True, per_page=TEST_CONFIG["max_comments_per_issue"] + 2)
                            limited_notes = list(notes)[:TEST_CONFIG["max_comments_per_issue"]]
                            for note in limited_notes:
                                if not safe_get(note, 'system', False):
                                    note_author = safe_dict_get(safe_get(note, 'author', {}), 'username', 'unknown_author')
                                    issue_data['comments'].append({
                                        "author_username": note_author,
                                        "body": safe_get(note, 'body', '')[:100] + "..." if len(safe_get(note, 'body', '')) > 100 else safe_get(note, 'body', ''),  # 限制评论长度
                                        "created_at": safe_get(note, 'created_at', '')
                                    })
                        except Exception as note_error:
                            print(f" [评论抓取错误: {note_error}]", end="")
                        
                        project_data['issues'].append(issue_data)
                    print(f" {len(limited_issues)} 个")
                except Exception as e:
                    print(f" ❌ Issues抓取失败: {e}")

                # 抓取 Merge Requests (限制数量)
                print(f"  🔄 抓取 Merge Requests...", end="")
                try:
                    mrs = full_project.mergerequests.list(all=True, per_page=TEST_CONFIG["max_mrs_per_project"] + 2)
                    limited_mrs = list(mrs)[:TEST_CONFIG["max_mrs_per_project"]]
                    
                    for mr in limited_mrs:
                        mr_author_username = safe_dict_get(safe_get(mr, 'author', {}), 'username', 'unknown_author')
                        
                        mr_data = {
                            "iid": safe_get(mr, 'iid'),
                            "title": safe_get(mr, 'title', 'Untitled MR'),
                            "description": safe_get(mr, 'description', '')[:200] + "..." if len(safe_get(mr, 'description', '')) > 200 else safe_get(mr, 'description', ''),  # 限制描述长度
                            "state": safe_get(mr, 'state', 'opened'),
                            "source_branch": safe_get(mr, 'source_branch', ''),
                            "target_branch": safe_get(mr, 'target_branch', ''),
                            "author_username": mr_author_username,
                            "labels": [label for label in safe_get(mr, 'labels', [])][:3],  # 限制标签数量
                            "milestone": safe_dict_get(safe_get(mr, 'milestone', {}), 'title', ''),
                            "created_at": safe_get(mr, 'created_at', ''),
                            "comments": []
                        }

                        try:
                            notes = mr.notes.list(all=True, per_page=TEST_CONFIG["max_comments_per_mr"] + 2)
                            limited_notes = list(notes)[:TEST_CONFIG["max_comments_per_mr"]]
                            for note in limited_notes:
                                if not safe_get(note, 'system', False):
                                    note_author = safe_dict_get(safe_get(note, 'author', {}), 'username', 'unknown_author')
                                    mr_data['comments'].append({
                                        "author_username": note_author,
                                        "body": safe_get(note, 'body', '')[:100] + "..." if len(safe_get(note, 'body', '')) > 100 else safe_get(note, 'body', ''),  # 限制评论长度
                                        "created_at": safe_get(note, 'created_at', '')
                                    })
                        except Exception as note_error:
                            print(f" [评论抓取错误: {note_error}]", end="")
                        
                        project_data['merge_requests'].append(mr_data)
                    print(f" {len(limited_mrs)} 个")
                except Exception as e:
                    print(f" ❌ MRs抓取失败: {e}")

                data['projects'].append(project_data)
                print(f"  ✅ 项目 '{safe_get(project, 'name', 'Unknown')}' 测试抓取完成")

            except Exception as e:
                print(f"  ❌ 处理项目 {safe_get(project, 'name', 'Unknown')} 时失败: {e}")
                continue

    except Exception as e:
        print(f"❌ 抓取项目列表时出错: {e}")

    # --- 写入文件 ---
    try:
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f"\n🎉 测试抓取完成！")
        print(f"📊 统计信息:")
        print(f"  - 用户: {len(data['users'])} 个")
        print(f"  - 组: {len(data['groups'])} 个")
        print(f"  - 项目: {len(data['projects'])} 个")
        print(f"💾 测试数据已保存到: {OUTPUT_FILE}")
        print(f"⏱️  文件大小: {len(json.dumps(data)) / 1024:.2f} KB")
        
    except Exception as e:
        print(f"❌ 写入文件失败: {e}")

if __name__ == "__main__":
    main()