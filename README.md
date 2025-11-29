# Epoch-Drift-Benchmark

## 安装库：
```bash
pip install browsergym  # (recommended) everything below
pip install browsergym-experiments  # experiment utilities (agent, loop, benchmarks) + everything below
pip install browsergym-core  # core functionalities only (no benchmark, just the openended task)
pip install browsergym-miniwob  # core + miniwob
pip install browsergym-webarena  # core + webarena
pip install browsergym-visualwebarena  # core + visualwebarena
pip install browsergym-workarena  # core + workarena
pip install browsergym-assistantbench  # core + assistantbench
pip install weblinx-browsergym  # core + weblinx

playwright install chromium
```

## Docker容器：

### GitLab

#### 运行 GitLab 服务

1. 启动服务
```bash
docker-compose -f docker-compose.v12.yml up -d
```

2. 查看服务状态
```bash
docker-compose -f docker-compose.v12.yml ps
```

3. 查看实时日志
```bash
docker-compose -f docker-compose.v12.yml logs -f
```

#### 停止 GitLab 服务

1. 停止服务（保留数据）
```bash
docker-compose -f docker-compose.v12.yml stop
```

2. 停止并删除容器（保留数据）
```bash
docker-compose -f docker-compose.v12.yml down
```

3. 完全停止并清理所有资源
```bash
docker-compose -f docker-compose.v12.yml down --volumes
```

#### 设置外部URL
```bash
docker exec gitlab-v13.0 sed -i "s|^external_url.*|external_url 'http://172.26.116.102:8080'|" /etc/gitlab/gitlab.rb
docker exec gitlab-v13.0 gitlab-ctl reconfigure
```

#### 账户密码
```
Account: root

Password: zlxQGkIhkgLcnGpsJyMRjAGdPhKP75k2mscZZJm6b+A=
```

#### 设置环境变量：
```bash
$env:BASE_URL="http://172.26.116.102"              
$env:WA_SHOPPING="http://localhost:7770/"
$env:WA_SHOPPING_ADMIN="http://localhost:7780/admin"
$env:WA_REDDIT="http://localhost:9999"
$env:WA_GITLAB="http://localhost:8080"
$env:WA_WIKIPEDIA="http://localhost:8888/wikipedia_en_all_maxi_2022-05/A/User:The_other_Kiwix_guy/Landing"
$env:WA_MAP="http://localhost:3000"
$env:WA_HOMEPAGE="http://localhost:4399"
         
$env:SHOPPING="http://localhost:7770/"
$env:SHOPPING_ADMIN="http://localhost:7780/admin"
$env:REDDIT="http://localhost:9999"
$env:GITLAB="http://localhost:8080"
$env:WIKIPEDIA="http://localhost:8888/wikipedia_en_all_maxi_2022-05/A/User:The_other_Kiwix_guy/Landing"
$env:MAP="http://localhost:3000"
$env:HOMEPAGE="http://localhost:4399"


$env:WA_GITLAB_V1="http://localhost:8080"
$env:WA_GITLAB_V2="http://localhost:8080"
```

```bash
BASE_URL="http://172.26.116.102"                                                                                     
export WA_SHOPPING="$BASE_URL:7770/"
export WA_SHOPPING_ADMIN="$BASE_URL:7780/admin"
export WA_REDDIT="$BASE_URL:9999"
export WA_GITLAB="$BASE_URL:8080"
export WA_WIKIPEDIA="$BASE_URL:8888/wikipedia_en_all_maxi_2022-05/A/User:The_other_Kiwix_guy/Landing"
export WA_MAP="$BASE_URL:3000"
export WA_HOMEPAGE="$BASE_URL:4399"

export SHOPPING="$BASE_URL:7770/"
export SHOPPING_ADMIN="$BASE_URL:7780/admin"
export REDDIT="$BASE_URL:9999"
export GITLAB="$BASE_URL:8080"
export WIKIPEDIA="$BASE_URL:8888/wikipedia_en_all_maxi_2022-05/A/User:The_other_Kiwix_guy/Landing"
export MAP="$BASE_URL:3000"
export HOMEPAGE="$BASE_URL:4399"

export WA_GITLAB_V1="$BASE_URL:8080"
export WA_GITLAB_V2="$BASE_URL:8080"
```

### Magento

```bash
echo "127.0.0.1 dockerized-magento.local" | sudo tee -a /etc/hosts
```

```bash
./magento start      # 启动项目
./magento stop       # 停止项目  
./magento restart    # 重启并清缓存
./magento status     # 查看状态
./magento stats      # 资源使用统计
./magento magerun    # 运行 magerun
./magento composer   # 运行 composer
./magento enter      # 进入容器
./magento destroy    # 删除所有数据
```


前端: http://dockerized-magento.local

后台: http://dockerized-magento.local/admin (admin/password123)

