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

## 2. 现状分析

### 2.1 已实现的特征对齐

| 特征类别 | 当前实现 | 对齐程度 |
|----------|----------|----------|
| User-Agent | `iFlow-Cli` | 100% |
| 签名算法 | HMAC-SHA256 | 100% |
| session-id | `session-{uuid}` | 100% |
| conversation-id | `{uuid}` | 100% |
| traceparent | W3C Trace Context | 100% |
| TLS 指纹 | curl_cffi chrome124 | ~70% |
| HTTP/2 | 不支持 | 0% |
| 请求头顺序 | 无序（dict） | 0% |
| 请求体字段顺序 | 无序 | 0% |

### 2.2 待对齐的特征差距

#### 2.2.1 TLS 指纹差距

**iflow-cli (Node.js) 的 TLS 特征**：
```
TLS Version: TLS 1.3
Cipher Suites: TLS_AES_128_GCM_SHA256:TLS_AES_256_GCM_SHA384:...
Extensions: server_name, supported_versions, signature_algorithms, ...
ALPN: h2, http/1.1
```

**当前实现 (curl_cffi chrome124)**：
```
TLS Version: TLS 1.3
Cipher Suites: Chrome 风格（非 Node.js 风格）
Extensions: Chrome 风格
ALPN: h2, http/1.1
```

**问题**：curl_cffi 的 `chrome124` 模板模拟的是 Chrome 浏览器，而非 Node.js 运行时。

#### 2.2.2 HTTP 请求头差距

**iflow-cli 的请求头顺序**（推测需抓包验证）：
```
:method: POST
:path: /v1/chat/completions
:scheme: https
:authority: apis.iflow.cn
content-type: application/json
user-agent: iFlow-Cli
accept: */*
...
```

**当前实现**：
- 使用 Python dict，无固定顺序
- HTTP/1.1 协议，无 HTTP/2 伪头部

#### 2.2.3 请求体差距

**iflow-cli 的 JSON 序列化**：
- 字段顺序可能有特定要求
- 空值处理策略

**当前实现**：
- 使用 `json.dumps()` 默认行为
- 字段顺序依赖 dict 插入顺序（Python 3.7+）

#### 2.2.4 遥测协议差距

**当前已实现**：
- `run_started` 事件
- `run_error` 事件
- `v.gif` 埋点

**待验证/补充**：
- `run_completed` 事件
- 其他生命周期事件
- 事件参数完整性

---

## 3. 技术方案

### 3.1 Phase 1: 真实 iflow-cli 流量采集与分析

**目标**：建立 iflow-cli 网络行为的完整基线

**任务清单**：

| 任务 | 描述 | 优先级 |
|------|------|--------|
| 1.1 | 使用 Wireshark/tcpdump 抓取 iflow-cli 完整 TLS 握手 | P0 |
| 1.2 | 使用 mitmproxy 抓取 HTTP/2 请求头完整顺序 | P0 |
| 1.3 | 记录所有 API 端点的请求体格式 | P0 |
| 1.4 | 分析遥测事件完整列表和参数 | P1 |
| 1.5 | 分析 OAuth 流程完整请求序列 | P1 |

**输出物**：
- `docs/capture/tls_handshake.txt` - TLS 握手分析
- `docs/capture/http_headers.json` - 请求头基线
- `docs/capture/request_bodies.json` - 请求体基线
- `docs/capture/telemetry_events.json` - 遥测事件基线

### 3.2 Phase 2: TLS 指纹对齐

**目标**：实现 Node.js 风格的 TLS 指纹

**方案对比**：

| 方案 | 可行性 | 复杂度 | 推荐度 |
|------|--------|--------|--------|
| A. curl_cffi 自定义 impersonate | 需要修改 curl_cffi 源码 | 高 | 中 |
| B. 使用 tls-client 库 | 支持 Node.js 模板 | 低 | 高 |
| C. 直接使用 Node.js 作为 HTTP 客户端 | 100% 对齐 | 中 | 高 |
| D. 自定义 OpenSSL 配置 | 部分对齐 | 高 | 低 |

**推荐方案 B**：使用 `tls-client` Python 库

```python
# tls-client 支持 Node.js 模板
from tls_client import Session

client = Session(client_identifier="node_18")
```

**任务清单**：

| 任务 | 描述 | 优先级 |
|------|------|--------|
| 2.1 | 集成 tls-client 库，替换 curl_cffi | P0 |
| 2.2 | 实现 Node.js 18/20/22 多版本模板支持 | P0 |
| 2.3 | 添加 TLS 指纹验证测试 | P0 |
| 2.4 | 实现优雅降级机制（tls-client 不可用时回退） | P1 |

### 3.3 Phase 3: HTTP/2 协议对齐

**目标**：实现 HTTP/2 协议支持，对齐请求头格式

**技术方案**：

使用 `httpx` 或 `hyper` 库实现 HTTP/2 支持：

```python
# httpx HTTP/2 支持
import httpx

async with httpx.AsyncClient(http2=True) as client:
    response = await client.post(...)
```

