import pandas as pd
import io

# 新的 Markdown/文本 数据（空格分隔格式）
markdown_data = """
方法	v1	v1+drift	v1+anomaly	v2	v2+drift	v2+anomaly
AWM	32.46%	31.00%	13.27%	49.11%	32.46%	10.00%
ASI	43.24%	37.72%	16.96%	42.11%	36.84%	16.67%
SkillWeaver	28.07%	26.32%	22.33%	20.65%	13.62%	12.95%
WALT	41.59%	42.48%	28.32%	61.06%	52.21%	26.55%
"""

def generate_universal_latex(md_data):
    # 1. 解析数据 (使用正则 \s+ 处理不定长空格)
    df = pd.read_csv(io.StringIO(md_data), sep=r"\s+", header=0)
    
    # 设定基准列 (用于计算下标的变化率)
    base_col = "v1"

    # 辅助函数：解析数值，同时返回原始格式是否带有%
    def parse_val(val):
        if isinstance(val, str):
            clean_val = val.strip()
            if '%' in clean_val:
                return float(clean_val.replace('%', '')), True # 是百分数
            return float(clean_val), False # 是纯数字
        return float(val), False

    # 格式化单元格
    def format_cell(val, base_val, is_base=False):
        val_float, is_percent = parse_val(val)
        base_float, _ = parse_val(base_val)
        
        # 计算相对变化率 (Relative Change)
        if base_float == 0:
            diff_pct = 0.0 if val_float == 0 else 100.0
        else:
            diff_pct = ((val_float - base_float) / base_float) * 100
        
        # 决定主数值的显示格式
        if is_percent:
            display_text = f"{val_float:.2f}\%"
        else:
            display_text = f"{val_float:.3f}"
        
        # 如果是基准列，不显示下标
        if is_base:
            return display_text
        
        # 差异颜色与符号设置
        if diff_pct < 0:
            # 红色显示负增长 (下降)
            diff_str = f"\\textcolor{{red}}{{{diff_pct:.1f}\%}}"
        elif diff_pct > 0:
            # 绿色显示正增长 (上升)
            diff_str = f"\\textcolor{{green!60!black}}{{+{diff_pct:.1f}\%}}"
        else:
            diff_str = "0.0\%"
            
        # 构造 LaTeX：主数值 + 数学模式下标
        return f"{display_text}$_{{{{\\scriptscriptstyle {diff_str}}}}}$"

    # 2. 构建 LaTeX
    latex_rows = []
    
    # 动态生成表头列定义 (例如 l|c|c|c|c...)
    num_data_cols = len(df.columns)
    col_def = "l" + "|" + "|".join(["c"] * (num_data_cols - 1))
    
    # 格式化表头 (加粗)
    header = " & ".join([f"\\textbf{{{c}}}" for c in df.columns]) + " \\\\"
    latex_rows.append(header)
    latex_rows.append("\\hline")
    
    for _, row in df.iterrows():
        row_str = []
        # 添加方法名 (第一列)
        row_str.append(row[df.columns[0]])
        
        # 获取基准值 (当前逻辑：所有列都跟 v1 比较)
        # 如果你想 v2 及其变体跟 v2 比较，可以在这里加判断逻辑
        base_val = row[base_col]
        
        # 处理数据列
        for col in df.columns[1:]:
            is_base = (col == base_col)
            # 如果想让 v2 也作为纯数值显示(不带红绿标)，可以加条件 or col == 'v2'
            cell_latex = format_cell(row[col], base_val, is_base)
            row_str.append(cell_latex)
            
        latex_rows.append(" & ".join(row_str) + " \\\\")

    full_latex = f"""
\\begin{{table}}[h]
\\centering
\\resizebox{{\\textwidth}}{{!}}{{
\\begin{{tabular}}{{{col_def}}}
\\hline
""" + "\n".join(latex_rows) + f"""
\\hline
\\end{{tabular}}
}}
\\caption{{Performance metrics. Subscripts denote relative percentage change from {base_col}.}}
\\label{{tab:metrics}}
\\end{{table}}
"""
    return full_latex

# 运行
print(generate_universal_latex(markdown_data))