phpMyAdmin: http://dockerized-magento.local:8080 (root/pw)

### WordPress

```bash
# 第一步：赋予脚本执行权限
chmod +x drift_manager.sh

# 第二步：启动容器
docker-compose up -d --build

# 第三步：执行初始化
./drift_manager.sh init

# 第四步：测试“漂移” (Drift)
./drift_manager.sh drift twentytwentyfour
```


## 运行方式
### ASI
```bash
python run_demo.py --task_name myBenchmark.3 --websites gitlab
python run_online.py --experiment asi --website gitlab --task_ids 419-419
```

### SkillWeaver
```bash
python -m skillweaver.explore gitlab logs/explore-gitlab

python -m skillweaver.evaluation.evaluate_benchmark gitlab results/gitlab_with_skills2 --knowledge-base-path-prefix logs/explore-gitlab/iter_159/kb_post --pool-size 8

python -m skillweaver.evaluation.evaluate_single_task --task_id 60 --out_dir results/gitlab_with_skills --knowledge_base_path_prefix logs/explore-gitlab/iter_159/kb_post
```

### MUSE
```bash
python run_myBenchmark_muse.py
```

## Drift脚本
```python
import random

class DriftInjector:
    def __init__(self, seed=42):
        """
        :param seed: 随机种子，确保每次生成的干扰逻辑在浏览器端执行顺序一致。
        """
        self.seed = seed

    def _get_seeded_rng_script(self) -> str:
        """
        生成一个基于种子的伪随机数生成器 (LCG 算法) 的 JS 代码。
        替代 Math.random()，确保由 Python 指定的 seed 控制随机结果。
        """
        return f"""
            // === Deterministic RNG Setup ===
            window.__drift_seed = {self.seed};
            
            // 简单的线性同余生成器 (LCG)
            // 只要初始 seed 相同，生成的序列永远相同
            const seededRandom = () => {{
                window.__drift_seed = (window.__drift_seed * 9301 + 49297) % 233280;
                return window.__drift_seed / 233280;
            }};

            // 辅助函数：生成确定性的随机字符串 (用于替换 Math.random().toString(36))
            const seededString = () => {{
                return Math.floor(seededRandom() * 2147483648).toString(36);
            }};
        """

    def _get_visual_drift_css(self, intensity: str) -> str:
        """
        (保持不变) 根据强度生成 CSS 样式。
        """
        css_parts = []
        if intensity == "low":
            css_parts.append("body { background-color: #f9f9f9 !important; line-height: 1.6 !important; }")
            css_parts.append("a { text-decoration: underline !important; }")
        elif intensity == "medium":
            css_parts.append("body, * { font-family: 'Courier New', monospace !important; }")
            css_parts.append("button, .btn { border-radius: 0px !important; background-color: #4a90e2 !important; color: #fff !important; border: 2px solid #000 !important; }")
            css_parts.append("input { background-color: #fff8dc !important; }")
        elif intensity == "high":
            css_parts.append("* { letter-spacing: 1.5px !important; word-spacing: 2px !important; }")
            css_parts.append("div, p, span { transform: rotate(0.2deg); }") 
            css_parts.append("body { filter: contrast(120%); }")
            css_parts.append("button, .btn { border: 3px dashed red !important; font-weight: bold !important; }")
            
        return " ".join(css_parts).replace("\n", " ")

    def _get_mutation_params(self, intensity: str) -> dict:
        """
        (保持不变) 根据强度定义 DOM 变异的概率参数
        """
        if intensity == "low":
            return {"remove_testid_prob": 0.1, "add_class_prob": 0.2, "enable_tag_replace": False, "attr_noise_prob": 0.1}
        elif intensity == "medium":
            return {"remove_testid_prob": 0.4, "add_class_prob": 0.5, "enable_tag_replace": True, "attr_noise_prob": 0.3}
        elif intensity == "high":
            return {"remove_testid_prob": 0.8, "add_class_prob": 0.9, "enable_tag_replace": True, "attr_noise_prob": 0.6}
        return self._get_mutation_params("medium")

    def generate_drift_script(self, drift_type: str, intensity: str) -> str:
        """
        生成带有强度控制且【结果确定】的 JS 注入脚本。
        """
        params = self._get_mutation_params(intensity)
        script_parts = []
        
        # 1. 注入 RNG 核心逻辑 (这是实现“每次结果相同”的关键)
        script_parts.append(self._get_seeded_rng_script())
        
        script_parts.append(f"console.log('[DriftInjector] Intensity: {intensity}, Type: {drift_type}, Seed: {self.seed}');")

        # === Part 1: Visual Drift (CSS) ===
        if "visual" in drift_type or drift_type == "all":
            css_content = self._get_visual_drift_css(intensity)
            script_parts.append(f"""
                const injectStyles = () => {{
                    if (document.getElementById('drift-style-injected')) return;
                    const style = document.createElement('style');
                    style.textContent = "{css_content}";
                    style.id = 'drift-style-injected';
                    (document.head || document.documentElement).appendChild(style);
                }};
            """)
        else:
            script_parts.append("const injectStyles = () => {};")

        # === Part 2: DOM Mutation Logic ===
        # 注意：这里所有的 Math.random() 都被替换为了 seededRandom()
        mutation_logic = ""
        
        if "locator" in drift_type or drift_type == "all":
            mutation_logic += f"""
                // 1. 干扰 data-testid
                if (node.getAttribute && node.getAttribute('data-testid')) {{
                    if (!node.getAttribute('data-drifted-id')) {{
                        const r = seededRandom(); // <--- 使用确定性随机数
                        if (r < {params['remove_testid_prob']}) {{
                            node.removeAttribute('data-testid');
                        }} else if (r < {params['remove_testid_prob']} + {params['attr_noise_prob']}) {{
                            node.setAttribute('data-testid', node.getAttribute('data-testid') + '__drifted');
                        }}
                        node.setAttribute('data-drifted-id', 'true'); 
                    }}
                }}

                // 2. 干扰 Class
                if (node.classList && !node.classList.contains('drift-c')) {{
                    if (seededRandom() < {params['add_class_prob']}) {{ // <--- 使用确定性随机数
                        // 生成确定性的随机字符串
                        node.classList.add('drift-' + seededString()); 
                        node.classList.add('drift-c');
                    }}
                }}
            """

        if ("structural" in drift_type or drift_type == "all") and params['enable_tag_replace']:
            mutation_logic += """
                const tagMap = { 'B': 'STRONG', 'I': 'EM', 'SPAN': 'LABEL' };
                if (tagMap[node.tagName] && !node.getAttribute('data-drifted-tag')) {
                     if (node.children.length === 0 && node.textContent.length < 50) {
                        const newTag = tagMap[node.tagName];
                        const newEl = document.createElement(newTag);
                        newEl.innerHTML = node.innerHTML;
                        newEl.className = node.className;
                        newEl.setAttribute('data-drifted-tag', 'true');
                        try {
                            node.parentNode.replaceChild(newEl, node);
                        } catch(e) {}
                     }
                }
            """

        # === Part 3: Execution & Observer ===
        script_parts.append(f"""
            const applyDrift = (node) => {{
                if (!node || node.nodeType !== 1) return;
                try {{
                    {mutation_logic}
                }} catch (e) {{}}
            }};

            const startObserver = () => {{
                const target = document.body || document.documentElement;
                if (!target) {{
                    requestAnimationFrame(startObserver);
                    return;
                }}
                injectStyles();
                document.querySelectorAll('*').forEach(applyDrift);
                const observer = new MutationObserver((mutations) => {{
                    mutations.forEach((mutation) => {{
                        mutation.addedNodes.forEach((node) => {{
                            if (node.nodeType === 1) {{
                                applyDrift(node);
                                node.querySelectorAll('*').forEach(applyDrift);
                            }}
                        }});
                    }});
                }});
                observer.observe(target, {{ childList: true, subtree: true }});
            }};

            if (document.readyState === 'loading') {{
                document.addEventListener('DOMContentLoaded', startObserver);
            }} else {{
                startObserver();
            }}
        """)

        return "\n".join(script_parts)
```

