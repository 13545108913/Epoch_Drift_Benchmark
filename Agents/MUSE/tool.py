import importlib
import inspect
import json
import os
import re
from typing import Callable, List, Union, get_origin, get_args, Dict, Any


class ToolRegistry:
    def __init__(self):
        self.tools = {}

    def register_tool(self, tool_name: str, tool_func: Callable):
        self.tools[tool_name] = tool_func

    def get_tool(self, tool_name: str):
        return self.tools.get(tool_name)

    def load_module_tools(self, module_name: str):
        try:
            module = importlib.import_module(f"toolbox.{module_name}")

            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (
                        callable(attr)
                        and not attr_name.startswith('_')
                        and getattr(attr, '__module__', None) == module.__name__  # 检查函数是否定义在当前模块中
                ):
                    self.register_tool(attr_name, attr)
        except Exception as e:
            print(f"Error loading module 'toolbox.{module_name}': {e}")

    def load_tools(self, tools_folder: str="toolbox", modules: List[str] = None):
        if modules is None:
            modules = [
                filename[:-3] for filename in os.listdir(tools_folder)
                if filename.endswith('.py') and filename != '__init__.py'
            ]

        for module_name in modules:
            self.load_module_tools(module_name)


def generate_tool_schema(func: Callable, enhance_des: str | None = None) -> str:

    TYPE_MAPPING = {
        int: "integer",
        float: "number",
        str: "string",
        bool: "boolean",
        list: "array",
        tuple: "array",
        dict: "object",
        type(None): "null"
    }

    func_name = func.__name__
    doc = inspect.getdoc(func)
    signature = inspect.signature(func)

    parameters = {
        "type": "object",
        "properties": {},
        "required": []
    }

    param_descriptions = {}
    if doc:
        match = re.search(r"Args:\s*(.*?)(?=\s*(?:Returns:|$))", doc, re.DOTALL)
        if match:
            args_section = match.group(1)
            param_lines = args_section.strip().splitlines()
            for line in param_lines:
                param_match = re.match(r"\s*(\w+)\s*:\s*(.*?)\s*$", line.strip())
                if param_match:
                    param_name, param_desc = param_match.groups()
                    param_descriptions[param_name] = param_desc.strip()

    for param_name, param in signature.parameters.items():
        param_type = param.annotation
        if param_type == inspect._empty:
            param_type = str

        if get_origin(param_type) is Union:
            possible_types = get_args(param_type)
            param_info = {"oneOf": []}
            for possible_type in possible_types:
                if get_origin(possible_type) is list:
                    param_info["oneOf"].append({
                        "type": "array",
                        "items": {
                            "type": TYPE_MAPPING.get(get_args(possible_type)[0], "string")
                        }
                    })
                else:
                    param_info["oneOf"].append({"type": TYPE_MAPPING.get(possible_type, "string")})
        elif get_origin(param_type) is list:
            param_info = {
                "type": "array",
                "items": {
                    "type": TYPE_MAPPING.get(get_args(param_type)[0], "string")
                }
            }
        else:
            param_info = {"type": TYPE_MAPPING.get(param_type, "string")}

        if param_name in param_descriptions:
            param_info["description"] = param_descriptions[param_name]
        else:
            param_info["description"] = f"WARNING: There is currently no parameter description for `{param_name}`"

        if param.default != inspect._empty:
            param_info["default"] = param.default

        parameters["properties"][param_name] = param_info

        if param.default == inspect._empty:
            parameters["required"].append(param_name)

    if enhance_des is not None:
        func_des = enhance_des
    elif doc:
        func_des = doc.split("\nArgs:")[0]
    else:
        func_des = "WARNING: There is currently no tool description"

    tool_schema = {
        "type": "function",
        "function": {
            "name": func_name,
            "description": func_des,
            "parameters": parameters
        }
    }

    return json.dumps(tool_schema, ensure_ascii=False)

def generate_tool_des(func: Callable) -> str:
    doc = inspect.getdoc(func)

    if doc:
        match = re.split(r"\n\s*Args:\s*", doc, maxsplit=1)
        func_des = match[0].strip() if match else doc.strip()
    else:
        func_des = "WARNING: There is currently no tool description"

    return func_des
