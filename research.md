# iflow2api 项目深度研究报告

## 1. 项目概述

### 1.1 项目简介

**iflow2api** 是一个将 iFlow CLI 的 AI 服务暴露为 OpenAI 兼容 API 的代理服务。它允许用户通过标准的 OpenAI API 格式或 Anthropic API 格式访问 iFlow 平台提供的多种高级 AI 模型。

- **项目名称**: iflow2api
- **当前版本**: 1.6.10
- **开源协议**: MIT
- **编程语言**: Python 3.10+
- **核心框架**: FastAPI + Flet

### 1.2 核心价值

iFlow 平台通过 `User-Agent` HTTP 头来区分普通 API 调用和 CLI 调用：
- **普通 API 调用**: 只能使用基础模型
- **CLI 调用** (`User-Agent: iFlow-Cli`): 可访问 GLM-5、DeepSeek、Kimi 等高级模型

本项目的核心价值在于：通过模拟 iFlow CLI 的请求特征，让普通 API 客户端也能访问 CLI 专属的高级模型。

---

## 2. 技术架构

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                      客户端请求                              │
│  (Claude Code / OpenAI SDK / curl / ChatGPT-Next-Web)      │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    iflow2api 本地代理                        │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  /v1/chat/completions │ /v1/messages │ /v1/models │   │
│  └─────────────────────────────────────────────────────┘   │
│                              │                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  1. 读取 ~/.iflow/settings.json 获取认证信息         │   │
│  │  2. 添加 User-Agent: iFlow-Cli 解锁高级模型          │   │
│  │  3. 生成 HMAC-SHA256 签名                           │   │
│  │  4. 转发请求到 iFlow API                            │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    iFlow API 服务                            │
│                https://apis.iflow.cn/v1                      │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 模块结构

```
iflow2api/
├── __init__.py          # 包初始化
├── __main__.py          # CLI 入口 (python -m iflow2api)
├── main.py              # 主入口
├── config.py            # iFlow 配置读取器
├── proxy.py             # API 代理核心逻辑
├── app.py               # FastAPI 应用
├── oauth.py             # OAuth 认证
├── oauth_login.py       # OAuth 登录处理器
├── token_refresher.py   # Token 自动刷新
├── settings.py          # 应用配置管理
├── gui.py               # Flet GUI 界面
├── vision.py            # 视觉/图像处理
├── tray.py              # 系统托盘
├── autostart.py         # 开机自启动
├── i18n.py              # 国际化支持
├── crypto.py            # 配置加密
├── instances.py         # 多实例管理
├── server.py            # 服务器管理
├── web_server.py        # Web 服务器
├── transport.py         # 统一传输层
├── updater.py           # 自动更新
├── version.py           # 版本信息
├── logging_setup.py     # 日志配置
├── ratelimit.py         # 速率限制
└── admin/               # Web 管理界面
    ├── auth.py          # 认证
    ├── routes.py        # 路由
    ├── websocket.py     # WebSocket
    └── static/          # 静态文件
```

---

## 3. 核心技术实现

### 3.1 认证机制

#### 3.1.1 配置读取 (config.py)

项目支持两种认证方式：

1. **iFlow CLI 配置** (`~/.iflow/settings.json`)
   - 读取 `apiKey`、`baseUrl`、`oauth_access_token` 等字段
   - 支持敏感字段加密存储

2. **应用主配置** (`~/.iflow2api/config.json`)
   - 优先级高于 iFlow CLI 配置
   - 包含完整的应用设置

```python
class IFlowConfig(BaseModel):
    api_key: str
    base_url: str = "https://apis.iflow.cn/v1"
    auth_type: Optional[str] = None  # oauth-iflow, api-key, openai-compatible
    oauth_access_token: Optional[str] = None
    oauth_refresh_token: Optional[str] = None
    oauth_expires_at: Optional[datetime] = None
```

#### 3.1.2 OAuth 认证 (oauth.py)

实现了完整的 OAuth 2.0 授权码流程：

- **授权端点**: `https://iflow.cn/oauth`
- **Token 端点**: `https://iflow.cn/oauth/token`
- **用户信息端点**: `https://iflow.cn/api/oauth/getUserInfo`

关键特性：
- 支持 Token 自动刷新
- 内置 CSRF 防护 (state 参数)
- Basic Auth 认证头构建

### 3.2 API 代理核心 (proxy.py)

#### 3.2.1 请求签名算法

iFlow API 使用 HMAC-SHA256 签名验证请求合法性：

```python
def generate_signature(user_agent: str, session_id: str, timestamp: int, api_key: str) -> str:
    """
    签名算法:
    - 算法: HMAC-SHA256
    - 密钥: apiKey
    - 签名内容: `{user_agent}:{session_id}:{timestamp}`
    - 输出: 十六进制字符串
    """
    message = f"{user_agent}:{session_id}:{timestamp}"
    return hmac.new(
        api_key.encode('utf-8'),
        message.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
```

#### 3.2.2 请求头构造

模拟 iflow-cli 0.5.13 的请求特征：

