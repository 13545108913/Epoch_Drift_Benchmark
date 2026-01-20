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

Password: a_very_secure_password_123!
```

#### 设置环境变量：
```bash
$env:BASE_URL="http://172.26.116.102"              
$env:WA_SHOPPING="http://localhost:7770/"
$env:WA_SHOPPING_ADMIN="http://dockerized-magento.local/admin"
$env:WA_REDDIT="http://localhost:9999"
$env:WA_GITLAB="http://localhost:8080"
$env:WA_WIKIPEDIA="http://localhost:8888/wikipedia_en_all_maxi_2022-05/A/User:The_other_Kiwix_guy/Landing"
$env:WA_MAP="http://localhost:3000"
$env:WA_HOMEPAGE="http://localhost:4399"
         
$env:SHOPPING="http://localhost:7770/"
$env:SHOPPING_ADMIN="http://dockerized-magento.local/admin"
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
export WA_SHOPPING_ADMIN="http://dockerized-magento.local/admin"
export WA_REDDIT="$BASE_URL:9999"
export WA_GITLAB="$BASE_URL:8080"
export WA_WIKIPEDIA="$BASE_URL:8888/wikipedia_en_all_maxi_2022-05/A/User:The_other_Kiwix_guy/Landing"
export WA_MAP="$BASE_URL:3000"
export WA_HOMEPAGE="$BASE_URL:4399"
export WA_WORDPRESS="http://localhost:8000"

export SHOPPING="$BASE_URL:7770/"
export SHOPPING_ADMIN="http://dockerized-magento.local/admin"
export REDDIT="$BASE_URL:9999"
export GITLAB="$BASE_URL:8080"
export WIKIPEDIA="$BASE_URL:8888/wikipedia_en_all_maxi_2022-05/A/User:The_other_Kiwix_guy/Landing"
export MAP="$BASE_URL:3000"
export HOMEPAGE="$BASE_URL:4399"
export WORDPRESS="http://localhost:8000"

export WA_GITLAB_V1="$BASE_URL:8080"
export WA_GITLAB_V2="$BASE_URL:8080"
export WA_SHOPPING_ADMIN_V1="http://dockerized-magento.local/admin"
export WA_SHOPPING_ADMIN_V2="http://dockerized-magento.local/admin"
export WA_WORDPRESS_V1="http://localhost:8000"
export WA_WORDPRESS_V2="http://localhost:8000"

export my_api_key="sk-wFOxHykWS5f5hcWXjEYwty5eriAiMvrcvHwdyVCXzvChY8g6"
export my_base_url="https://yunwu.ai/v1"
export my_model="claude-haiku-4-5-20251001"

export with_drift='false'
export with_waber='true'

export OPENAI_API_KEY="sk-wFOxHykWS5f5hcWXjEYwty5eriAiMvrcvHwdyVCXzvChY8g6"
```

```bash
export my_api_key="sk-41fae6597fd14d6fa2c5c4068c0e5760"
export my_base_url="https://api.deepseek.com"
export my_model="deepseek-chat"
```

http://180.209.3.219:8080

### Magento

#### Magento 1.9

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

接收者操作步骤：
```bash
mkdir my-magento
tar -xzvf magento-full-backup.tar.gz -C my-magento
cd my-magento

./magento start
```

```bash
docker load --input shopping_admin_final_0719.tar
docker run --name shopping_admin -p 7780:80 -d shopping_admin_final_0719
docker exec shopping_admin /var/www/magento2/bin/magento setup:store-config:set --base-url="http://localhost:7780" # no trailing slash
docker exec shopping_admin mysql -u magentouser -pMyPassword magentodb -e  'UPDATE core_config_data SET value="http://localhost:7780/" WHERE path = "web/secure/base_url";'
docker exec shopping_admin /var/www/magento2/bin/magento cache:flush
```

#### Magento 2.4

关闭VPN！！！！！

任务,原生命令,推荐快捷命令
启动容器,docker compose up -d,bin/start
停止容器,docker compose stop,bin/stop
运行 Magento 命令,docker exec -it ... php bin/magento c:f,bin/magento c:f
运行 Composer,docker exec -it ... composer install,bin/composer install
进入 PHP 容器,docker exec -it <php_container> bash,bin/bash
查看日志,docker compose logs -f,bin/logs
启用/禁用缓存,(Magento 命令),bin/clinotty bin/magento cache:enable

前端地址: https://magento.test/

后台地址: https://magento.test/admin

Username: admin

Password: Password123

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

前台首页: http://localhost:8000

后台管理: http://localhost:8000/wp-admin

用户名 (Username): admin

密码 (Password): password

## WABER设置

### ASI

```bash
mitmdump -p 8848 -s addons_webarena.py
```

在`/Users/chenboyu/anaconda3/envs/asi/lib/python3.10/site-packages/browsergym/core/env.py`的236行加上`proxy={"server": "http://127.0.0.1:8848"},`


## 运行方式
### ASI
```bash
python run_demo.py --task_name myBenchmark.9 --websites gitlab
python run_online.py --website gitlab --task_ids 0-7
python run_online_parallel.py --website gitlab --task_ids 0-7
python run_online_parallel.py --website gitlab --task_ids 0-161 --fast
```

### SkillWeaver
```bash
python -m skillweaver.explore gitlab logs/explore-gitlab

