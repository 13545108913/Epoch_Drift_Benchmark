"""
Code Parser Utilities

Utilities for parsing and extracting code from LLM responses and trajectories.
"""

import ast
import re
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class FunctionInfo:
    """Information about a parsed function."""
    name: str
    signature: str
    docstring: str
    body: str
    parameters: List[str]
    return_type: Optional[str] = None
    line_number: int = 0


class CodeParser:
    """Utilities for parsing Python code from various sources."""
    
    @staticmethod
    def extract_code_blocks(text: str, language: str = "python") -> List[str]:
        """
        Extract code blocks from markdown-formatted text.
        
        Args:
            text: Text containing code blocks
            language: Programming language to extract (default: python)
            
        Returns:
            List of code block contents
        """
        blocks = []
        
        # Pattern for specific language blocks
        lang_pattern = rf'```{language}\n(.*?)\n```'
        matches = re.findall(lang_pattern, text, re.DOTALL | re.IGNORECASE)
        blocks.extend([match.strip() for match in matches if match.strip()])
        
        # If no language-specific blocks found, try generic code blocks
        if not blocks:
            generic_pattern = r'```\n(.*?)\n```'
            matches = re.findall(generic_pattern, text, re.DOTALL)
            # Filter for Python-like code
            for match in matches:
                code = match.strip()
                if ('def ' in code or 'class ' in code or 
                    'import ' in code or 'from ' in code):
                    blocks.append(code)
        
        return blocks
    
    @staticmethod
    def extract_functions(code: str) -> List[FunctionInfo]:
        """
        Extract function information from Python code.
        
        Args:
            code: Python code string
            
        Returns:
            List of FunctionInfo objects
        """
        functions = []
        
        try:
            # Parse the AST
            tree = ast.parse(code)
            
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    func_info = CodeParser._parse_function_node(node, code)
                    if func_info:
                        functions.append(func_info)
        
        except SyntaxError as e:
            logger.warning(f"Syntax error parsing code: {e}")
            # Fall back to regex-based parsing
            functions = CodeParser._regex_parse_functions(code)
        
        return functions
    
    @staticmethod
    def _parse_function_node(node: ast.FunctionDef, code: str) -> Optional[FunctionInfo]:
        """Parse a function AST node."""
        try:
            # Get function name
            name = node.name
            
            # Get parameters
            params = []
            for arg in node.args.args:
                params.append(arg.arg)
            
            # Get docstring
            docstring = ""
            if (node.body and isinstance(node.body[0], ast.Expr) and
                isinstance(node.body[0].value, ast.Constant) and
                isinstance(node.body[0].value.value, str)):
                docstring = node.body[0].value.value.strip()
            
            # Get signature by extracting from code
            code_lines = code.split('\n')
            signature = ""
            body = ""
            
            func_start = None
            for i, line in enumerate(code_lines):
                if f"def {name}" in line:
                    func_start = i
                    break
            
            if func_start is not None:
                # Extract signature
                paren_count = 0
                sig_lines = []
                for i in range(func_start, len(code_lines)):
                    line = code_lines[i]
                    sig_lines.append(line)
                    paren_count += line.count('(') - line.count(')')
                    if paren_count == 0 and ':' in line:
                        signature = '\n'.join(sig_lines)
                        
                        # Extract body
                        body_lines = code_lines[i+1:]
                        body = '\n'.join(body_lines)
                        break
            
            return FunctionInfo(
                name=name,
                signature=signature.strip(),
                docstring=docstring,
                body=body.strip(),
                parameters=params,
                line_number=getattr(node, 'lineno', 0)
            )
        
        except Exception as e:
            logger.error(f"Error parsing function node: {e}")
            return None
    
    @staticmethod
    def _regex_parse_functions(code: str) -> List[FunctionInfo]:
        """Parse functions using regex as fallback."""
        functions = []
        
        # Pattern to match function definitions
        func_pattern = r'def\s+(\w+)\s*\([^)]*\):'
        
        for match in re.finditer(func_pattern, code):
            name = match.group(1)
            
            # Try to extract more details
            start_pos = match.start()
            lines_before = code[:start_pos].count('\n')
            
            # Simple extraction - just the function name
            func_info = FunctionInfo(
                name=name,
                signature=match.group(0),
                docstring="",
                body="",
                parameters=[],
                line_number=lines_before + 1
            )
            
            functions.append(func_info)
        
        return functions
    
    @staticmethod
    def validate_python_syntax(code: str) -> Tuple[bool, Optional[str]]:
        """
        Validate Python code syntax.
        
        Args:
            code: Python code to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            ast.parse(code)
            return True, None
        except SyntaxError as e:
            return False, str(e)
        except Exception as e:
            return False, f"Unexpected error: {str(e)}"
    
    @staticmethod
    def get_function_names(code: str, exclude: List[str] = None) -> List[str]:
        """
        Get all function names from code.
        
        Args:
            code: Python code
            exclude: List of function names to exclude
            
        Returns:
            List of function names
        """
        exclude = exclude or []
        functions = CodeParser.extract_functions(code)
        return [func.name for func in functions if func.name not in exclude]
    
    @staticmethod
    def count_function_definitions(code: str) -> int:
        """Count the number of function definitions in code."""
        return len(re.findall(r'def\s+\w+\s*\(', code))
    
    @staticmethod
    def extract_imports(code: str) -> List[str]:
        """Extract import statements from code."""
        imports = []
        
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append(f"import {alias.name}")
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    for alias in node.names:
                        imports.append(f"from {module} import {alias.name}")
        
        except SyntaxError:
            # Fall back to regex
            import_pattern = r'^(import\s+\w+|from\s+\w+\s+import\s+\w+)'
            for line in code.split('\n'):
                if re.match(import_pattern, line.strip()):
                    imports.append(line.strip())
        
        return imports
    
    @staticmethod
    def clean_code(code: str) -> str:
        """Clean and normalize code."""
        lines = code.split('\n')
        cleaned_lines = []
        
        for line in lines:
            # Remove trailing whitespace
            line = line.rstrip()
            
            # Remove inline comments but preserve docstrings
            if '#' in line and not ('"""' in line or "'''" in line):
                comment_pos = line.find('#')
                # Make sure # is not inside a string
                before_hash = line[:comment_pos]
                if before_hash.count('"') % 2 == 0 and before_hash.count("'") % 2 == 0:
                    line = line[:comment_pos].rstrip()
            
            if line:  # Skip empty lines
                cleaned_lines.append(line)
        
        return '\n'.join(cleaned_lines)


