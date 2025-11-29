import random

class DriftInjector:
    def __init__(self):
        pass

    def _get_visual_drift_css(self, intensity: str) -> str:
        """
        根据强度生成 CSS 样式。
        Low: 轻微的背景色变化，行高调整（干扰视觉定位但不破坏布局）。
        Medium: 字体变更（影响 OCR），按钮颜色反转，去圆角。
        High: 全局字体间距（破坏文本分割），轻微旋转（破坏坐标），高对比度/反色。
        """
        css_parts = []

        # 1. 基础样式库
        if intensity == "low":
            # 轻微干扰：修改背景色，微调行高
            css_parts.append("body { background-color: #f9f9f9 !important; line-height: 1.6 !important; }")
            css_parts.append("a { text-decoration: underline !important; }")
        
        elif intensity == "medium":
            # 中度干扰：修改字体（影响基于像素的定位和OCR），修改按钮样式
            css_parts.append("body, * { font-family: 'Courier New', monospace !important; }")
            css_parts.append("button, .btn { border-radius: 0px !important; background-color: #4a90e2 !important; color: #fff !important; border: 2px solid #000 !important; }")
            css_parts.append("input { background-color: #fff8dc !important; }")

        elif intensity == "high":
            # 高度干扰：字母间距（破坏分词），元素轻微旋转（破坏精确坐标点击），强制反色
            css_parts.append("* { letter-spacing: 1.5px !important; word-spacing: 2px !important; }")
            # 极轻微旋转，通常会让基于坐标的点击失效，但人类还能操作
            css_parts.append("div, p, span { transform: rotate(0.2deg); }") 
            css_parts.append("body { filter: contrast(120%); }")
            css_parts.append("button, .btn { border: 3px dashed red !important; font-weight: bold !important; }")

        # 既然看不见属性变化，我们可以临时修改 CSS，让被修改了 DOM 的元素“显形”。
        # css_parts.append("""
        #     /* 让被移除了 testid 或被修改属性的元素显示红框 */
        #     [data-drifted-id] { border: 2px solid red !important; box-shadow: 0 0 5px red !important; }
            
        #     /* 让被添加了随机 class 的元素背景变黄 (半透明) */
        #     .drift-c { background-color: rgba(255, 255, 0, 0.2) !important; }
            
        #     /* 让被替换标签的元素显示绿框 */
        #     [data-drifted-tag] { border: 2px solid green !important; }
        # """)

        # 压缩为一行
        return " ".join(css_parts).replace("\n", " ")

    def _get_mutation_params(self, intensity: str) -> dict:
        """
        根据强度定义 DOM 变异的概率参数
        """
        if intensity == "low":
            return {
                "remove_testid_prob": 0.1,    # 10% 概率移除 id
                "add_class_prob": 0.2,        # 20% 概率添加垃圾 class
                "enable_tag_replace": False,  # 不改变标签结构
                "attr_noise_prob": 0.1        # 10% 概率修改 data 属性值
            }
        elif intensity == "medium":
            return {
                "remove_testid_prob": 0.4,    # 40% 概率移除 id
                "add_class_prob": 0.5,        # 50% 概率添加垃圾 class
                "enable_tag_replace": True,   # 开启简单标签替换 (b -> strong)
                "attr_noise_prob": 0.3
            }
        elif intensity == "high":
            return {
                "remove_testid_prob": 0.8,    # 80% 概率移除关键 id (迫使 Agent 用文本定位)
                "add_class_prob": 0.9,        # 几乎所有元素都加垃圾 class
                "enable_tag_replace": True,   # 开启标签替换
                "attr_noise_prob": 0.6        # 高概率污染属性值
            }
        return self._get_mutation_params("medium")

    def generate_drift_script(self, drift_type: str, intensity: str) -> str:
        """
        生成带有强度控制的 JS 注入脚本。
        """
        params = self._get_mutation_params(intensity)
        script_parts = []
        
        # Log 用于调试
        script_parts.append(f"console.log('[DriftInjector] Intensity: {intensity}, Type: {drift_type}');")

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
                    console.log('[DriftInjector] Styles injected.');
                }};
            """)
        else:
            script_parts.append("const injectStyles = () => {};")

        # === Part 2: DOM Mutation Logic ===
        mutation_logic = ""
        
        # Locator Drift: 针对 data-testid, id, class 等属性进行干扰
        if "locator" in drift_type or drift_type == "all":
            mutation_logic += f"""
                // 1. 干扰 data-testid (Agent 最常用的定位符)
                if (node.getAttribute && node.getAttribute('data-testid')) {{
                    if (!node.getAttribute('data-drifted-id')) {{
                        const r = Math.random();
                        if (r < {params['remove_testid_prob']}) {{
                            // 移除属性
                            node.removeAttribute('data-testid');
                        }} else if (r < {params['remove_testid_prob']} + {params['attr_noise_prob']}) {{
                            // 修改属性值 (加后缀)
                            node.setAttribute('data-testid', node.getAttribute('data-testid') + '__drifted');
                        }}
                        node.setAttribute('data-drifted-id', 'true'); // 防止重复处理
                    }}
                }}

                // 2. 干扰 Class (增加噪声，防止基于 strict class match 定位)
                if (node.classList && !node.classList.contains('drift-c')) {{
                    if (Math.random() < {params['add_class_prob']}) {{
                        node.classList.add('drift-' + Math.random().toString(36).substring(7));
                        node.classList.add('drift-c'); // 标记已处理
                    }}
                }}
            """

        # Structural Drift: 改变 HTML 标签结构
        if ("structural" in drift_type or drift_type == "all") and params['enable_tag_replace']:
            mutation_logic += """
                // 标签替换：不改变语义，但改变 XPath 结构
                // 例如: b -> strong, i -> em
                // 注意：这必须非常小心，不能破坏 Vue 的事件绑定，通常只替换纯展示标签
                
                const tagMap = { 'B': 'STRONG', 'I': 'EM', 'SPAN': 'LABEL' };
                if (tagMap[node.tagName] && !node.getAttribute('data-drifted-tag')) {
                     // 仅当节点没有复杂的 Vue 属性时尝试替换（简化判断）
                     // 在真实 Vue 环境彻底替换标签风险很高，这里做保守处理：
                     // 仅修改 innerHTML 简单的节点
                     if (node.children.length === 0 && node.textContent.length < 50) {
                        const newTag = tagMap[node.tagName];
                        const newEl = document.createElement(newTag);
                        newEl.innerHTML = node.innerHTML;
                        // 复制 class
                        newEl.className = node.className;
                        newEl.setAttribute('data-drifted-tag', 'true');
                        
                        // 替换
                        try {
                            node.parentNode.replaceChild(newEl, node);
                        } catch(e) {}
                     }
                }
            """

        # === Part 3: Execution & Observer ===
        # 包含防抖、等待 Body、递归处理子节点的逻辑
        script_parts.append(f"""
            const applyDrift = (node) => {{
                if (!node || node.nodeType !== 1) return; // 仅处理元素节点
                try {{
                    {mutation_logic}
                }} catch (e) {{
                    // 忽略错误，防止阻塞页面脚本
                }}
            }};

            const startObserver = () => {{
                const target = document.body || document.documentElement;
                if (!target) {{
                    requestAnimationFrame(startObserver);
                    return;
                }}

                injectStyles();

                // 初始遍历 (处理已存在的 DOM)
                document.querySelectorAll('*').forEach(applyDrift);

                // 监听后续变化 (AJAX, Vue Re-render)
                const observer = new MutationObserver((mutations) => {{
                    mutations.forEach((mutation) => {{
                        mutation.addedNodes.forEach((node) => {{
                            if (node.nodeType === 1) {{
                                applyDrift(node);
                                // 深度优先，处理新插入子树中的所有节点
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