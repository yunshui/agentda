# Agentda — 财务数据查询 MCP 服务

基于 [Model Context Protocol (MCP)](https://modelcontextprotocol.io) 的财务数据查询系统。提供用户信息查询和财务指标数据查询能力，支持 RSA 加密 Token 认证和行级安全隔离。

## 系统架构

三个独立服务：

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  Agent Core  │     │   MCP Core   │     │   API Core   │
│  (port 8000) │     │  (port 8001) │     │  (port 8002) │
│              │     │              │     │              │
│  客户端事件    │     │  认证 + 代理  │     │  数据 + 权限   │
│  上报         │     │  RSA Token   │     │  行级安全     │
└──────────────┘     └──────────────┘     └──────────────┘
```

- **`agent-core`** (port 8000) — 客户端事件/动作上报端点，接收结构化事件数据并记录日志
- **`mcp-core`** (port 8001) — MCP 远端服务，处理认证（RSA 加密 Token）、接收 MCP 请求、调用后端
- **`api-core`** (port 8002) — 后台 REST API，提供用户查询和财务数据接口，含模拟数据

## Token 调用流程

### 1. Token 生成阶段

```
┌─────────────┐
│  运维/管理   │
└──────┬──────┘
       │
       │ python tools/generate_token_py --user-id 000000001
       ▼
┌──────────────────────┐
│  RSA 公钥加密 Token   │
│  ┌─────────────────┐ │
│  │ user_id         │ │  ← 用户身份
│  │ token_type      │ │  ← access / refresh
│  │ jti             │ │  ← 唯一标识
│  │ expires_at      │ │  ← 过期时间
│  │ issued_at       │ │  ← 签发时间
│  └─────────────────┘ │
│         RSA-OAEP      │
│         Encrypt       │
└──────────────────────┘
       │
       ├── Access Token  (15分钟) → 给客户端用于 API 调用
       └── Refresh Token (7天)    → 客户端保存，用于续期
```

### 2. API 调用流程（Access Token）

```
┌──────────┐         ┌──────────────────┐         ┌──────────────┐
│  Client  │         │    MCP Core      │         │   API Core   │
│ (MCP客户端)│        │  (port 8001)     │         │  (port 8002) │
└────┬─────┘         └────────┬─────────┘         └──────┬───────┘
     │                        │                          │
     │  POST /mcp             │                          │
     │  Authorization:        │                          │
     │  Bearer <AccessToken>  │                          │
     │─────────────────────►  │                          │
     │                        │                          │
     │                        │  1. 验证 Authorization   │
     │                        │  2. RSA 私钥解密 Token    │
     │                        │  3. 校验过期时间          │
     │                        │  4. 校验 Token 类型       │
     │                        │  5. 提取 user_id         │
     │                        │                          │
     │                        │  注入当前用户上下文        │
     │                        │  current_user_id = "xxx" │
     │                        │                          │
     │                        │  GET /api/user/{user_id} │
     │                        │  X-User-ID: 000000001    │
     │                        │─────────────────────────►│
     │                        │                          │
     │                        │       用户数据返回         │
     │                        │◄─────────────────────────│
     │                        │                          │
     │   MCP 格式化响应       │                          │
     │◄──────────────────────│                          │
```

### 3. Token 刷新流程（Refresh Token）

```
┌──────────┐         ┌──────────────────┐
│  Client  │         │    MCP Core      │
│ (MCP客户端)│        │  (port 8001)     │
└────┬─────┘         └────────┬─────────┘
     │                        │
     │  Access Token 过期      │
     │                        │
     │  POST /mcp/auth/refresh    │
     │  {"refresh_token": xxx}│
     │─────────────────────►  │
     │                        │
     │                        │  1. RSA 私钥解密 Refresh Token
     │                        │  2. 校验类型（必须是 refresh）
     │                        │  3. 检查是否在黑名单（吊销）
     │                        │  4. 校验过期时间
     │                        │  5. 生成新的 Access Token
     │                        │
     │  {"access_token": new, │
     │   "expires_in": 900}   │
     │◄──────────────────────│
     │                        │
     │  用新 Access Token     │
     │  重新调用 MCP 接口      │
```

### 4. Token 吊销流程

```
┌──────────┐         ┌──────────────────┐         ┌──────────────────┐
│  Client  │         │    MCP Core      │         │   revoked_tokens │
│ (MCP客户端)│        │  (port 8001)     │         │   .json (黑名单)  │
└────┬─────┘         └────────┬─────────┘         └────────┬─────────┘
     │                        │                           │
     │  POST /mcp/auth/revoke     │                           │
     │  {"jti": "abc123"}     │                           │
     │─────────────────────►  │                           │
     │                        │                           │
     │                        │  写入黑名单                │
     │                        │─────────────────────────►│
     │                        │                           │
     │  {"status": "revoked"} │                           │
     │◄──────────────────────│                           │
     │                        │                           │
     │  下次用此 Refresh       │                           │
     │  Token 续期时 → 拒绝    │                           │
```

### 5. 完整时序图

```mermaid
sequenceDiagram
    participant C as MCP 客户端
    participant MR as MCP Core (port 8001)
    participant BA as API Core (port 8002)
    participant FS as 文件存储

    Note over C,FS: 初始化阶段
    C->>MR: POST /mcp/auth/refresh<br/>{"refresh_token": "xxx"}
    MR->>MR: RSA 解密 Refresh Token
    MR->>MR: 校验类型、有效期、吊销状态
    MR->>MR: 生成新 Access Token (15min)
    MR-->>C: {"access_token": "new", "expires_in": 900}

    Note over C,FS: API 调用阶段
    C->>MR: POST /mcp<br/>Authorization: Bearer &lt;AccessToken&gt;
    MR->>MR: RSA 解密 → 提取 user_id
    MR->>MR: current_user_id = "000000001"
    MR->>BA: GET /api/user/000000001<br/>X-User-ID: 000000001
    BA-->>MR: {name, department, balance, role}
    MR-->>C: MCP 格式化响应

    Note over C,FS: Token 过期 → 自动刷新
    C->>MR: POST /mcp/auth/refresh<br/>{"refresh_token": "xxx"}
    MR->>MR: RSA 解密 → 检查吊销
    MR->>MR: 生成新 Access Token
    MR-->>C: {"access_token": "new", "expires_in": 900}

    Note over C,FS: 吊销 Refresh Token
    C->>MR: POST /mcp/auth/revoke<br/>{"jti": "def456"}
    MR->>FS: revoked_tokens.json<br/>添加 jti 到黑名单
    MR-->>C: {"status": "revoked"}
```

### Token 数据结构

#### 明文 Payload（加密前的 JSON）

两种 Token 使用相同的 JSON 结构，仅 `token_type` 和 `expires_at` 不同：

```json
{
  "user_id": "000000001",
  "token_type": "access",
  "jti": "a1b2c3d4e5f6g7h8",
  "expires_at": "2026-07-07T12:30:00Z",
  "issued_at": "2026-07-07T12:15:00Z"
}
```

#### 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| user_id | string | 9位数字用户编号，唯一标识用户身份 |
| token_type | string | `access`（15分钟有效期）或 `refresh`（7天有效期） |
| jti | string | Token 唯一标识（16字节随机数，secrets.token_urlsafe），用于吊销和追踪 |
| expires_at | string | ISO8601 UTC 过期时间，服务端拒绝过期 Token |
| issued_at | string | ISO8601 UTC 签发时间，用于审计追踪 |

#### 网络传输格式（加密后的密文）

Token 在网络中传输时不直接暴露上述 JSON，而是经过两层变换：

```
明文 JSON
    │
    ▼
RSA-OAEP 加密（公钥）
    │
    ▼
Base64 编码
    │
    ▼
字符串形式传输
```

最终在 HTTP Header 中的样子：

```
Authorization: Bearer ugz7SHYpfHKBCV7+l5YFnUUSawRgcRlV92/cfc6I+D2HsQlg8bJKeWAfjXKIKW4cPS14aJ5+SAa+RKEQapE3Tbm6LjvVAUZRVoBYMcOz0OLbHwG8aK0YMS0eTQy+oMuJsVOBTmw5s2P0OSEkraxZd+jaWmomuVT5zPwPLhVeohTyHiFSo9JliciOAcxbqXqT4z8F4E64Ioc3u5FkAHKCl1ykFL7IfCk4+e/oF99PuzvZ1LRL3CFBVGFTvN+2z2eRZvjwGdSsR9SFY1qkwGZ+LtOPeOPgCn7EfHFk8YJ5Vy7BrD/GS5yqrICTwfYySpeMQN6dUI0NZGsAB2t+N02SqQ==
```

Base64 编码后的密文长度约 344 字符（RSA-2048 加密输出固定 256 字节）。

#### Access Token vs Refresh Token

| 特性 | Access Token | Refresh Token |
|------|-------------|---------------|
| 有效期 | 15 分钟 | 7 天（可配置） |
| 用途 | 每次 MCP 调用时传入 | 获取新的 Access Token |
| 传输位置 | Authorization Header | POST JSON Body |
| 吊销 | 不需要（有效期极短） | 支持黑名单吊销 |
| 生成频率 | 每次刷新生成一个新 Token | 运维阶段一次性生成 |
| 存储位置 | 客户端内存 | 客户端配置文件（如 `.mcp.json`） |

#### 文件存储格式

Token 签发记录和吊销黑名单以 JSON 文件形式存储在 `tools/` 目录下：

**token_records.json** — Token 签发记录（用于审计）

```json
[
  {
    "user_id": "000000001",
    "refresh_jti": "cVxyXpm_JNtVvrXKUJQZmQ",
    "refresh_expires_at": "2026-06-01T04:49:11Z",
    "issued_at": "2026-05-25T04:49:11Z",
    "status": "active"
  }
]
```

| 字段 | 说明 |
|------|------|
| user_id | 所属用户 |
| refresh_jti | Refresh Token 的 jti，作为唯一标识 |
| refresh_expires_at | Refresh Token 过期时间 |
| issued_at | 签发时间 |
| status | `active`（有效）/ `revoked`（已吊销） |

**revoked_tokens.json** — 吊销黑名单（仅存储 jti）

```json
["abc123", "def456"]
```

RFC 标准 JWT 对比说明：本项目 Token 机制与 JWT 的核心区别在于，JWT 使用数字签名（RS256/HS256）保证完整性，任何人都可以 Base64 解码看到 payload；本项目使用 RSA-OAEP 公钥加密，整个 payload 完全不可见，只有持有私钥的服务端才能解密。这在 MCP 场景中更适合，因为 Token 在客户端仅作透传，无需客户端解析内容。

#### 代码实现对照

| 步骤 | 函数 | 位置 |
|------|------|------|
| 生成密钥对 | `generate_rsa_keypair()` | `tools/generate_token_py:61` |
| 加密 Token | `generate_token()` | `tools/generate_token_py:136` |
| 解密 Token | `decrypt_token()` | `mcp-core/main.py:209` |
| 校验请求 | `verify_request()` | `mcp-core/main.py:393` |
| 刷新 Token | `refresh_token()` | `mcp-core/main.py:311` |
| 吊销 Token | `revoke_token()` | `mcp-core/main.py:359` |

#### 安全性分析

| 攻击面 | 防护措施 |
|--------|----------|
| Token 窃听 | RSA-OAEP 加密 + HTTPS 传输 |
| Token 重放 | Access Token 15 分钟过期 + jti 唯一性 |
| Refresh Token 泄露 | 支持吊销，发现泄露可立即撤销 |
| 中间人攻击 | 服务端持有私钥，公钥加密防止篡改 |
| 用户身份伪造 | Token 内容不可见，无法伪造合法 payload |

### 安全要点

- Token 整体用 RSA-OAEP 加密传输，明文不暴露
- Access Token 有效期短（15分钟），降低泄露风险
- Refresh Token 可吊销，服务端维护黑名单（`revoked_tokens.json`）
- MCP Tools 不接受 `user_id` 参数，身份完全从 Token 解密获取

## 快速开始

### 0. 启动 Agent Core（客户端事件上报）

```bash
cd agent-core
pip install -r requirements.txt
python main.py
```

服务启动在 `http://localhost:8000`

### 1. 启动后端 API

```bash
cd api-core
pip install -r requirements.txt
python main.py
```

服务启动在 `http://localhost:8002`

### 2. 启动 MCP 远端服务

```bash
cd mcp-core
pip install -r requirements.txt
python main.py
```

服务启动在 `http://localhost:8001`

### 3. 生成 Token（可选，本地测试用）

项目中已预置 RSA 密钥对和 Refresh Token，可直接使用。如需重新生成：

```bash
# 生成新密钥对（会覆盖已有密钥）
python tools/generate_token_py --generate-key

# 为用户生成 Token 对（Access Token + Refresh Token）
python tools/generate_token_py --user-id 000000001 --refresh-expires 7
```

## MCP 工具列表

| 工具 | 说明 |
|------|------|
| `get_my_info` | 获取当前用户的完整个人信息 |
| `get_my_balance` | 获取当前用户的账户余额 |
| `get_my_department` | 获取当前用户所在部门 |
| `check_my_permission` | 检查当前用户权限角色 |
| `list_all_users` | 查询所有用户列表（仅 admin） |
| `get_finance_dictionary` | 获取财务指标元数据字典 |
| `query_financial_metrics` | 查询财务指标数据 |

所有工具自动注入当前认证用户 ID，不接受外部传入的用户标识参数。

## Agent Core 接口

客户端事件上报服务，接收客户端应用的结构化事件数据并记录日志。

### POST /agent/report

提交客户端事件/动作报告（批量模式）。

客户端上下文字段（共享）和事件列表（`events`）分开，支持一次上报多个事件。

#### 请求体

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| user_id | string | 是 | 用户标识 |
| client_ip | string | 是 | 客户端 IP 地址 |
| mac_address | string | 是 | 客户端 MAC 地址 |
| os_version | string | 是 | 操作系统版本 |
| app_name | string | 是 | 应用名称 |
| app_version | string | 是 | 应用版本 |
| screen_resolution | string | 是 | 屏幕分辨率 |
| events | array[object] | 是 | 事件列表，每项包含： |

**events[i] 字段：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| event_type | string | 是 | 事件类型：action 或 event |
| event_params | object | 否 | 事件参数（默认为空对象） |
| message_content | string | 是 | 事件消息内容 |
| event_time | string | 是 | 事件发生时间 (yyyy-MM-dd HH:mm:ss.SSS) |

#### 请求示例

```json
{
  "user_id": "000000001",
  "client_ip": "192.168.1.100",
  "mac_address": "00:1A:2B:3C:4D:5E",
  "os_version": "Windows 10",
  "app_name": "ClientApp",
  "app_version": "1.0.0",
  "screen_resolution": "1920x1080",
  "events": [
    {
      "event_type": "action",
      "event_params": {"action": "login"},
      "message_content": "User logged in",
      "event_time": "2026-07-14 10:30:00.000"
    },
    {
      "event_type": "action",
      "event_params": {"action": "query", "target": "finance"},
      "message_content": "User queried financial data",
      "event_time": "2026-07-14 10:30:05.000"
    }
  ]
}
```

#### 响应

```json
{
  "status": "success",
  "message": "2 event(s) received"
}
```

### GET /agent/health

健康检查。

```json
{
  "status": "ok"
}
```

## 测试用户

| 用户编号 | 姓名 | 角色 | 所属机构 |
|---------|------|------|---------|
| 000000001 | 张三 | admin | BR001 |
| 000000002 | 李四 | admin | BR001 |
| 000000003 | 王五 | viewer | BR002 |
| 000000004 | 赵六 | viewer | BR001 |
| 000000005 | 钱七 | admin | BR002 |

## 支持的财务指标

| 分类 | 指标名 | 中文名 |
|------|--------|--------|
| 盈利能力 | NET_PROFIT | 净利润 |
| 盈利能力 | NET_INTEREST_INCOME | 净利息收入 |
| 规模指标 | TOTAL_ASSETS | 资产总额 |
| 规模指标 | TOTAL_LIABILITIES | 负债总额 |
| 风险指标 | NPL_RATIO | 不良贷款率 |
| 风险指标 | CAR_RATIO | 资本充足率 |
| 业务指标 | LOAN_BALANCE | 贷款余额 |
| 业务指标 | DEPOSIT_BALANCE | 存款余额 |

支持按年、季度、月度粒度查询。

## 安全设计

- **白名单验证** — 只能查询字典中预定义的指标
- **行级安全 (RLS)** — 用户绑定机构，数据自动按机构过滤
- **角色访问控制** — admin 可管理，viewer 仅可查询自身数据
- **Token 加密** — RSA-OAEP 加密，Access Token 15 分钟有效，Refresh Token 7 天
- **吊销机制** — Refresh Token 支持黑名单吊销
