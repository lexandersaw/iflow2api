# iflow2api CPA 特征严格对齐开发计划

## 1. 项目背景与目标

### 1.1 背景

当前 iflow2api 项目已经实现了与 iflow-cli 的基本网络行为对齐，包括：
- User-Agent 标识
- HMAC-SHA256 签名算法
- 基本的 HTTP 请求头
- TLS 指纹伪装（通过 curl_cffi）

但在 **CPA（Client Protocol Attributes，客户端协议特征）** 层面，仍存在与真实 iflow-cli 的差异，可能导致：
- 上游服务识别为非官方客户端
- 请求被限流或拒绝
- 部分功能不可用

### 1.2 目标

实现与 iflow-cli 网络行为的 **100% 特征对齐**，包括：

1. **TLS/SSL 指纹**：完全模拟 Node.js 的 TLS 握手特征
2. **HTTP 请求头**：严格对齐 iflow-cli 的头部顺序、大小写、默认值
3. **请求体格式**：对齐 JSON 序列化细节、字段顺序
4. **连接行为**：对齐连接池、Keep-Alive、超时行为
5. **遥测协议**：完整实现 iflow-cli 的埋点上报逻辑
6. **OAuth 流程**：对齐认证请求的完整特征

---

## 2. 真实流量分析（基于 mitmproxy 抓包）

> 数据来源：`tmp_iflow_mitm_report.json` - iflow-cli 0.5.13 实际请求抓包

### 2.1 抓包概览

| 指标 | 值 |
|------|-----|
| iflow-cli 版本 | 0.5.13 |
| Node.js 版本 | v22.22.0 |
| 总请求数 | 5 |
| 请求端点 | 4 个不同 URL |

### 2.2 API 请求详情

#### 2.2.1 Chat Completions API 请求头（已验证）

**URL**: `https://apis.iflow.cn:443/v1/chat/completions`

**请求头完整顺序**：
```http
host: apis.iflow.cn
connection: keep-alive
Content-Type: application/json
Authorization: Bearer sk-c21c5d72452b5a7e156cd7c480ac0d58
user-agent: iFlow-Cli
session-id: session-54b39cbf-ccc7-49d8-9259-c2cfcb1be915
conversation-id: 3dfc232f-3358-434a-a382-a1262f645486
x-iflow-signature: f44f70a513ac1f977c69252cf03a799ccf103027cbdea7f7b3f1e5d94adeb8ca
x-iflow-timestamp: 1772019048397
traceparent: 00-41dc44a0aca8b038a8c1dc8b7c66def0-b4ec50c0a50fbedb-01
accept: */*
accept-language: *
sec-fetch-mode: cors
accept-encoding: br, gzip, deflate
content-length: 76601
```

**关键发现**：
1. 使用 **HTTP/1.1** 协议（非 HTTP/2）
2. 头部名称为**小写**（`host`, `connection`, `Content-Type` 混合）
3. `user-agent` 为 `iFlow-Cli`（无版本号）
4. 签名和时间戳字段名使用**小写** `x-iflow-signature`, `x-iflow-timestamp`

#### 2.2.2 遥测请求详情（已验证）

##### run_started 事件

**URL**: `https://gm.mmstat.com:443//aitrack.lifecycle.run_started`

**请求头**：
```http
host: gm.mmstat.com
connection: keep-alive
Content-Type: application/json
accept: */*
accept-language: *
sec-fetch-mode: cors
user-agent: node
accept-encoding: br, gzip, deflate
content-length: 364
```

**请求体**：
```json
{
  "gmkey": "AI",
  "gokey": "pid=iflow&sam=iflow.cli.3dfc232f-3358-434a-a382-a1262f645486.41dc44a0aca8b038a8c1dc8b7c66def0&trace_id=41dc44a0aca8b038a8c1dc8b7c66def0&session_id=session-54b39cbf-ccc7-49d8-9259-c2cfcb1be915&conversation_id=3dfc232f-3358-434a-a382-a1262f645486&observation_id=cb0c0010a58b19ea&model=glm-5&tool=&user_id=9b4ceeaa-815d-462d-a5ba-07fb176dbcdc"
}
```