**任务清单**：

| 任务 | 描述 | 优先级 |
|------|------|--------|
| 3.1 | 在 transport.py 中添加 HTTP/2 支持 | P0 |
| 3.2 | 实现 HTTP/2 伪头部顺序对齐 | P0 |
| 3.3 | 实现请求头大小写规范化 | P1 |
| 3.4 | 添加 HTTP/2 帧级别日志（调试用） | P2 |

### 3.4 Phase 4: 请求头严格对齐

**目标**：实现请求头的精确匹配

**对齐要点**：

1. **头部名称大小写**
   - iflow-cli 使用小写（HTTP/2 规范）
   - 当前实现混合大小写

2. **头部顺序**
   - HTTP/2 使用伪头部 `:method`, `:path`, `:scheme`, `:authority`
   - 常规头部顺序需抓包确定

3. **头部值格式**
   - `accept-encoding: br, gzip, deflate`（注意空格）
   - `accept: */*`

**任务清单**：

| 任务 | 描述 | 优先级 |
|------|------|--------|
| 4.1 | 定义请求头模板类，支持顺序控制 | P0 |
| 4.2 | 实现头部名称规范化函数 | P0 |
| 4.3 | 添加头部顺序验证测试 | P1 |
| 4.4 | 对齐不同端点的头部差异 | P1 |

### 3.5 Phase 5: 请求体格式对齐

**目标**：实现请求体的精确匹配

**对齐要点**：

1. **JSON 字段顺序**
   ```json
   // iflow-cli 可能的顺序
   {
     "model": "glm-5",
     "messages": [...],
     "temperature": 0.7,
     "top_p": 0.95,
     "max_new_tokens": 8192,
     "tools": [],
     "stream": true
   }
   ```

2. **空值处理**
   - `null` vs 字段省略

3. **数字精度**
   - `0.7` vs `0.7000000000000001`

**任务清单**：

| 任务 | 描述 | 优先级 |
|------|------|--------|
| 5.1 | 实现有序 JSON 序列化器 | P0 |
| 5.2 | 定义各端点的请求体模板 | P0 |
| 5.3 | 添加请求体格式验证测试 | P1 |
| 5.4 | 对齐模型特定参数的位置 | P1 |

### 3.6 Phase 6: 遥测协议完善

**目标**：完整实现 iflow-cli 的遥测协议

**待验证事件**：

| 事件名 | 当前状态 | 待确认 |
|--------|----------|--------|
| `run_started` | 已实现 | 参数完整性 |
| `run_completed` | 未实现 | 是否存在 |
| `run_error` | 已实现 | 参数完整性 |
| `tool_call` | 未实现 | 是否存在 |
| `v.gif` | 已实现 | 参数完整性 |

**任务清单**：

| 任务 | 描述 | 优先级 |
|------|------|--------|
| 6.1 | 抓包分析完整的遥测事件序列 | P0 |
| 6.2 | 实现 run_completed 事件（如存在） | P0 |
| 6.3 | 完善所有事件的参数 | P0 |
| 6.4 | 添加遥测事件发送顺序控制 | P1 |

### 3.7 Phase 7: OAuth 流程对齐

**目标**：对齐 OAuth 认证的完整特征

**对齐要点**：

1. **OAuth 授权请求**
   - URL 参数顺序
   - 回调地址格式

2. **Token 请求**
   - POST body 格式
   - Basic Auth 头部格式

3. **用户信息请求**
   - accessToken 参数位置

**任务清单**：

| 任务 | 描述 | 优先级 |
|------|------|--------|
| 7.1 | 对齐 OAuth 授权 URL 格式 | P1 |
| 7.2 | 对齐 Token 请求格式 | P1 |
| 7.3 | 对齐用户信息请求格式 | P1 |
| 7.4 | 添加 OAuth 流程完整性测试 | P2 |

---

## 4. 实现计划

### 4.1 新增模块

```
iflow2api/
├── cpa/                      # CPA 特征对齐模块
│   ├── __init__.py
│   ├── tls.py                # TLS 指纹配置
│   ├── headers.py            # 请求头模板
│   ├── body.py               # 请求体格式化
│   ├── telemetry.py          # 遥测协议
│   ├── validator.py          # 特征验证工具
│   └── presets/              # 预设模板
│       ├── node18.json
│       ├── node20.json
│       └── node22.json
├── transport/                # 重构传输层
│   ├── __init__.py
│   ├── base.py               # 基类
│   ├── httpx_h2.py           # httpx HTTP/2 实现
│   ├── tls_client.py         # tls-client 实现
│   └── fallback.py           # 降级实现
└── tests/
    └── cpa/
        ├── test_tls.py
        ├── test_headers.py
        └── test_body.py
```

### 4.2 配置扩展