python -m skillweaver.explore shopping_admin logs/explore-admin

python -m skillweaver.explore wordpress logs/explore-wordpress

python -m skillweaver.evaluation.evaluate_benchmark gitlab results/gitlab_with_skills_v16_waber --knowledge-base-path-prefix logs/explore-gitlab/iter_159/kb_post --pool-size 8

python -m skillweaver.evaluation.evaluate_benchmark shopping_admin results/admin_with_skills_v1 --knowledge-base-path-prefix logs/explore-admin/iter_159/kb_post --pool-size 8

python -m skillweaver.evaluation.evaluate_benchmark wordpress results/wordpress_with_skills_v2_waber --knowledge-base-path-prefix logs/explore-wordpress/iter_159/kb_post --pool-size 6

python -m skillweaver.evaluation.evaluate_single_task --task_id 4 --out_dir results/gitlab_with_skills_v16_waber --knowledge_base_path_prefix logs/explore-gitlab/iter_159/kb_post
```

### MUSE
```bash
python run_myBenchmark_muse.py
```

### WALT

```bash
walt discover --url http://172.26.116.102:8080 --llm "deepseek-chat" --planner-llm "deepseek-chat" --max-processes 8 --auth-file /Users/chenboyu/Desktop/Epoch_Drift_Benchmark/Agents/WALT/gitlab_state.json


python src/walt/benchmarks/wa/aeval.py --config experiment_configs/wa_with_tools.yaml --result_dir outputs/wa_gitlab_v16_waber --tool_dir walt-tools/gitlab_v16 --expose_tool_actions --fallback_to_agent --force_login_every_task


walt discover --url https://dockerized-magento.local/admin --llm "gpt-5-mini" --planner-llm "gpt-5-mini" --max-processes 8 --auth-file /Users/chenboyu/Desktop/Epoch_Drift_Benchmark/Agents/WALT/auth.json

walt discover --url http://172.26.116.102:8080 --llm "gpt-5-mini" --planner-llm "gpt-5-mini" --max-processes 1
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
### v12更改：
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

### v16更改：
```
3, 15, 16, 19, 20, 21, 23, 24, 25, 28, 33, 34, 35, 36, 37, 38, 51, 62, 63, 64, 65, 75, 144, 163, 

删除：
17, 18, 21, 22, 26, 27, 43, 66, 71, 76, 77, 78, 113-117, 164
```

## Magento任务更改：
### v1.9更改：

```
2.4也要改: 59, 126

删除: 4, 5, 6, 17, 22, 23, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 45, 46, 61, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 87, 88, 89, 90, 91, 92, 93, 94, 101, 112, 113, 114, 115, 116, 117, 118, 119, 120, 121, 132, 133, 134, 135, 166, 167, 168, 169, 170, 171, 172, 173, 174, 175, 176, 178, 180, 181
```

### git clone 的command需要修改（不一定为ssh://git@172.26.116.102:2223/eriklindernoren/PyTorch-GAN.git）

## 运行结果
### 成功率
| 方法        | v1(训练) | v1_drift(high) | v1_waber | v2 | v2_drift | v2_waber |
|:-------------:|:----------:|:----------:|:----------:|:----------:|:----------:|:----------:|
| AWM         | 25.93%   | 18.52%   | 6.79%    | 25.31%    | 22.16%    | 10.56%|
| ASI         | 30.25%   | 20.99%   | 14.20%    | 34.57%    | 25.31%    | 10.69%|
| SkillWeaver | 18.06%   | 15.07%   | 12.63%    | 17.90%    | 13.75%    | 3.29%|
| WALT        | 27.78%   | 19.75%   |  0.00%    | 25.93%    | 23.46%    | 0.00%|

| 方法        | v1(训练) | v1_drift(high) | v1_waber | v2 | v2_drift | v2_waber |
|:-------------:|:----------:|:----------:|:----------:|:----------:|:----------:|:----------:|
| AWM         | 57.89%   |  18.42%  |   19.30%   |  28.07%   |  23.68%   | 7.89%|
| ASI         | 50.00%   |  28.07%  |   18.42%   |  37.72%   |  19.30%   | 16.67%|
| SkillWeaver | 15.38%   |  8.25%  |   11.36%   |  16.81%   |   2.04%  | 5.41%|
| WALT        | 28.95%   |  8.77%  |   0.00%   |  49.12%   |   37.72%  | 0.00% |

