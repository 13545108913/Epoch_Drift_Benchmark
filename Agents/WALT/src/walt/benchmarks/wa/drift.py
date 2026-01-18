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