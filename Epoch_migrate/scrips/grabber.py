import gitlab
import json
import sys
import time
from datetime import datetime

# --- 配置 ---
V14_URL = 'http://localhost:8023' 
V14_ADMIN_TOKEN = 'glpat-XmjTr6uk2_XbWzitBzB5'
OUTPUT_FILE = f'gitlab_data_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
MAX_RETRIES = 3  # 最大重试次数
RETRY_DELAY = 5  # 重试延迟（秒）
# --- 

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

def retry_with_backoff(func, *args, **kwargs):
    """重试装饰器函数，带有指数退避"""
    last_exception = None
    for attempt in range(MAX_RETRIES):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            last_exception = e
            if attempt < MAX_RETRIES - 1:  # 不是最后一次尝试
                wait_time = RETRY_DELAY * (2 ** attempt)  # 指数退避
                print(f"  重试 {attempt + 1}/{MAX_RETRIES} 在 {wait_time} 秒后... 错误: {e}")
                time.sleep(wait_time)
    
    # 所有重试都失败了
    print(f"  ❌ 在 {MAX_RETRIES} 次重试后失败: {last_exception}")
    raise last_exception

def get_labels(project):
    """获取项目标签"""
    def _get_labels():
        try:
            labels = project.labels.list(all=True)
            return [
                {
                    "id": safe_get(label, 'id'),
                    "name": safe_get(label, 'name', ''),
                    "color": safe_get(label, 'color', ''),
                    "description": safe_get(label, 'description', '')
                }
                for label in labels
            ]
        except Exception as e:
            print(f" [标签错误: {e}]", end="")
            return []
    
    return retry_with_backoff(_get_labels)

def get_milestones(project):
    """获取项目里程碑"""
    def _get_milestones():
        try:
            milestones = project.milestones.list(all=True)
            return [
                {
                    "id": safe_get(milestone, 'id'),
                    "title": safe_get(milestone, 'title', ''),
                    "description": safe_get(milestone, 'description', ''),
                    "state": safe_get(milestone, 'state', 'active'),
                    "due_date": safe_get(milestone, 'due_date', ''),
                    "start_date": safe_get(milestone, 'start_date', '')
                }
                for milestone in milestones
            ]
        except Exception as e:
            print(f" [里程碑错误: {e}]", end="")
            return []
    
    return retry_with_backoff(_get_milestones)

def get_forks(project):
    """获取项目派生信息"""
    def _get_forks():
        try:
            forks = project.forks.list(all=True)
            return [
                {
                    "id": safe_get(fork, 'id'),
                    "name": safe_get(fork, 'name', ''),
                    "path": safe_get(fork, 'path', ''),
                    "namespace": safe_dict_get(safe_get(fork, 'namespace', {}), 'full_path', ''),
                    "web_url": safe_get(fork, 'web_url', '')
                }
                for fork in forks
            ]
        except Exception as e:
            print(f" [派生错误: {e}]", end="")
            return []
    
    return retry_with_backoff(_get_forks)

def get_stars(project):
    """获取项目星标信息"""
    def _get_stars():
        try:
            return {
                "star_count": safe_get(project, 'star_count', 0),
            }
        except Exception as e:
            print(f" [星标错误: {e}]", end="")
            return {"star_count": 0}
    
    return retry_with_backoff(_get_stars)

