"""CPA 请求体格式化。

确保请求体 JSON 字段顺序与 iflow-cli 一致。
"""

import json
from typing import Any, Dict

from .constants import CHAT_BODY_FIELD_ORDER


def serialize_chat_body(body: Dict[str, Any]) -> str:
    """
    按指定顺序序列化请求体。

    Args:
        body: 请求体字典

    Returns:
        JSON 字符串，字段按 CHAT_BODY_FIELD_ORDER 顺序排列
    """
    ordered_body = {}

    # 按顺序添加已知字段
    for field in CHAT_BODY_FIELD_ORDER:
        if field in body:
            ordered_body[field] = body[field]

    # 添加其他字段（如模型特定参数）
    for key, value in body.items():
        if key not in ordered_body:
            ordered_body[key] = value

    # 使用紧凑格式，无空格
    return json.dumps(ordered_body, ensure_ascii=False, separators=(",", ":"))


def order_chat_body(body: Dict[str, Any]) -> Dict[str, Any]:
    """
    返回有序的请求体字典（用于后续处理）。

    Args:
        body: 原始请求体字典

    Returns:
        有序的请求体字典
    """
    ordered_body = {}

    # 按顺序添加已知字段
    for field in CHAT_BODY_FIELD_ORDER:
        if field in body:
            ordered_body[field] = body[field]

    # 添加其他字段
    for key, value in body.items():
        if key not in ordered_body:
            ordered_body[key] = value

    return ordered_body
