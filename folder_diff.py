import os
import difflib
import filecmp
from pathlib import Path
from datetime import datetime

class PythonFileComparator:
    def __init__(self, folder_a, folder_b, output_file="diff_report.txt"):
        self.folder_a = Path(folder_a)
        self.folder_b = Path(folder_b)
        self.output_file = output_file
        
    def _get_py_files(self, folder_path):
        """递归获取文件夹下所有 .py 文件的相对路径"""
        file_paths = set()
        for root, _, files in os.walk(folder_path):
            for file in files:
                # [关键修改] 仅筛选 .py 结尾的文件
                if file.endswith('.py'):
                    full_path = Path(root) / file
                    try:
                        relative_path = full_path.relative_to(folder_path)
                        file_paths.add(relative_path)
                    except ValueError:
                        continue
        return file_paths

    def _read_file(self, file_path):
        """读取 Python 文件内容"""
        # Python 文件通常是 utf-8，偶尔有 gbk
        encodings = ['utf-8', 'gbk'] 
        for enc in encodings:
            try:
                with open(file_path, 'r', encoding=enc) as f:
                    return f.readlines()
            except (UnicodeDecodeError, PermissionError):
                continue
        return None 

    def compare(self):
        print(f"正在对比 Python 文件:\n A: {self.folder_a}\n B: {self.folder_b}\n...")
        
        # 获取文件列表
        files_a = self._get_py_files(self.folder_a)
        files_b = self._get_py_files(self.folder_b)
        
        all_files = sorted(files_a | files_b)
        
        # 写入报告
        with open(self.output_file, 'w', encoding='utf-8') as report:
            report.write(f"Python Scripts Diff Report\n")
            report.write(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            report.write(f"Folder A: {self.folder_a}\n")
            report.write(f"Folder B: {self.folder_b}\n")
            report.write("="*60 + "\n\n")

            if not all_files:
                report.write("没有找到任何 .py 文件。\n")

            for rel_path in all_files:
                path_a = self.folder_a / rel_path
                path_b = self.folder_b / rel_path
                
                # 1. 仅在 A 中
                if rel_path in files_a and rel_path not in files_b:
                    report.write(f"[-] 仅在 A 中存在: {rel_path}\n")
                    report.write("-" * 40 + "\n")
                    
                # 2. 仅在 B 中
                elif rel_path in files_b and rel_path not in files_a:
                    report.write(f"[+] 仅在 B 中存在: {rel_path}\n")
                    report.write("-" * 40 + "\n")
                    
                # 3. 都在，对比代码内容
                else:
                    if filecmp.cmp(path_a, path_b, shallow=False):
                        continue # 代码完全一致，跳过
                        
                    content_a = self._read_file(path_a)
                    content_b = self._read_file(path_b)
                    
                    if content_a is None or content_b is None:
                        report.write(f"[!] 无法读取文件编码: {rel_path}\n")
                        report.write("-" * 40 + "\n")
                    else:
                        diff = list(difflib.unified_diff(
                            content_a, 
                            content_b, 
                            fromfile=f"A/{rel_path}", 
                            tofile=f"B/{rel_path}",
                            lineterm=''
                        ))
                        
                        if diff:
                            report.write(f"[~] 代码差异: {rel_path}\n")
                            for line in diff:
                                report.write(line + "\n")
                            report.write("-" * 40 + "\n")

        print(f"对比完成！结果已保存至: {self.output_file}")

if __name__ == "__main__":
    # 配置路径
    SRC_FOLDER_1 = "Agents/WALT/src/walt" 
    SRC_FOLDER_2 = "Agents_new/WALT/src/walt" 
    OUTPUT_FILE = "diff_result.txt"

    # 清理旧结果
    if os.path.exists(OUTPUT_FILE):
        os.remove(OUTPUT_FILE)

    if not os.path.exists(SRC_FOLDER_1) or not os.path.exists(SRC_FOLDER_2):
        print("错误：路径不存在")
    else:
        comparator = PythonFileComparator(SRC_FOLDER_1, SRC_FOLDER_2, OUTPUT_FILE)
        comparator.compare()