**参数解析**：
| 参数 | 值 | 说明 |
|------|-----|------|
| pid | iflow | 产品标识 |
| sam | iflow.cli.{conversation_id}.{trace_id} | 采样标识 |
| trace_id | 32位十六进制 | 追踪ID |
| session_id | session-{uuid} | 会话ID |
| conversation_id | {uuid} | 对话ID |
| observation_id | 16位十六进制 | 观测ID |
| model | glm-5 | 模型名称 |
| tool | 空 | 工具名称 |
| user_id | {uuid} | 用户ID（基于 api_key 生成） |

##### run_error 事件

**URL**: `https://gm.mmstat.com:443//aitrack.lifecycle.run_error`

**额外参数**：
| 参数 | 值 | 说明 |
|------|-----|------|
| parent_observation_id | cb0c0010a58b19ea | 父观测ID（run_started 的 observation_id） |
| error_msg | URL编码的错误信息 | 错误详情 |
| cliVer | 0.5.13 | CLI 版本号 |
| platform | win32 | 平台标识 |
| arch | x64 | 架构 |
| nodeVersion | v22.22.0 | Node.js 版本 |
| osVersion | Windows 11 Pro | 操作系统版本 |
| toolName | 空 | 工具名称 |
| toolArgs | 空 | 工具参数 |

##### v.gif 埋点

**URL**: `https://log.mmstat.com:443/v.gif`

**请求头**：
```http
host: log.mmstat.com
connection: keep-alive
content-type: text/plain;charset=UTF-8
cache-control: no-cache
accept: */*
accept-language: *
sec-fetch-mode: cors
user-agent: node
accept-encoding: br, gzip, deflate
content-length: 354
```

**请求体（URL 编码格式）**：
```
logtype=1&title=iFlow-CLI&pre=-&scr=2560x1440&cna=xOgYIrn2IG8CAXEMMWYwga6u&spm-cnt=a2110qe.33796382.46182003.0.0&aplus&pid=iflow&_user_id=9b4ceeaa-815d-462d-a5ba-07fb176dbcdc&cache=5c1bf02&sidx=aplusSidex&ckx=aplusCkx&platformType=pc&device_model=Windows&os=Windows&o=win&node_version=v22.22.0&language=zh_CN.UTF-8&interactive=0&iFlowEnv=&_g_encode=utf-8
```

**关键发现**：
1. v.gif 使用 `text/plain;charset=UTF-8` 而非 JSON
2. 请求体为 URL 编码格式（form-urlencoded）
3. 包含屏幕分辨率 `scr=2560x1440`
4. 包含 `cna` cookie 值（阿里云追踪标识）
5. 包含 `aplus` 相关字段（阿里云埋点系统）

#### 2.2.3 OAuth getUserInfo 请求

**URL**: `https://iflow.cn:443/api/oauth/getUserInfo?accessToken=aoWVSzgblwzyEQj-v76uKCEYqzQ`

**请求头**：
```http
host: iflow.cn
connection: keep-alive
accept: */*
accept-language: *
sec-fetch-mode: cors
user-agent: node
accept-encoding: br, gzip, deflate
```

**关键发现**：
1. `user-agent: node`（非 iFlow-Cli）
2. accessToken 作为 URL 查询参数传递
3. 无 Authorization 头部

---

## 3. 当前实现对比分析

### 3.1 已实现的特征对齐

| 特征类别 | 当前实现 | iflow-cli 实际 | 对齐程度 |
|----------|----------|----------------|----------|
| User-Agent (API) | `iFlow-Cli` | `iFlow-Cli` | 100% |
| User-Agent (遥测) | `node` | `node` | 100% |
| 签名算法 | HMAC-SHA256 | HMAC-SHA256 | 100% |
| session-id | `session-{uuid}` | `session-{uuid}` | 100% |
| conversation-id | `{uuid}` | `{uuid}` | 100% |
| traceparent | W3C Trace Context | W3C Trace Context | 100% |
| 协议版本 | HTTP/1.1 | HTTP/1.1 | 100% |

### 3.2 待对齐的特征差距

#### 3.2.1 请求头顺序差异

**iflow-cli 实际顺序**：
```
host -> connection -> Content-Type -> Authorization -> user-agent ->
session-id -> conversation-id -> x-iflow-signature -> x-iflow-timestamp ->
traceparent -> accept -> accept-language -> sec-fetch-mode -> accept-encoding -> content-length
```

**当前实现问题**：
- Python dict 无固定顺序（3.7+ 按插入顺序，但需要显式控制）
- 头部名称大小写不一致（`Content-Type` vs `content-type`）

