"""CPA 遥测协议实现。

完整实现 iflow-cli 的遥测参数，包括 run_started、run_error、v.gif 事件。
"""

import hashlib
import platform
import secrets
from urllib.parse import quote
from typing import Optional

from .constants import (
    IFLOW_CLI_VERSION,
    NODE_VERSION_EMULATED,
    MMSTAT_GM_BASE,
    MMSTAT_VGIF_URL,
)


def generate_observation_id() -> str:
    """
    生成 16 位十六进制观测 ID。

    Returns:
        16 位十六进制字符串
    """
    return secrets.token_hex(8)


def generate_user_id_from_api_key(api_key: str) -> str:
    """
    从 API Key 生成用户 ID。

    使用 MD5 生成确定性 UUID 格式的用户 ID。

    Args:
        api_key: API 密钥

    Returns:
        UUID 格式的用户 ID
    """
    # 使用 MD5 生成 32 位十六进制
    hash_value = hashlib.md5(api_key.encode()).hexdigest()

    # 格式化为 UUID 格式
    return f"{hash_value[:8]}-{hash_value[8:12]}-{hash_value[12:16]}-{hash_value[16:20]}-{hash_value[20:]}"


def build_run_started_gokey(
    trace_id: str,
    observation_id: str,
    session_id: str,
    conversation_id: str,
    user_id: str,
    model: str,
    tool: str = "",
) -> str:
    """
    构建 run_started 事件的 gokey 参数。

    Args:
        trace_id: 32 位十六进制追踪 ID
        observation_id: 16 位十六进制观测 ID
        session_id: 会话 ID (格式: session-{uuid})
        conversation_id: 对话 ID (uuid 格式)
        user_id: 用户 ID
        model: 模型名称
        tool: 工具名称（可选）

    Returns:
        URL 编码格式的 gokey 参数字符串
    """
    return (
        f"pid=iflow"
        f"&sam=iflow.cli.{conversation_id}.{trace_id}"
        f"&trace_id={trace_id}"
        f"&session_id={session_id}"
        f"&conversation_id={conversation_id}"
        f"&observation_id={observation_id}"
        f"&model={quote(model)}"
        f"&tool={quote(tool)}"
        f"&user_id={user_id}"
    )


def build_run_error_gokey(
    trace_id: str,
    observation_id: str,
    parent_observation_id: str,
    session_id: str,
    conversation_id: str,
    user_id: str,
    error_msg: str,
    model: str,
    tool: str = "",
    tool_name: str = "",
    tool_args: str = "",
) -> str:
    """
    构建 run_error 事件的 gokey 参数。

    Args:
        trace_id: 32 位十六进制追踪 ID
        observation_id: 16 位十六进制观测 ID
        parent_observation_id: 父观测 ID（run_started 的 observation_id）
        session_id: 会话 ID
        conversation_id: 对话 ID
        user_id: 用户 ID
        error_msg: 错误信息
        model: 模型名称
        tool: 工具名称（可选）
        tool_name: 工具名称（可选）
        tool_args: 工具参数（可选）

    Returns:
        URL 编码格式的 gokey 参数字符串
    """
    return (
        f"pid=iflow"
        f"&sam=iflow.cli.{conversation_id}.{trace_id}"
        f"&trace_id={trace_id}"
        f"&observation_id={observation_id}"
        f"&parent_observation_id={parent_observation_id}"
        f"&session_id={session_id}"
        f"&conversation_id={conversation_id}"
        f"&user_id={user_id}"
        f"&error_msg={quote(error_msg)}"
        f"&model={quote(model)}"
        f"&tool={quote(tool)}"
        f"&toolName={quote(tool_name)}"
        f"&toolArgs={quote(tool_args)}"
        f"&cliVer={IFLOW_CLI_VERSION}"
        f"&platform={platform.system().lower()}"
        f"&arch={platform.machine().lower()}"
        f"&nodeVersion={NODE_VERSION_EMULATED}"
        f"&osVersion={platform.platform()}"
    )


def build_vgif_payload(
    user_id: str,
    cna: str = "",
    screen_resolution: str = "1920x1080",
) -> str:
    """
    构建 v.gif 埋点参数。

    Args:
        user_id: 用户 ID
        cna: 阿里云追踪标识（可从 cookie 获取）
        screen_resolution: 屏幕分辨率

    Returns:
        URL 编码格式的参数字符串
    """
    # 获取平台信息
    system = platform.system()
    system_lower = system.lower()

    # 简化的平台标识
    if system_lower.startswith("win"):
        os_short = "win"
    elif system_lower == "darwin":
        os_short = "mac"
    elif system_lower == "linux":
        os_short = "linux"
    else:
        os_short = system_lower

    return (
        f"logtype=1"
        f"&title=iFlow-CLI"
        f"&pre=-"
        f"&scr={screen_resolution}"
        f"&cna={cna}"
        f"&spm-cnt=a2110qe.33796382.46182003.0.0"
        f"&aplus"
        f"&pid=iflow"
        f"&_user_id={user_id}"
        f"&cache={secrets.token_hex(3)}"
        f"&sidx=aplusSidex"
        f"&ckx=aplusCkx"
        f"&platformType=pc"
        f"&device_model={system}"
        f"&os={system}"
        f"&o={os_short}"
        f"&node_version={NODE_VERSION_EMULATED}"
        f"&language=zh_CN.UTF-8"
        f"&interactive=0"
        f"&iFlowEnv="
        f"&_g_encode=utf-8"
    )


def build_telemetry_body(gmkey: str, gokey: str) -> dict:
    """
    构建遥测请求体。

    Args:
        gmkey: 固定为 "AI"
        gokey: URL 编码的参数字符串

    Returns:
        请求体字典
    """
    return {
        "gmkey": gmkey,
        "gokey": gokey,
    }


# 遥测事件 URL
RUN_STARTED_URL = f"{MMSTAT_GM_BASE}//aitrack.lifecycle.run_started"
RUN_ERROR_URL = f"{MMSTAT_GM_BASE}//aitrack.lifecycle.run_error"
RUN_SUCCESS_URL = f"{MMSTAT_GM_BASE}//aitrack.lifecycle.run_success"
VGIF_URL = MMSTAT_VGIF_URL