| 方法        | v1(训练) | v1_drift(high) | v1_waber | v2 | v2_drift | v2_waber |
|:-------------:|:----------:|:----------:|:----------:|:----------:|:----------:|:----------:|
| AWM         | 79.75%   |  82.28%  |   44.30%   |  67.09%   |  63.29%   |  34.18%   |
| ASI         | 92.41%   |  97.47%  |   49.37%   |  56.96%   |  54.43%   |  32.91%   |
| SkillWeaver  | 55.84%   |  40.35%  |   29.33%   |  14.55%   |  18.87%   |  9.33%   |
| WALT         | 92.41%   |  89.87%  |   0.00%   |  55.70%   |  53.16%   |  0.00%   |


### LLM调用次数
| 方法        | v1(训练) | v1_drift(high) | v1_waber | v2 | v2_drift | v2_waber |
|:-------------:|:----------:|:----------:|:----------:|:----------:|:----------:|:----------:|
| AWM         | 8.59    | 9.17     | 9.90    | 9.59    | 9.80     | 9.42|
| ASI         | 7.68    | 8.03     | 9.37    | 9.00    | 9.39     | 9.28|
| SkillWeaver | 14.14   | 15.07    | 34.24   | 21.85   | 23.68    | 28.19|
| WALT        | 8.69    | 8.90     |  0.00   | 8.65    | 8.78     | 0.00|

| 方法        | v1(训练) | v1_drift(high) | v1_waber | v2 | v2_drift | v2_waber |
|:-------------:|:----------:|:----------:|:----------:|:----------:|:----------:|:----------:|
| AWM         |  6.85  |  8.28  |   9.36   |  6.82   |   7.42   | 9.54|
| ASI         |  7.19  |  8.30  |   8.93   |  7.50   |   7.15  | 9.11|
| SkillWeaver |  11.56  |  19.13  |   18.32   |  8.23   |   8.84  | 33.09|
| WALT        | 17.44   |  25.40  |   0.00   |  15.83   |   16.62   | 0.00 |

| 方法        | v1(训练) | v1_drift(high) | v1_waber | v2 | v2_drift | v2_waber |
|:-------------:|:----------:|:----------:|:----------:|:----------:|:----------:|:----------:|
| AWM         |  3.84  |  3.06  |   6.96   |   4.61  |   4.47  |   7.23  |
| ASI         |  3.00  |  2.38  |   7.32   |   5.18  |   4.87  |   6.62  |
| SkillWeaver  |  11.27  |  7.84  |   22.11   |   9.37  |   9.91  |   22.59  |
| WALT         |  4.37  |  4.20  |   0.00   |   13.82  |   13.58  |   0.00  |

### Skill调用次数
| 方法        | v1(训练) | v1_drift(high) | v1_waber | v2 | v2_drift |
|:-------------:|:----------:|:----------:|:----------:|:----------:|:----------:|
| AWM         | -    | -     | -    | -    | -     |
| ASI         | 0.210    | 0.302     | 0.451    | 0.284    | 0.247     |
| SkillWeaver | 0.728   | 0.796    | 0.816   | 0.710   | 1.432     |
| WALT        | 0.031    | 0.025     |  0      | 0    |  0.025    |

## 实验框架
```
1.在引入drift和waber后，性能会下降
1.1 drift程度越大，性能下降越严重。
1.2 尝试改进prompt，让agent能够适应drift脚本；如果无法通过改进prompt解决，则直接作为结论。
1.3 有一些agent完全无法处理加入waber后的场景（成功率为0%），可以在prompt中改进，如何让agent处理。在此基础上，将drift与waber两者结合。

2. 性能变化了之后应该怎么办
2.1 可以在v1_drift上进行训练（提取技能），记录开销（LLM调用次数，token数），比较drift上总结的经验与最初的经验的不同。比较经验是否改变，是否有效，是否更高效，比较两者的开销差距。

3. cost的视角
3.1 目前的Web Agent都是调用的LLM，可以训练一个7B的小模型，比较LLM与小模型的性能差距（7B），cost差距
3.2 小模型也是有必要做的，能够有类似的性能，更小的cost。
```

## API

| 方法        | API |
|:-------------:|:----------:|
| AWM         | GPT-4 (gpt-4-0613)    |
| ASI         | claude-3.5-sonnet    |
| SkillWeaver | GPT-4o   |
| WALT        | GPT-5-mini    |

## Case Study

Case 1：WALT 异常状态下的瘫痪

Case 2：Wordpress 上为什么干扰反而提升了性能？

Case 3：Magento 复杂 DOM 的脆弱性

Case 4：ASI 的进化适应