## gitlab任务更改：
```
id：6 增加一个"OpenAPI Generator CLI"的issue
id: 59 gimmiethat.space仓库中移除member Jakub
id: 62 增加一个标题为“octovisuals page”的merge request
id: 63 增加一个标题为“semantic HTML post”的merge request
id: 64 增加一个标题为“focus edge cases”的merge request
id: 65
id: 96 删除chatgpt_plugin仓库
id: 97 删除awesome_llm_reading仓库
id: 98
id: 99
id: 100
id: 101 移除yjlou成员
id: 102
id: 103
id: 104
id: 105
id: 106
id: 119
id: 120
id: 124
id: 125
id: 145
id: 146
...
id: 159
id: 167
...
id: 171

修改：3, 15, 16, 19, 20, 23, 24, 33, 34, 35, 36, 37, 38, 51, 53(repo name), 60, 62, 63, 75, 108-112, 144, 163
待定：17, 18, 21, 22, 43, 66, 76, 77, 78, 89, 90, 113-117(不能查看follow), 164

url 里面的/-/
两种match都要修改

issue 在v16里有bug
git clone 的比对逻辑需要修改

最终删除：
17, 18, 21, 22, 26, 27, 43, 66, 71, 76, 77, 78, 113-117, 164
```

## 运行结果
| 方法        | v1(训练) | v1_drift | v1_waber |
|:-------------:|:----------:|:----------:|:----------:|
| ASI         | 22.22%   | 16.05%   | 0.00%    |
| SkillWeaver | 18.06%   | 15.07%   | 无       |