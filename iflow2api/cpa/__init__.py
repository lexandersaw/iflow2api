"""CPA (Client Protocol Attributes) 特征对齐模块。

本模块实现了与 iflow-cli 0.5.13 的网络行为严格对齐，包括：
- 请求头顺序和大小写
- 请求体 JSON 字段顺序
- 遥测协议参数完整性
- OAuth 请求特征

基于 mitmproxy 抓包数据分析实现。
"""

from .constants import (
    IFLOW_CLI_VERSION,
    NODE_VERSION_EMULATED,
    IFLOW_CLI_USER_AGENT,
    NODE_USER_AGENT,
    MMSTAT_GM_BASE,
    MMSTAT_VGIF_URL,
    CHAT_API_HEADER_ORDER,
    CHAT_BODY_FIELD_ORDER,
)
from .headers import (
    build_chat_headers,
    build_telemetry_headers,
    build_oauth_headers,
    build_vgif_headers,
)
from .body import serialize_chat_body
from .telemetry import (
    build_run_started_gokey,
    build_run_error_gokey,
    build_vgif_payload,
    generate_observation_id,
    generate_user_id_from_api_key,
)

__all__ = [
    # Constants
    "IFLOW_CLI_VERSION",
    "NODE_VERSION_EMULATED",
    "IFLOW_CLI_USER_AGENT",
    "NODE_USER_AGENT",
    "MMSTAT_GM_BASE",
    "MMSTAT_VGIF_URL",
    "CHAT_API_HEADER_ORDER",
    "CHAT_BODY_FIELD_ORDER",
    # Headers
    "build_chat_headers",
    "build_telemetry_headers",
    "build_oauth_headers",
    "build_vgif_headers",
    # Body
    "serialize_chat_body",
    # Telemetry
    "build_run_started_gokey",
    "build_run_error_gokey",
    "build_vgif_payload",
    "generate_observation_id",
    "generate_user_id_from_api_key",
]