#### 3.2.2 遥测事件参数差异

**run_error 缺失参数**：
- `cliVer` - CLI 版本号
- `platform` - 平台标识
- `arch` - 架构
- `nodeVersion` - Node.js 版本
- `osVersion` - 操作系统版本
- `toolName` - 工具名称
- `toolArgs` - 工具参数

**v.gif 缺失参数**：
- `scr` - 屏幕分辨率
- `cna` - 阿里云追踪标识
- `spm-cnt` - SPM 追踪
- `aplus` - 阿里云埋点标识
- `cache` - 缓存标识
- `sidx` / `ckx` - aplus 索引

#### 3.2.3 请求体格式差异

**请求体顺序**（抓包显示）：
```json
{
  "model": "glm-5",
  "messages": [...]
}
```

**当前实现**：
- 字段顺序依赖 dict 插入顺序
- 需要确保 `model` 在最前

---

## 4. 技术方案

### 4.1 Phase 1: 请求头顺序对齐（已完成抓包验证）

**目标**：实现请求头的精确顺序和大小写匹配

**实现方案**：

使用 `collections.OrderedDict` 或显式构建请求头列表：

```python
# iflow2api/cpa/headers.py

from typing import Dict, List, Tuple

# Chat API 请求头模板（按抓包顺序）
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
    构建严格顺序的请求头列表

    Returns:
        List[Tuple[str, str]]: 有序请求头列表，可直接传递给 httpx
    """
    return [
        ("host", host),
        ("connection", "keep-alive"),
        ("Content-Type", "application/json"),
        ("Authorization", f"Bearer {api_key}"),
        ("user-agent", "iFlow-Cli"),
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
```

**任务清单**：

| 任务 | 描述 | 优先级 | 状态 |
|------|------|--------|------|
| 1.1 | 创建 `cpa/headers.py` 模块 | P0 | 待开发 |
| 1.2 | 实现 Chat API 请求头模板 | P0 | 待开发 |
| 1.3 | 实现遥测请求头模板 | P0 | 待开发 |
| 1.4 | 实现 OAuth 请求头模板 | P1 | 待开发 |
| 1.5 | 添加请求头顺序验证测试 | P1 | 待开发 |

### 4.2 Phase 2: 遥测协议完善

**目标**：完整实现 iflow-cli 的遥测参数

**run_error 事件补充参数**：

```python
# iflow2api/cpa/telemetry.py

import platform
from urllib.parse import quote

IFLOW_CLI_VERSION = "0.5.13"
NODE_VERSION_EMULATED = "v22.22.0"

def build_run_error_gokey(
    trace_id: str,
    observation_id: str,
    parent_observation_id: str,
    session_id: str,
    conversation_id: str,
    user_id: str,
    error_msg: str,
    model: str,
) -> str:
    """构建 run_error 事件的 gokey 参数"""
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
        f"&tool="
        f"&toolName="
        f"&toolArgs="
        f"&cliVer={IFLOW_CLI_VERSION}"
        f"&platform={platform.system().lower()}"
        f"&arch={platform.machine().lower()}"
        f"&nodeVersion={NODE_VERSION_EMULATED}"
        f"&osVersion={platform.platform()}"
    )
```

**v.gif 埋点补充参数**：

```python
def build_vgif_payload(
    user_id: str,
    cna: str = "",  # 阿里云追踪标识（可从 cookie 获取）
    screen_resolution: str = "1920x1080",
) -> str:
    """构建 v.gif 埋点参数"""
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
        f"&device_model={platform.system()}"
        f"&os={platform.system()}"
        f"&o={'win' if platform.system().lower().startswith('win') else platform.system().lower()}"
        f"&node_version={NODE_VERSION_EMULATED}"
        f"&language=zh_CN.UTF-8"
        f"&interactive=0"
        f"&iFlowEnv="
        f"&_g_encode=utf-8"
    )
```

**任务清单**：

| 任务 | 描述 | 优先级 | 状态 |
|------|------|--------|------|
| 2.1 | 创建 `cpa/telemetry.py` 模块 | P0 | 待开发 |
| 2.2 | 补充 run_error 缺失参数 | P0 | 待开发 |
| 2.3 | 补充 v.gif 缺失参数 | P0 | 待开发 |
| 2.4 | 添加 cna cookie 追踪支持 | P1 | 待开发 |
| 2.5 | 添加遥测参数验证测试 | P1 | 待开发 |