```python
# settings.py 新增配置
class CPASettings(BaseModel):
    """CPA 特征配置"""

    # TLS 配置
    tls_backend: Literal["tls_client", "curl_cffi", "httpx"] = "tls_client"
    node_version: Literal["node18", "node20", "node22"] = "node22"

    # HTTP 配置
    http_version: Literal["h2", "http1.1"] = "h2"

    # 请求头配置
    header_case: Literal["lower", "title", "original"] = "lower"

    # 请求体配置
    json_field_order: bool = True
    json_compact: bool = True  # 无缩进

    # 遥测配置
    telemetry_enabled: bool = True
    telemetry_strict: bool = True  # 严格模式，失败时报错
```

### 4.3 依赖变更

```toml
# pyproject.toml
dependencies = [
    # 现有依赖...

    # CPA 相关新增
    "tls-client>=0.2.0",      # TLS 指纹伪装
    "hyper>=0.7.0",           # HTTP/2 底层库（可选）
]

[project.optional-dependencies]
cpa-full = [
    "tls-client>=0.2.0",
    "hyper>=0.7.0",
]
```

---

## 5. 测试验证

### 5.1 单元测试

```python
# tests/cpa/test_tls.py
def test_tls_fingerprint_node18():
    """验证 TLS 指纹与 Node.js 18 匹配"""
    client = create_transport(backend="tls_client", node_version="node18")
    fingerprint = capture_tls_fingerprint(client)
    expected = load_expected_fingerprint("node18")
    assert fingerprint == expected

# tests/cpa/test_headers.py
def test_header_order():
    """验证请求头顺序"""
    headers = build_headers(...)
    expected_order = [":method", ":path", ":scheme", ":authority", ...]
    assert list(headers.keys()) == expected_order
```

### 5.2 集成测试

```python
# tests/integration/test_cpa_alignment.py
async def test_full_request_alignment():
    """完整请求对比测试"""
    # 1. 发送相同请求到测试服务器
    # 2. 对比 iflow-cli 和 iflow2api 的请求差异
    # 3. 验证差异在允许范围内
    pass
```

### 5.3 回归测试

确保 CPA 对齐不破坏现有功能：
- OpenAI API 兼容性
- Anthropic API 兼容性
- 流式响应
- 错误处理

---

## 6. 风险与缓解

### 6.1 技术风险

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| tls-client 不稳定 | 请求失败 | 实现多后端降级机制 |
| HTTP/2 兼容性问题 | 部分端点不可用 | 自动降级到 HTTP/1.1 |
| iflow-cli 版本更新 | 特征失效 | 定期同步更新基线 |

### 6.2 维护风险

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| iflow-cli 行为变更 | 需重新对齐 | 建立自动化监控 |
| Node.js 版本更新 | TLS 指纹变化 | 支持多版本模板 |

---

## 7. 里程碑

| 阶段 | 内容 | 预计工作量 |
|------|------|------------|
| M1 | 流量采集与分析基线建立 | 2-3 天 |
| M2 | TLS 指纹对齐 | 3-5 天 |
| M3 | HTTP/2 + 请求头对齐 | 3-5 天 |
| M4 | 请求体格式对齐 | 2-3 天 |
| M5 | 遥测协议完善 | 2-3 天 |
| M6 | OAuth 流程对齐 | 1-2 天 |
| M7 | 测试验证 + 文档 | 2-3 天 |

**总计**：约 15-24 天

---

## 8. 验收标准

### 8.1 功能验收

- [ ] TLS 指纹与 Node.js 22 完全匹配
- [ ] 支持 HTTP/2 协议
- [ ] 请求头顺序与 iflow-cli 一致
- [ ] 请求体格式与 iflow-cli 一致
- [ ] 遥测事件完整发送
- [ ] OAuth 流程正常工作

### 8.2 质量验收

- [ ] 单元测试覆盖率 > 80%
- [ ] 集成测试通过
- [ ] 回归测试通过
- [ ] 性能无明显下降（< 5% 延迟增加）

### 8.3 文档验收

- [ ] 更新 README 说明 CPA 对齐
- [ ] 添加配置文档
- [ ] 添加故障排查指南

---

## 9. 后续维护

### 9.1 版本同步机制

当 iflow-cli 发布新版本时：

1. 检查 User-Agent 版本号
2. 抓包对比特征差异
3. 更新预设模板
4. 发布对应版本

### 9.2 监控告警

- 添加 API 错误率监控
- 异常响应特征告警
- 自动化特征对比测试

---

## 附录

### A. 参考资源

- iflow-cli 源码: https://github.com/iflow-ai/iflow-cli
- tls-client 文档: https://github.com/FlorianREGAZ/Python-Tls-Client
- curl-impersonate: https://github.com/lwthiker/curl-impersonate
- HTTP/2 规范: RFC 7540

### B. 抓包命令参考

```bash
# TLS 握手抓取
openssl s_client -connect apis.iflow.cn:443 -showcerts

# HTTP 流量抓取（需要 mitmproxy）
mitmproxy --mode reverse:https://apis.iflow.cn --flow-detail 3

# 完整 pcap
tcpdump -i any -s 0 -w iflow.pcap host apis.iflow.cn
```

### C. TLS 指纹对比工具

```bash
# 使用 ja3 分析
python -m tls_client.debug --url https://apis.iflow.cn
```