```python
headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {api_key}",
    "user-agent": "iFlow-Cli",           # 解锁高级模型的关键
    "session-id": f"session-{uuid}",      # 会话标识
    "conversation-id": str(uuid),         # 对话标识
    "x-iflow-signature": signature,       # HMAC 签名
    "x-iflow-timestamp": str(timestamp),  # 毫秒时间戳
    "traceparent": traceparent,           # W3C Trace Context
}
```

#### 3.2.3 模型特定配置

针对不同模型自动添加必要的参数：

| 模型 | 配置参数 |
|------|----------|
| deepseek-* | `thinking_mode=True`, `reasoning=True` |
| glm-5 | `chat_template_kwargs={enable_thinking: True}`, `enable_thinking=True`, `thinking={type: "enabled"}` |
| glm-4.7 | `chat_template_kwargs={enable_thinking: True}` |
| kimi-k2.5 | `thinking={type: "enabled"}` |
| *thinking* | `thinking_mode=True` |

### 3.3 双 API 格式支持 (app.py)

#### 3.3.1 OpenAI 兼容 API

端点: `/v1/chat/completions`

完全兼容 OpenAI Chat Completions API 格式，支持：
- 流式/非流式响应
- 工具调用 (Tool Calls)
- 多轮对话

#### 3.3.2 Anthropic 兼容 API

端点: `/v1/messages`

实现了完整的 Anthropic Messages API 格式转换：

**请求转换 (Anthropic -> OpenAI)**:
```python
def anthropic_to_openai_request(body: dict) -> dict:
    """
    - system 字段 -> system role message
    - content blocks -> OpenAI 多模态格式
    - tools input_schema -> OpenAI parameters
    - tool_choice 格式转换
    """
```

**响应转换 (OpenAI -> Anthropic)**:
```python
def openai_to_anthropic_response(openai_response: dict, model: str) -> dict:
    """
    - choices -> content blocks
    - tool_calls -> tool_use blocks
    - finish_reason -> stop_reason
    """
```

#### 3.3.3 流式响应处理

对于支持思考链的模型（如 GLM-5），流式响应的处理逻辑：

```
上游API行为:
- 大部分 chunk 只有 reasoning_content (思考过程)
- 少部分 chunk 只有 content (最终回答)
- 两者不会同时出现

处理策略:
- preserve_reasoning=False: 合并到 content 字段
- preserve_reasoning=True: 保留独立字段
```

### 3.4 传输层抽象 (transport.py)

支持两种 HTTP 后端：

1. **httpx**: Python/OpenSSL 默认 TLS 栈
2. **curl_cffi**: curl-impersonate，可伪装为 Chrome/Node TLS 指纹

```python
TransportBackend = Literal["httpx", "curl_cffi"]

def create_upstream_transport(
    backend: TransportBackend = "curl_cffi",
    impersonate: str = "chrome124",
    ...
) -> BaseUpstreamTransport:
    """
    默认使用 curl_cffi 以规避 TLS 指纹检测
    """
```

### 3.5 视觉/多模态支持 (vision.py)

支持图像输入的格式转换：

**OpenAI 格式**:
```json
{"type": "image_url", "image_url": {"url": "data:image/png;base64,..."}}
```

**Anthropic 格式**:
```json
{"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": "..."}}
```

---

## 4. 功能特性

### 4.1 支持的模型

#### 文本模型

| 模型 ID | 名称 | 说明 |
|---------|------|------|
| glm-4.6 | GLM-4.6 | 智谱 GLM-4.6 |
| glm-4.7 | GLM-4.7 | 智谱 GLM-4.7 |
| glm-5 | GLM-5 | 智谱 GLM-5 (推荐) |
| iFlow-ROME-30BA3B | iFlow-ROME-30BA3B | iFlow ROME 30B (快速) |
| deepseek-v3.2-chat | DeepSeek-V3.2 | DeepSeek V3.2 对话模型 |
| qwen3-coder-plus | Qwen3-Coder-Plus | 通义千问 Qwen3 Coder Plus |
| kimi-k2 | Kimi-K2 | Moonshot Kimi K2 |
| kimi-k2-thinking | Kimi-K2-Thinking | Moonshot Kimi K2 思考模型 |
| kimi-k2.5 | Kimi-K2.5 | Moonshot Kimi K2.5 |
| kimi-k2-0905 | Kimi-K2-0905 | Moonshot Kimi K2 0905 |
| minimax-m2.5 | MiniMax-M2.5 | MiniMax M2.5 |

#### 视觉模型

| 模型 ID | 名称 | 说明 |
|---------|------|------|
| qwen-vl-max | Qwen-VL-Max | 通义千问 VL Max 视觉模型 |

### 4.2 客户端兼容性

| 客户端 | 协议 | 配置方式 |
|--------|------|----------|
| Claude Code | Anthropic | `ANTHROPIC_BASE_URL=http://localhost:28000` |
| OpenAI SDK | OpenAI | `base_url="http://localhost:28000/v1"` |
| ChatGPT-Next-Web | OpenAI | API 地址设为 `http://localhost:28000` |
| LobeChat | OpenAI | Base URL 设为 `http://localhost:28000/v1` |
| Open WebUI | OpenAI | 添加 OpenAI 兼容连接 |

