from __future__ import annotations

import json
import logging
import os
from typing import Any, Optional, Type

from langchain_core.messages import (
	AIMessage,
	BaseMessage,
	HumanMessage,
	SystemMessage,
	ToolMessage,
)

logger = logging.getLogger(__name__)


# def extract_json_from_model_output(content: str) -> dict:
# 	"""Extract JSON from model output, handling both plain JSON and code-block-wrapped JSON."""
# 	try:
# 		# If content is wrapped in code blocks, extract just the JSON part
# 		if '```' in content:
# 			# Find the JSON content between code blocks
# 			content = content.split('```')[1]
# 			# Remove language identifier if present (e.g., 'json\n')
# 			if '\n' in content:
# 				content = content.split('\n', 1)[1]
# 		try:
# 			return json.loads(content)
# 		except json.JSONDecodeError as e:
# 			# try and parse the largest dictionary
# 			content = content.split('{')[1].split('}')[0]
# 			return json.loads(content)
# 	except json.JSONDecodeError as e:
# 		logger.warning(f'Failed to parse model output: {content} {str(e)}')
# 		raise ValueError('Could not parse response.')

import logging
# 引入 json_repair
from json_repair import repair_json


def extract_json_from_model_output(content: str) -> dict:
    """
    Extract and parse JSON from model output using json_repair.
    Handles:
    - Conversational text wrapping (DeepSeek style)
    - Markdown code blocks
    - Malformed JSON (missing quotes, trailing commas, etc.)
    """
    if not content:
        raise ValueError("Model output is empty.")

    try:
        # repair_json(..., return_objects=True) 会尝试自动提取并修复 JSON，
        # 直接返回 Python 的 dict 或 list，无需再调用 json.loads
        parsed_result = repair_json(content, return_objects=True)

        # 二次检查：确保解析出来的是字典或列表，而不是为了修复而强行变成的字符串
        if isinstance(parsed_result, (dict, list)):
            return parsed_result
        
        # 如果 repair_json 没能识别出对象，可能它把整段话当成了字符串返回
        # 此时尝试手动定位第一个 '{' 和最后一个 '}' 再试一次
        start_idx = content.find('{')
        end_idx = content.rfind('}')
        
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            # 截取最有可能是 JSON 的片段
            json_fragment = content[start_idx : end_idx + 1]
            parsed_fragment = repair_json(json_fragment, return_objects=True)
            if isinstance(parsed_fragment, (dict, list)):
                return parsed_fragment

        # 如果都失败了，抛出异常
        raise ValueError(f"Result is not a valid JSON object/list. Got type: {type(parsed_result)}")

    except Exception as e:
        # 记录前200个字符用于调试
        error_snippet = content[:200].replace('\n', ' ') 
        logger.error(f"Failed to parse model output with json_repair. Error: {e}. Content preview: {error_snippet}...")
        raise ValueError(f"Could not parse response. Content: {content[:100]}...")


def convert_input_messages(input_messages: list[BaseMessage], model_name: Optional[str]) -> list[BaseMessage]:
	"""Convert input messages to a format that is compatible with the planner model"""
	if model_name is None:
		return input_messages
	if model_name == 'deepseek-reasoner' or model_name.startswith('deepseek-r1'):
		input_messages = _convert_messages_for_non_function_calling_models(input_messages)
		input_messages = _merge_successive_messages(input_messages, HumanMessage)
		input_messages = _merge_successive_messages(input_messages, AIMessage)
	elif "o3-mini" in model_name:
		input_messages = _convert_messages_for_non_function_calling_models(input_messages)
	return input_messages


def _convert_messages_for_non_function_calling_models(input_messages: list[BaseMessage]) -> list[BaseMessage]:
	"""Convert messages for non-function-calling models"""
	output_messages = []
	for message in input_messages:
		if isinstance(message, HumanMessage):
			output_messages.append(message)
		elif isinstance(message, SystemMessage):
			output_messages.append(message)
		elif isinstance(message, ToolMessage):
			output_messages.append(HumanMessage(content=message.content))
		elif isinstance(message, AIMessage):
			# check if tool_calls is a valid JSON object
			if message.tool_calls:
				tool_calls = json.dumps(message.tool_calls)
				output_messages.append(AIMessage(content=tool_calls))
			else:
				output_messages.append(message)
		else:
			raise ValueError(f'Unknown message type: {type(message)}')
	return output_messages


def _merge_successive_messages(messages: list[BaseMessage], class_to_merge: Type[BaseMessage]) -> list[BaseMessage]:
	"""Some models like deepseek-reasoner dont allow multiple human messages in a row. This function merges them into one."""
	merged_messages = []
	streak = 0
	for message in messages:
		if isinstance(message, class_to_merge):
			streak += 1
			if streak > 1:
				if isinstance(message.content, list):
					merged_messages[-1].content += message.content[0]['text']  # type:ignore
				else:
					merged_messages[-1].content += message.content
			else:
				merged_messages.append(message)
		else:
			merged_messages.append(message)
			streak = 0
	return merged_messages


def save_conversation(input_messages: list[BaseMessage], response: Any, target: str, encoding: Optional[str] = None) -> None:
	"""Save conversation history to file."""

	# create folders if not exists
	os.makedirs(os.path.dirname(target), exist_ok=True)

	with open(
		target,
		'w',
		encoding=encoding,
	) as f:
		_write_messages_to_file(f, input_messages)
		_write_response_to_file(f, response)


def _write_messages_to_file(f: Any, messages: list[BaseMessage]) -> None:
	"""Write messages to conversation file"""
	for message in messages:
		f.write(f' {message.__class__.__name__} \n')

		if isinstance(message.content, list):
			for item in message.content:
				if isinstance(item, dict) and item.get('type') == 'text':
					f.write(item['text'].strip() + '\n')
		elif isinstance(message.content, str):
			try:
				content = json.loads(message.content)
				f.write(json.dumps(content, indent=2) + '\n')
			except json.JSONDecodeError:
				f.write(message.content.strip() + '\n')

		f.write('\n')


def _write_response_to_file(f: Any, response: Any) -> None:
	"""Write model response to conversation file"""
	f.write(' RESPONSE\n')
	f.write(json.dumps(json.loads(response.model_dump_json(exclude_unset=True)), indent=2))