def get_pipelines(project):
    """获取CI/CD流水线"""
    def _get_pipelines():
        try:
            pipelines = project.pipelines.list(all=True, per_page=50)
            pipeline_data = []
            
            for pipeline in pipelines:
                try:
                    full_pipeline = project.pipelines.get(safe_get(pipeline, 'id'))
                    
                    jobs = []
                    try:
                        pipeline_jobs = full_pipeline.jobs.list(all=True)
                        for job in pipeline_jobs:
                            jobs.append({
                                "id": safe_get(job, 'id'),
                                "name": safe_get(job, 'name', ''),
                                "stage": safe_get(job, 'stage', ''),
                                "status": safe_get(job, 'status', ''),
                                "created_at": safe_get(job, 'created_at', ''),
                                "finished_at": safe_get(job, 'finished_at', '')
                            })
                    except Exception as job_error:
                        print(f" [任务错误: {job_error}]", end="")
                    
                    pipeline_data.append({
                        "id": safe_get(full_pipeline, 'id'),
                        "status": safe_get(full_pipeline, 'status', ''),
                        "ref": safe_get(full_pipeline, 'ref', ''),
                        "sha": safe_get(full_pipeline, 'sha', ''),
                        "created_at": safe_get(full_pipeline, 'created_at', ''),
                        "updated_at": safe_get(full_pipeline, 'updated_at', ''),
                        "jobs": jobs
                    })
                except Exception as pipe_error:
                    print(f" [流水线详情错误: {pipe_error}]", end="")
                    continue
            
            return pipeline_data
        except Exception as e:
            print(f" [流水线错误: {e}]", end="")
            return []
    
    return retry_with_backoff(_get_pipelines)

def get_wiki_pages(project):
    """获取Wiki页面"""
    def _get_wiki_pages():
        try:
            if not safe_get(project, 'wiki_enabled', False):
                return []
                
            wiki_pages = project.wikis.list(all=True)
            wiki_data = []
            
            for wiki_page in wiki_pages:
                try:
                    full_page = project.wikis.get(safe_get(wiki_page, 'slug'))
                    wiki_data.append({
                        "slug": safe_get(full_page, 'slug', ''),
                        "title": safe_get(full_page, 'title', ''),
                        "format": safe_get(full_page, 'format', 'markdown'),
                        "content": safe_get(full_page, 'content', ''),
                        "created_at": safe_get(full_page, 'created_at', '')
                    })
                except Exception as page_error:
                    print(f" [Wiki页面错误: {page_error}]", end="")
                    continue
            
            return wiki_data
        except Exception as e:
            print(f" [Wiki错误: {e}]", end="")
            return []
    
    return retry_with_backoff(_get_wiki_pages)

def write_project_to_file(project_data, filename):
    """将单个项目数据追加到文件"""
    try:
        # 读取现有数据
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            # 文件不存在或为空，创建新结构
            existing_data = {
                "export_info": {
                    "source_url": V14_URL,
                    "export_time": datetime.now().isoformat(),
                    "gitlab_version": None
                },
                "users": [],
                "projects": []
            }
        
        # 添加新项目
        existing_data['projects'].append(project_data)
        
        # 写回文件
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(existing_data, f, indent=2, ensure_ascii=False)
        
        return True
    except Exception as e:
        print(f"  ❌ 写入项目到文件失败: {e}")
        return False

