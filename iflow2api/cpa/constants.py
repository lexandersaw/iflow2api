"""CPA 模块常量定义。

基于 iflow-cli 0.5.13 mitmproxy 抓包数据。
"""

# iflow-cli 版本号
IFLOW_CLI_VERSION = "0.5.13"

# 模拟的 Node.js 版本
NODE_VERSION_EMULATED = "v22.22.0"

# User-Agent
IFLOW_CLI_USER_AGENT = "iFlow-Cli"
NODE_USER_AGENT = "node"

# 遥测端点
MMSTAT_GM_BASE = "https://gm.mmstat.com"
MMSTAT_VGIF_URL = "https://log.mmstat.com/v.gif"

# Chat API 请求头顺序（按 iflow-cli 0.5.13 抓包顺序）
CHAT_API_HEADER_ORDER = [
    "host",
    "connection",
    "Content-Type",
    "Authorization",
    "user-agent",
    "session-id",
    "conversation-id",
    "x-iflow-signature",
    "x-iflow-timestamp",
    "traceparent",
    "accept",
    "accept-language",
    "sec-fetch-mode",
    "accept-encoding",
    "content-length",
]

# Chat API 请求体字段顺序
CHAT_BODY_FIELD_ORDER = [
    "model",
    "messages",
    "temperature",
    "top_p",
    "max_new_tokens",
    "tools",
    "stream",
]

# 遥测请求头顺序
TELEMETRY_HEADER_ORDER = [
    "host",
    "connection",
    "Content-Type",
    "accept",
    "accept-language",
    "sec-fetch-mode",
    "user-agent",
    "accept-encoding",
    "content-length",
]

# v.gif 请求头顺序
VGIF_HEADER_ORDER = [
    "host",
    "connection",
    "content-type",
    "cache-control",
    "accept",
    "accept-language",
    "sec-fetch-mode",
    "user-agent",
    "accept-encoding",
    "content-length",
]

# OAuth getUserInfo 请求头顺序
OAUTH_HEADER_ORDER = [
    "host",
    "connection",
    "accept",
    "accept-language",
    "sec-fetch-mode",
    "user-agent",
    "accept-encoding",
]
