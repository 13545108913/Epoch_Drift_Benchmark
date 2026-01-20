import pandas as pd
import io

# 新的 Markdown 数据（纯数字格式）
markdown_data = """

"""

def generate_universal_latex(md_data):
    # 1. 解析 Markdown
    df = pd.read_csv(io.StringIO(md_data), sep="|", header=0, skipinitialspace=True)
    df = df.dropna(axis=1, how='all')
    df.columns = [c.strip() for c in df.columns]
    
    base_col = "v1(训练)"

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
            diff_pct = 0.0 if val_float == 0 else 100.0 # 避免除以0
        else:
            diff_pct = ((val_float - base_float) / base_float) * 100
        
        # 决定主数值的显示格式
        if is_percent:
            display_text = f"{val_float:.2f}\%"
        else:
            # 纯数字保留2位小数（可根据需要调整）
            display_text = f"{val_float:.3f}"
        
        if is_base:
            return display_text
        
        # 差异颜色与符号设置
        if diff_pct < 0:
            # 红色显示负增长
            diff_str = f"\\textcolor{{red}}{{{diff_pct:.1f}\%}}"
        elif diff_pct > 0:
            # 绿色显示正增长
            diff_str = f"\\textcolor{{green!60!black}}{{+{diff_pct:.1f}\%}}"
        else:
            diff_str = "0.0\%"
            
        # 构造 LaTeX：主数值 + 数学模式下标
        return f"{display_text}$_{{{{\\scriptscriptstyle {diff_str}}}}}$"

    # 2. 构建 LaTeX
    latex_rows = []
    header = " & ".join([f"\\textbf{{{c}}}" for c in df.columns]) + " \\\\"
    latex_rows.append(header)
    latex_rows.append("\\hline")
    
    for _, row in df.iterrows():
        row_str = []
        # 方法名
        row_str.append(row[df.columns[0]].strip())
        
        base_val = row[base_col]
        
        for col in df.columns[1:]:
            is_base = (col == base_col)
            cell_latex = format_cell(row[col], base_val, is_base)
            row_str.append(cell_latex)
            
        latex_rows.append(" & ".join(row_str) + " \\\\")

    full_latex = """
\\begin{table}[h]
\\centering
\\resizebox{\\textwidth}{!}{
\\begin{tabular}{l|c|c|c|c|c}
\\hline
""" + "\n".join(latex_rows) + """
\\hline
\\end{tabular}
}
\\caption{Performance metrics. Subscripts denote relative percentage change from v1(Training).}
\\label{tab:metrics}
\\end{table}
"""
    return full_latex

# 运行
print(generate_universal_latex(markdown_data))