def main():
    try:
        gl = gitlab.Gitlab(V14_URL, private_token=V14_ADMIN_TOKEN)
        gl.auth()
        
        current_user = gl.user
        print(f"✅ 成功连接到源 GitLab (v14): {V14_URL}")
        print(f"✅ 当前用户: {safe_get(current_user, 'username', 'Unknown')}")
        
    except Exception as e:
        print(f"❌ 连接到 v14 实例失败: {e}")
        print("请检查:")
        print("  - V14_URL 和 V14_ADMIN_TOKEN 是否正确")
        print("  - GitLab v14 容器是否正在运行")
        print("  - 网络连接是否正常")
        sys.exit(1)

    # 初始化输出文件
    initial_data = {
        "export_info": {
            "source_url": V14_URL,
            "export_time": datetime.now().isoformat(),
            "gitlab_version": None
        },
        "users": [],
        "projects": []
    }

    # 获取GitLab版本信息
    try:
        version_info = gl.version()
        initial_data["export_info"]["gitlab_version"] = version_info
        print(f"✅ GitLab 版本: {version_info}")
    except:
        print("⚠️  无法获取GitLab版本信息")

    # 创建初始文件
    try:
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(initial_data, f, indent=2, ensure_ascii=False)
        print(f"✅ 初始化输出文件: {OUTPUT_FILE}")
    except Exception as e:
        print(f"❌ 创建输出文件失败: {e}")
        sys.exit(1)

    # --- 抓取用户 ---
    print("\n📋 抓取用户...")
    try:
        users = gl.users.list(all=True)
        active_users = [u for u in users if safe_get(u, 'state') == 'active' and safe_get(u, 'username') != 'root']
        
        user_data = []
        for user in active_users:
            user_info = {
                "id": safe_get(user, 'id'),
                "username": safe_get(user, 'username', 'unknown_username'),
                "name": safe_get(user, 'name', ''),
                "email": safe_get(user, 'email', ''),
                "state": safe_get(user, 'state', 'unknown')
            }
            user_data.append(user_info)
        
        # 更新文件中的用户数据
        try:
            with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
            existing_data['users'] = user_data
            with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
                json.dump(existing_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"  ❌ 更新用户数据到文件失败: {e}")
        
        print(f"  ✅ 抓取了 {len(user_data)} 个活动用户")
        
        empty_names = sum(1 for u in user_data if not u['name'])
        empty_emails = sum(1 for u in user_data if not u['email'])
        print(f"  📊 统计: {empty_names} 个用户名为空, {empty_emails} 个邮箱为空")
        
    except Exception as e:
        print(f"❌ 抓取用户时出错: {e}")

    # --- 抓取项目 ---
    print("\n📦 抓取项目...")
    try:
        projects = gl.projects.list(all=True)
        print(f"  📊 发现了 {len(projects)} 个项目，开始深度抓取...")

        successful_projects = 0
        failed_projects = 0

        for i, project in enumerate(projects):
            print(f"\n[{i+1}/{len(projects)}] 正在处理项目: {safe_get(project, 'name_with_namespace', 'Unknown Project')}")
            
            try:
                # 重试获取完整项目信息
                def _get_full_project():
                    return gl.projects.get(project.id)
                
                full_project = retry_with_backoff(_get_full_project)
                
                # 安全处理项目信息
                namespace_info = safe_get(full_project, 'namespace', {})
                if isinstance(namespace_info, dict):
                    namespace_path = safe_dict_get(namespace_info, 'full_path', safe_dict_get(namespace_info, 'path', 'unknown_namespace'))
                else:
                    namespace_path = safe_get(namespace_info, 'full_path', 'unknown_namespace')
                
                project_data = {
                    "id": safe_get(full_project, 'id'),
                    "name": safe_get(full_project, 'name', 'unknown_project'),
                    "path": safe_get(full_project, 'path', 'unknown_path'),
                    "namespace": namespace_path,
                    "visibility": safe_get(full_project, 'visibility', 'private'),
                    "description": safe_get(full_project, 'description', ''),
                    "web_url": safe_get(full_project, 'web_url', ''),
                    "http_url_to_repo": safe_get(full_project, 'http_url_to_repo', ''),
                    "ssh_url_to_repo": safe_get(full_project, 'ssh_url_to_repo', ''),
                    "created_at": safe_get(full_project, 'created_at', ''),
                    "last_activity_at": safe_get(full_project, 'last_activity_at', ''),
                    "star_count": safe_get(full_project, 'star_count', 0),
                    "forks_count": safe_get(full_project, 'forks_count', 0),
                    "wiki_enabled": safe_get(full_project, 'wiki_enabled', False),
                    "issues_enabled": safe_get(full_project, 'issues_enabled', False),
                    "merge_requests_enabled": safe_get(full_project, 'merge_requests_enabled', False),
                    "wiki_enabled": safe_get(full_project, 'wiki_enabled', False),
                    "snippets_enabled": safe_get(full_project, 'snippets_enabled', False),
                    "authed_http_url_to_repo": None,
                    "labels": [],
                    "milestones": [],
                    "forks": [],
                    "stars": {},
                    "pipelines": [],
                    "wiki_pages": [],
                    "issues": [],
                    "merge_requests": []
                }

                authed_source_url = project_data['http_url_to_repo'].replace('http://', f'http://oauth2:{V14_ADMIN_TOKEN}@')
                project_data["authed_http_url_to_repo"] = authed_source_url

                # 使用重试机制抓取各项数据
                print(f"  🏷️  抓取 Labels...", end="")
                project_data['labels'] = get_labels(full_project)
                print(f" {len(project_data['labels'])} 个")

                print(f"  🎯 抓取 Milestones...", end="")
                project_data['milestones'] = get_milestones(full_project)
                print(f" {len(project_data['milestones'])} 个")

                print(f"  🍴 抓取 Forks...", end="")
                project_data['forks'] = get_forks(full_project)
                print(f" {len(project_data['forks'])} 个")

                print(f"  ⭐ 抓取 Stars...", end="")
                project_data['stars'] = get_stars(full_project)
                print(f" {project_data['stars']['star_count']} 个")

                print(f"  🔧 抓取 CI/CD Pipelines...", end="")
                project_data['pipelines'] = get_pipelines(full_project)
                print(f" {len(project_data['pipelines'])} 个")

                print(f"  📚 抓取 Wiki Pages...", end="")
                project_data['wiki_pages'] = get_wiki_pages(full_project)
                print(f" {len(project_data['wiki_pages'])} 个")

                # 抓取 Issues（带重试）
                print(f"  📝 抓取 Issues...", end="")
                def _get_issues():
                    try:
                        issues = full_project.issues.list(all=True)
                        issue_data = []
                        for issue in issues:
                            author_info = safe_get(issue, 'author', {})
                            if isinstance(author_info, dict):
                                author_username = safe_dict_get(author_info, 'username', 'unknown_author')
                            else:
                                author_username = safe_get(author_info, 'username', 'unknown_author')
                            
                            assignees = safe_get(issue, 'assignees', [])
                            assignee_usernames = []
                            if assignees:
                                for assignee in assignees:
                                    if isinstance(assignee, dict):
                                        username = safe_dict_get(assignee, 'username')
                                    else:
                                        username = safe_get(assignee, 'username')
                                    if username:
                                        assignee_usernames.append(username)
                            
                            issue_info = {
                                "iid": safe_get(issue, 'iid'),
                                "title": safe_get(issue, 'title', 'Untitled Issue'),
                                "description": safe_get(issue, 'description', ''),
                                "state": safe_get(issue, 'state', 'opened'),
                                "author": author_username,
                                "assignees": assignee_usernames,
                                "labels": [label for label in safe_get(issue, 'labels', [])],
                                "milestone": safe_dict_get(safe_get(issue, 'milestone', {}), 'title', ''),
                                "created_at": safe_get(issue, 'created_at', ''),
                                "updated_at": safe_get(issue, 'updated_at', ''),
                                "comments": []
                            }
                            
                            # 抓取评论
                            try:
                                for note in issue.notes.list(all=True):
                                    if not safe_get(note, 'system', False):
                                        note_author = safe_get(note, 'author', {})
                                        if isinstance(note_author, dict):
                                            note_author_username = safe_dict_get(note_author, 'username', 'unknown_author')
                                        else:
                                            note_author_username = safe_get(note_author, 'username', 'unknown_author')
                                        
                                        issue_info['comments'].append({
                                            "author": note_author_username,
                                            "body": safe_get(note, 'body', ''),
                                            "created_at": safe_get(note, 'created_at', '')
                                        })
                            except Exception as note_error:
                                print(f" [评论抓取错误: {note_error}]", end="")
                            
                            issue_data.append(issue_info)
                        return issue_data
                    except Exception as e:
                        print(f" [Issues错误: {e}]", end="")
                        return []
                
                project_data['issues'] = retry_with_backoff(_get_issues)
                print(f" {len(project_data['issues'])} 个")

                # 抓取 Merge Requests（带重试）
                print(f"  🔄 抓取 Merge Requests...", end="")
                def _get_merge_requests():
                    try:
                        mrs = full_project.mergerequests.list(all=True)
                        mr_data = []
                        for mr in mrs:
                            mr_author_info = safe_get(mr, 'author', {})
                            if isinstance(mr_author_info, dict):
                                mr_author_username = safe_dict_get(mr_author_info, 'username', 'unknown_author')
                            else:
                                mr_author_username = safe_get(mr_author_info, 'username', 'unknown_author')
                            
                            mr_info = {
                                "iid": safe_get(mr, 'iid'),
                                "title": safe_get(mr, 'title', 'Untitled MR'),
                                "description": safe_get(mr, 'description', ''),
                                "state": safe_get(mr, 'state', 'opened'),
                                "source_branch": safe_get(mr, 'source_branch', ''),
                                "target_branch": safe_get(mr, 'target_branch', ''),
                                "author": mr_author_username,
                                "labels": [label for label in safe_get(mr, 'labels', [])],
                                "milestone": safe_dict_get(safe_get(mr, 'milestone', {}), 'title', ''),
                                "created_at": safe_get(mr, 'created_at', ''),
                                "updated_at": safe_get(mr, 'updated_at', ''),
                                "comments": []
                            }

                            # 抓取评论
                            try:
                                for note in mr.notes.list(all=True):
                                    if not safe_get(note, 'system', False):
                                        note_author = safe_get(note, 'author', {})
                                        if isinstance(note_author, dict):
                                            note_author_username = safe_dict_get(note_author, 'username', 'unknown_author')
                                        else:
                                            note_author_username = safe_get(note_author, 'username', 'unknown_author')
                                        
                                        mr_info['comments'].append({
                                            "author": note_author_username,
                                            "body": safe_get(note, 'body', ''),
                                            "created_at": safe_get(note, 'created_at', '')
                                        })
                            except Exception as note_error:
                                print(f" [评论抓取错误: {note_error}]", end="")
                            
                            mr_data.append(mr_info)
                        return mr_data
                    except Exception as e:
                        print(f" [MRs错误: {e}]", end="")
                        return []
                
                project_data['merge_requests'] = retry_with_backoff(_get_merge_requests)
                print(f" {len(project_data['merge_requests'])} 个")

                # 立即写入项目数据到文件
                if write_project_to_file(project_data, OUTPUT_FILE):
                    print(f"  ✅ 项目 '{safe_get(project, 'name', 'Unknown')}' 处理完成并已保存")
                    successful_projects += 1
                else:
                    print(f"  ⚠️  项目 '{safe_get(project, 'name', 'Unknown')}' 处理完成但保存失败")
                    failed_projects += 1

            except Exception as e:
                print(f"  ❌ 处理项目 {safe_get(project, 'name', 'Unknown')} 时失败: {e}")
                failed_projects += 1
                continue

        print(f"\n📊 项目处理完成统计:")
        print(f"  ✅ 成功: {successful_projects} 个")
        print(f"  ❌ 失败: {failed_projects} 个")
        print(f"  📁 总计: {len(projects)} 个")

    except Exception as e:
        print(f"❌ 抓取项目列表时出错: {e}")

    # --- 最终统计 ---
    try:
        with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
            final_data = json.load(f)
        
        print(f"\n🎉 导出完成！")
        print(f"📊 最终统计信息:")
        print(f"  - 用户: {len(final_data['users'])} 个")
        print(f"  - 项目: {len(final_data['projects'])} 个")
        
        total_stats = {
            "labels": sum(len(p['labels']) for p in final_data['projects']),
            "milestones": sum(len(p['milestones']) for p in final_data['projects']),
            "forks": sum(len(p['forks']) for p in final_data['projects']),
            "pipelines": sum(len(p['pipelines']) for p in final_data['projects']),
            "wiki_pages": sum(len(p['wiki_pages']) for p in final_data['projects']),
            "issues": sum(len(p['issues']) for p in final_data['projects']),
            "merge_requests": sum(len(p['merge_requests']) for p in final_data['projects'])
        }
        
        for key, value in total_stats.items():
            print(f"  - {key}: {value} 个")
            
        print(f"💾 数据已保存到: {OUTPUT_FILE}")
        
    except Exception as e:
        print(f"❌ 读取最终统计信息失败: {e}")

if __name__ == "__main__":
    main()