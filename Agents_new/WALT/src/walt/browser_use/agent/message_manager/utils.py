from __future__ import annotations

import json
import logging
import os
from typing import Any, Optional, Type
import re

from langchain_core.messages import (
	AIMessage,
	BaseMessage,
	HumanMessage,
	SystemMessage,
	ToolMessage,
)

logger = logging.getLogger(__name__)


def extract_json_from_model_output(content: str) -> dict:
    """
    更加健壮的 JSON 提取函数。
    支持从代码块中提取，或者从混合文本中搜索最外层的 {} 结构。
    """
    try:
        # 1. 尝试直接处理代码块 (Markdown 格式)
        if '```' in content:
            # split 后取中间部分，通常索引 1 是代码块内容
            # 兼容可能有多个代码块的情况，这里取第一个非空的块
            parts = content.split('```')
            for part in parts:
                if '{' in part:
                    content = part
                    break
            
            # 去除可能的语言标识 (如 ```json)
            if content.strip().startswith('json'):
                content = content.strip()[4:]

        # 尝试直接解析
        return json.loads(content)

    except json.JSONDecodeError:
        # 2. 如果直接解析失败，尝试寻找字符串中第一个 '{' 和最后一个 '}'
        try:
            start_index = content.find('{')
            end_index = content.rfind('}')

            if start_index != -1 and end_index != -1 and end_index > start_index:
                # 提取完整的大括号闭包内容
                json_str = content[start_index : end_index + 1]
                return json.loads(json_str)
            else:
                logger.error(f"No JSON braces found in content: {content[:100]}...")
                raise ValueError('No JSON object found in response.')
                
        except json.JSONDecodeError as e:
            logger.warning(f'Failed to parse extracted JSON: {content} {str(e)}')
            raise ValueError('Could not parse response.')


def convert_input_messages(input_messages: list[BaseMessage], model_name: Optional[str]) -> list[BaseMessage]:
	"""Convert input messages to a format that is compatible with the planner model"""
	if model_name is None:
		return input_messages
	if model_name == 'deepseek-reasoner' or model_name.startswith('deepseek-r1') or model_name.startswith('claude'):
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