class TrajectoryParser:
    """Utilities for parsing trajectory data."""
    
    @staticmethod
    def extract_actions(trajectory_data: Any) -> List[str]:
        """Extract action strings from trajectory data."""
        actions = []
        
        if hasattr(trajectory_data, 'actions'):
            # Protobuf trajectory
            for action_data in trajectory_data.actions:
                if hasattr(action_data, 'action') and action_data.action:
                    actions.append(str(action_data.action))
        
        elif isinstance(trajectory_data, dict):
            if 'actions' in trajectory_data:
                for action in trajectory_data['actions']:
                    if isinstance(action, str):
                        actions.append(action)
                    elif isinstance(action, dict) and 'action' in action:
                        actions.append(str(action['action']))
            
            elif 'steps' in trajectory_data:
                for step in trajectory_data['steps']:
                    if isinstance(step, dict) and 'action' in step:
                        actions.append(str(step['action']))
        
        return [action for action in actions if action.strip()]
    
    @staticmethod
    def parse_action_sequence(actions: List[str]) -> Dict[str, Any]:
        """Parse action sequence to extract patterns."""
        patterns = {
            'click_count': 0,
            'fill_count': 0,
            'navigate_count': 0,
            'common_selectors': [],
            'action_types': []
        }
        
        selectors = []
        
        for action in actions:
            action_lower = action.lower()
            
            # Count action types
            if 'click' in action_lower:
                patterns['click_count'] += 1
                patterns['action_types'].append('click')
            elif 'fill' in action_lower or 'type' in action_lower:
                patterns['fill_count'] += 1
                patterns['action_types'].append('fill')
            elif 'goto' in action_lower or 'navigate' in action_lower:
                patterns['navigate_count'] += 1
                patterns['action_types'].append('navigate')
            
            # Extract potential selectors
            selector_patterns = [
                r"['\"]([^'\"]*)['\"]",  # Quoted strings
                r"#[\w-]+",             # IDs
                r"\.[\w-]+",            # Classes
            ]
            
            for pattern in selector_patterns:
                matches = re.findall(pattern, action)
                selectors.extend(matches)
        
        # Find common selectors
        from collections import Counter
        selector_counts = Counter(selectors)
        patterns['common_selectors'] = [sel for sel, count in selector_counts.most_common(5)]
        
        return patterns