### 4.3 Phase 3: 请求体格式对齐

**目标**：确保请求体 JSON 字段顺序正确

**实现方案**：

```python
# iflow2api/cpa/body.py

import json
from typing import Any, Dict

# Chat API 请求体字段顺序
CHAT_BODY_FIELD_ORDER = ["model", "messages", "temperature", "top_p", "max_new_tokens", "tools", "stream"]

def serialize_chat_body(body: Dict[str, Any]) -> str:
    """
    按指定顺序序列化请求体

    Args:
        body: 请求体字典

    Returns:
        JSON 字符串
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

    return json.dumps(ordered_body, ensure_ascii=False, separators=(",", ":"))
```

**任务清单**：

| 任务 | 描述 | 优先级 | 状态 |
|------|------|--------|------|
| 3.1 | 创建 `cpa/body.py` 模块 | P0 | 待开发 |
| 3.2 | 实现有序 JSON 序列化器 | P0 | 待开发 |
| 3.3 | 添加请求体格式验证测试 | P1 | 待开发 |

### 4.4 Phase 4: TLS 指纹对齐

**目标**：实现 Node.js 风格的 TLS 指纹

**方案对比**：

| 方案 | 可行性 | 复杂度 | 推荐度 |
|------|--------|--------|--------|
| A. curl_cffi 自定义 impersonate | 需要修改 curl_cffi 源码 | 高 | 中 |
| B. 使用 tls-client 库 | 支持 Node.js 模板 | 低 | 高 |
| C. 保持 curl_cffi chrome124 | 当前已可用 | 无 | 可接受 |

**重要发现**：根据抓包结果，iflow-cli 使用 HTTP/1.1 协议，当前 curl_cffi chrome124 实现可能已经足够。TLS 指纹对齐优先级可降低。

**任务清单**：

| 任务 | 描述 | 优先级 | 状态 |
|------|------|--------|------|
| 4.1 | 评估当前 TLS 指纹是否满足需求 | P1 | 待验证 |
| 4.2 | 如需要，集成 tls-client 库 | P2 | 待开发 |
| 4.3 | 添加 TLS 指纹验证测试 | P2 | 待开发 |

---

## 5. 实现计划

### 5.1 新增模块

```
iflow2api/
├── cpa/                      # CPA 特征对齐模块
│   ├── __init__.py
│   ├── headers.py            # 请求头模板（顺序控制）
│   ├── body.py               # 请求体格式化（有序序列化）
│   ├── telemetry.py          # 遥测协议（完整参数）
│   └── constants.py          # 常量定义
└── tests/
    └── cpa/
        ├── test_headers.py
        ├── test_body.py
        └── test_telemetry.py
```

### 5.2 关键常量定义

```python
# iflow2api/cpa/constants.py

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

# Chat API 请求头顺序
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
```

### 5.3 集成到现有代码

修改 `proxy.py` 中的 `_get_headers` 方法：

```python
from .cpa.headers import build_chat_headers
from .cpa.constants import IFLOW_CLI_USER_AGENT

def _get_headers(self, stream: bool = False, traceparent: Optional[str] = None) -> dict:
    """获取请求头（按 iflow-cli 0.5.13 抓包顺序）"""
    timestamp = int(time.time() * 1000)
    signature = generate_signature(IFLOW_CLI_USER_AGENT, self._session_id, timestamp, self.config.api_key)
    traceparent = traceparent or self._generate_traceparent()

    # 使用 CPA 模块构建有序请求头
    return dict(build_chat_headers(
        host="apis.iflow.cn",
        api_key=self.config.api_key,
        session_id=self._session_id,
        conversation_id=self._conversation_id,
        signature=signature,
        timestamp=str(timestamp),
        traceparent=traceparent,
        content_length=0,  # 后续计算
    ))
```

### 5.4 依赖变更

无需新增依赖，使用现有库实现。

---

## 6. 测试验证

### 6.1 单元测试