### 4.3 高级功能

1. **Web 管理界面** (`/admin`)
   - 服务状态监控
   - 多实例管理
   - 配置管理
   - 登录认证

2. **桌面应用** (Flet GUI)
   - 系统托盘
   - 开机自启动
   - 暗色主题
   - 多语言支持

3. **Docker 部署**
   - 支持滚动发布 (latest/edge/版本号)
   - docker-compose 配置

---

## 5. 安全机制

### 5.1 认证安全

1. **API Key 验证**
   - 支持自定义 API Key 验证
   - 使用常数时间比较防止时序攻击

2. **Token 加密存储**
   - OAuth token 使用 Fernet 对称加密
   - 加密后以 `enc:` 前缀标识

3. **请求体大小限制**
   - 最大 10MB 请求体限制
   - 防止内存耗尽 DoS 攻击

### 5.2 CORS 配置

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,  # RFC 禁止 * + credentials=True
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## 6. 部署方式

### 6.1 本地运行

```bash
# 从 PyPI 安装
pip install iflow2api

# 命令行模式
iflow2api

# GUI 模式
iflow2api.gui
```

### 6.2 Docker 部署

```bash
# 使用最新稳定版
docker pull cacaview/iflow2api:latest

# 使用开发版
docker pull cacaview/iflow2api:edge

# docker-compose
docker-compose up -d
```

### 6.3 配置文件

- **iFlow CLI 配置**: `~/.iflow/settings.json`
- **应用主配置**: `~/.iflow2api/config.json`

---

## 7. 技术亮点

### 7.1 协议转换

项目实现了两种主流 AI API 格式的双向转换：
- OpenAI Chat Completions API
- Anthropic Messages API

这使得 Claude Code 等基于 Anthropic API 的工具可以直接使用 iFlow 提供的模型。

### 7.2 思考链支持

针对支持推理/思考能力的模型（GLM-5、DeepSeek、Kimi-K2-Thinking），项目实现了完整的思考链处理：
- 流式响应中的 reasoning_content 处理
- Anthropic 格式的 thinking_delta 支持
- 可配置的保留/合并策略

### 7.3 TLS 指纹伪装

通过 curl_cffi 库实现 TLS 指纹伪装，模拟 Chrome 浏览器的 TLS 握手特征，避免被上游服务识别为自动化程序。

### 7.4 遥测对齐

完整实现了 iflow-cli 的遥测协议：
- W3C Trace Context (traceparent)
- mmstat 事件上报
- run_started / run_error 生命周期事件

---

## 8. 依赖关系

### 8.1 核心依赖

| 包名 | 用途 |
|------|------|
| fastapi | Web 框架 |
| uvicorn | ASGI 服务器 |
| httpx | HTTP 客户端 |
| curl_cffi | TLS 指纹伪装 |
| pydantic | 数据验证 |
| flet | GUI 框架 |
| pystray | 系统托盘 |
| Pillow | 图像处理 |

### 8.2 可选依赖

| 包名 | 用途 |
|------|------|
| cryptography | 配置加密 |
| pyinstaller | 打包可执行文件 |

---

## 9. 项目质量评估

### 9.1 代码质量

| 维度 | 评估 | 说明 |
|------|------|------|
| 功能正确性 | 优秀 | 完整实现了 OpenAI/Anthropic API 兼容 |
| 设计架构 | 优秀 | 模块化设计，职责分离清晰 |
| 可读性 | 良好 | 代码注释充分，日志详细 |
| 健壮性 | 良好 | 完善的错误处理和回退机制 |
| 规范一致性 | 良好 | 使用 Pydantic 进行类型验证 |

### 9.2 安全性评估

| 方面 | 状态 | 说明 |
|------|------|------|
| 敏感数据加密 | 已实现 | OAuth token 加密存储 |
| 请求体验证 | 已实现 | 大小限制、类型验证 |
| 认证机制 | 已实现 | 支持自定义 API Key |
| CORS 安全 | 已实现 | 遵循 RFC 规范 |

---

## 10. 总结

iflow2api 是一个设计精良、功能完善的 AI API 代理服务。它通过模拟 iFlow CLI 的请求特征，成功解锁了高级 AI 模型的访问权限，同时提供了 OpenAI 和 Anthropic 两种主流 API 格式的兼容支持。

项目的技术亮点包括：
1. **双向协议转换**: OpenAI <-> Anthropic API 格式转换
2. **思考链支持**: 完整的 reasoning_content 处理逻辑
3. **TLS 指纹伪装**: 通过 curl_cffi 实现 Chrome 风格 TLS 握手
4. **遥测对齐**: 完整复制 iflow-cli 的遥测行为
5. **多端部署**: CLI/GUI/Docker 多种运行方式

该项目对于希望使用 iFlow 平台高级模型但受限于 API 格式兼容性的用户具有重要价值。
