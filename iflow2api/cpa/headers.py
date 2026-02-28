"""CPA 请求头模板。

实现请求头的精确顺序和大小写匹配，基于 iflow-cli 0.5.13 抓包数据。
"""

from typing import List, Tuple, Optional

from .constants import (
    IFLOW_CLI_USER_AGENT,
    NODE_USER_AGENT,
)


def build_chat_headers(
    host: str,
    api_key: str,
    session_id: str,
    conversation_id: str,
    signature: str,
    timestamp: str,
    traceparent: str,
    content_length: int,
) -> List[Tuple[str, str]]:
    """
    构建 Chat API 请求头（按 iflow-cli 0.5.13 抓包顺序）。

    Args:
        host: 目标主机名
        api_key: API 密钥
        session_id: 会话ID (格式: session-{uuid})
        conversation_id: 对话ID (uuid格式)
        signature: HMAC-SHA256 签名
        timestamp: 毫秒时间戳
        traceparent: W3C Trace Context
        content_length: 请求体长度

    Returns:
        List[Tuple[str, str]]: 有序请求头列表，可直接传递给 HTTP 客户端
    """
    return [
        ("host", host),
        ("connection", "keep-alive"),
        ("Content-Type", "application/json"),
        ("Authorization", f"Bearer {api_key}"),
        ("user-agent", IFLOW_CLI_USER_AGENT),
        ("session-id", session_id),
        ("conversation-id", conversation_id),
        ("x-iflow-signature", signature),
        ("x-iflow-timestamp", timestamp),
        ("traceparent", traceparent),
        ("accept", "*/*"),
        ("accept-language", "*"),
        ("sec-fetch-mode", "cors"),
        ("accept-encoding", "br, gzip, deflate"),
        ("content-length", str(content_length)),
    ]


def build_telemetry_headers(
    host: str,
    content_length: int,
) -> List[Tuple[str, str]]:
    """
    构建遥测请求头（用于 aitrack.lifecycle.* 端点）。

    Args:
        host: 目标主机名 (gm.mmstat.com)
        content_length: 请求体长度

    Returns:
        List[Tuple[str, str]]: 有序请求头列表
    """
    return [
        ("host", host),
        ("connection", "keep-alive"),
        ("Content-Type", "application/json"),
        ("accept", "*/*"),
        ("accept-language", "*"),
        ("sec-fetch-mode", "cors"),
        ("user-agent", NODE_USER_AGENT),
        ("accept-encoding", "br, gzip, deflate"),
        ("content-length", str(content_length)),
    ]


def build_vgif_headers(
    host: str,
    content_length: int,
) -> List[Tuple[str, str]]:
    """
    构建 v.gif 埋点请求头。

    Args:
        host: 目标主机名 (log.mmstat.com)
        content_length: 请求体长度

    Returns:
        List[Tuple[str, str]]: 有序请求头列表
    """
    return [
        ("host", host),
        ("connection", "keep-alive"),
        ("content-type", "text/plain;charset=UTF-8"),
        ("cache-control", "no-cache"),
        ("accept", "*/*"),
        ("accept-language", "*"),
        ("sec-fetch-mode", "cors"),
        ("user-agent", NODE_USER_AGENT),
        ("accept-encoding", "br, gzip, deflate"),
        ("content-length", str(content_length)),
    ]


def build_oauth_headers(
    host: str,
) -> List[Tuple[str, str]]:
    """
    构建 OAuth getUserInfo 请求头。

    Args:
        host: 目标主机名 (iflow.cn)

    Returns:
        List[Tuple[str, str]]: 有序请求头列表
    """
    return [
        ("host", host),
        ("connection", "keep-alive"),
        ("accept", "*/*"),
        ("accept-language", "*"),
        ("sec-fetch-mode", "cors"),
        ("user-agent", NODE_USER_AGENT),
        ("accept-encoding", "br, gzip, deflate"),
    ]


def headers_to_dict(headers: List[Tuple[str, str]]) -> dict:
    """
    将有序请求头列表转换为字典。

    注意：Python 3.7+ dict 保持插入顺序，但转换为 dict 后
    HTTP 客户端可能会重新排序。对于需要严格顺序的场景，
    请直接使用 List[Tuple] 格式。

    Args:
        headers: 有序请求头列表

    Returns:
        dict: 请求头字典
    """
    return dict(headers)