```python
# tests/cpa/test_headers.py

from iflow2api.cpa.headers import build_chat_headers
from iflow2api.cpa.constants import CHAT_API_HEADER_ORDER

def test_header_order():
    """验证请求头顺序与 iflow-cli 一致"""
    headers = build_chat_headers(
        host="apis.iflow.cn",
        api_key="test-key",
        session_id="session-test",
        conversation_id="conv-test",
        signature="abc123",
        timestamp="1234567890",
        traceparent="00-abc123-def456-01",
        content_length=100,
    )

    actual_order = [h[0] for h in headers]
    assert actual_order == CHAT_API_HEADER_ORDER, f"Header order mismatch: {actual_order}"

def test_header_case():
    """验证请求头大小写"""
    headers = dict(build_chat_headers(...))

    # 验证关键头部大小写
    assert "Content-Type" in headers  # 混合大小写
    assert "user-agent" in headers    # 小写
    assert "x-iflow-signature" in headers  # 小写
```

### 6.2 集成测试

```python
# tests/cpa/test_telemetry.py

from iflow2api.cpa.telemetry import build_run_error_gokey, build_vgif_payload

def test_run_error_params():
    """验证 run_error 事件参数完整性"""
    gokey = build_run_error_gokey(
        trace_id="test-trace",
        observation_id="obs-123",
        parent_observation_id="parent-obs",
        session_id="session-test",
        conversation_id="conv-test",
        user_id="user-123",
        error_msg="test error",
        model="glm-5",
    )

    # 验证必需参数存在
    assert "cliVer=" in gokey
    assert "platform=" in gokey
    assert "arch=" in gokey
    assert "nodeVersion=" in gokey
    assert "osVersion=" in gokey
    assert "toolName=" in gokey
    assert "toolArgs=" in gokey

def test_vgif_params():
    """验证 v.gif 埋点参数完整性"""
    payload = build_vgif_payload(user_id="user-123")

    # 验证新增参数
    assert "scr=" in payload
    assert "cna=" in payload
    assert "spm-cnt=" in payload
    assert "aplus" in payload
    assert "cache=" in payload
    assert "sidx=" in payload
    assert "ckx=" in payload
```

### 6.3 回归测试

确保 CPA 对齐不破坏现有功能：
- OpenAI API 兼容性
- Anthropic API 兼容性
- 流式响应
- 错误处理

---

## 7. 里程碑（更新）

| 阶段 | 内容 | 预计工作量 | 状态 |
|------|------|------------|------|
| M0 | 流量采集与分析 | 已完成 | 已完成 |
| M1 | 请求头顺序对齐 | 1-2 天 | 待开发 |
| M2 | 遥测协议完善 | 1-2 天 | 待开发 |
| M3 | 请求体格式对齐 | 1 天 | 待开发 |
| M4 | TLS 指纹评估 | 0.5 天 | 待验证 |
| M5 | 测试验证 + 文档 | 1-2 天 | 待开发 |

**总计**：约 4-7 天（已根据抓包结果优化）

---

## 8. 验收标准

### 8.1 功能验收

- [x] 获取 iflow-cli 0.5.13 真实请求特征
- [ ] 请求头顺序与 iflow-cli 一致
- [ ] 遥测参数与 iflow-cli 一致
- [ ] 请求体格式与 iflow-cli 一致
- [ ] 所有现有功能正常工作

### 8.2 质量验收

- [ ] 单元测试覆盖率 > 80%
- [ ] 集成测试通过
- [ ] 回归测试通过

---

## 9. 附录

### 9.1 抓包数据存档

原始抓包数据已保存至 `tmp_iflow_mitm_report.json`，关键信息摘要：

| 端点 | 方法 | User-Agent |
|------|------|------------|
| `/v1/chat/completions` | POST | iFlow-Cli |
| `//aitrack.lifecycle.run_started` | POST | node |
| `//aitrack.lifecycle.run_error` | POST | node |
| `/v.gif` | POST | node |
| `/api/oauth/getUserInfo` | GET | node |

### 9.2 关键发现总结

1. **协议版本**：HTTP/1.1（非 HTTP/2）
2. **User-Agent 差异**：
   - Chat API: `iFlow-Cli`
   - 遥测/OAuth: `node`
3. **请求头大小写**：混合模式（`Content-Type` 混合，`user-agent` 小写）
4. **遥测参数**：run_error 包含版本和环境信息
5. **v.gif 格式**：URL 编码而非 JSON

### 9.3 参考资源

- iflow-cli 版本: 0.5.13
- Node.js 版本: v22.22.0
- 抓包工具: mitmproxy
