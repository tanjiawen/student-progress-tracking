# DeepSeek TUI 服务化技术改造方案

> 版本: 1.0  
> 日期: 2026-05  
> 作者: 技术改造团队  
> 基于: DeepSeek TUI v0.8.12

---

## 1. 背景与目标

### 1.1 现状

DeepSeek TUI 是一个终端原生的 AI 编码助手，内建了完整的 Agent 引擎（会话管理、Turn 编排、工具调用、子 Agent、持久化任务队列），但原始形态是**交互式终端程序**，不支持外部系统以 API 方式调用。

### 1.2 目标

将 DeepSeek TUI 的 Agent 能力封装为**标准 HTTP/SSE 服务**，使其可以被任意下游系统（考试批改系统、CI/CD 流水线、代码审查平台等）通过 REST API 调用，同时保持：

- **零外部依赖**——不引入 Node.js、Python 运行时（桥接层除外）
- **本地部署**——数据不离开自有机房
- **持久化**——会话、任务、用量可追溯
- **安全边界清晰**——仅绑定 localhost + 反向代理鉴权

### 1.3 范围

| 组件 | 说明 | 运行时依赖 |
|------|------|-----------|
| `deepseek serve --http` | Agent 运行时 API 服务 | Rust 二进制 |
| Caddy 反向代理 | TLS 终止 + HTTP Basic Auth | Caddy |
| `exam-bridge.py` | 考试系统适配层（可选） | Python 3 标准库 |
| systemd / launchd | 系统服务管理 | 操作系统原生 |

---

## 2. 总体架构

```
                     ┌─────────────────────────┐
                     │     下游业务系统          │
                     │  (考试系统 / CI / 平台)    │
                     └──────┬────────┬─────────┘
                            │        │
              POST /exam/process   POST /v1/threads/{id}/turns
              (简化协议)            (完整 Runtime API)
                            │        │
                            ▼        ▼
              ┌─────────────────────────────┐
              │  Caddy / Nginx (可选)        │
              │  · TLS 终止 (Let's Encrypt)  │
              │  · HTTP Basic Auth           │
              │  · SSE 长连接超时保护         │
              └─────────────┬───────────────┘
                            │ 127.0.0.1:7878
                            ▼
              ┌─────────────────────────────┐
              │      exam-bridge.py          │
              │  (可选适配层，:8888)           │
              │  试卷 → Thread → Turn → 返回  │
              └─────────────┬───────────────┘
                            │ 127.0.0.1:7878
                            ▼
              ┌─────────────────────────────┐
              │    deepseek serve --http     │
              │         :7878                │
              │  ┌───────────────────────┐   │
              │  │  Agent Engine         │   │
              │  │  · Session / Turn     │   │
              │  │  · Tool Orchestration │   │
              │  │  · Sub-Agent Spawner  │   │
              │  │  · RLM                │   │
              │  │  · Durable Task Queue │   │
              │  └───────────────────────┘   │
              └─────────────┬───────────────┘
                            │ HTTPS
                            ▼
              ┌─────────────────────────────┐
              │     DeepSeek API            │
              │  (api.deepseek.com)         │
              │  · deepseek-v4-pro          │
              │  · deepseek-v4-flash        │
              └─────────────────────────────┘
```

### 分层设计原则

1. **引擎层** (`deepseek serve --http`)：核心 Agent 能力，只暴露 REST + SSE，绑定 127.0.0.1
2. **代理层** (Caddy/Nginx)：TLS + 认证，唯一对外暴露的端口
3. **适配层** (`exam-bridge.py`)：业务语义转换，把业务请求（试卷批改、代码审查等）翻译为 Thread/Turn 调用
4. **调用层**：下游系统只需 HTTP POST，不感知 SSE/Thread/Turn

---

## 3. 核心组件详细设计

### 3.1 deepseek serve --http（引擎层）

#### 3.1.1 能力矩阵

| 端点 | 方法 | 用途 |
|------|------|------|
| `/health` | GET | 健康检查 |
| `/v1/threads` | POST | 创建会话线程 |
| `/v1/threads` | GET | 列出线程（支持分页、搜索、归档过滤） |
| `/v1/threads/{id}` | GET | 获取线程详情 |
| `/v1/threads/{id}` | PATCH | 更新线程属性（标题、模型、模式、系统提示词） |
| `/v1/threads/{id}/turns` | POST | 发送消息，启动 Agent Turn |
| `/v1/threads/{id}/events` | GET | SSE 事件流（实时增量 + 历史回放） |
| `/v1/threads/{id}/resume` | POST | 恢复已中断的线程 |
| `/v1/threads/{id}/fork` | POST | 从指定 Turn 分叉 |
| `/v1/threads/{id}/compact` | POST | 手动触发上下文压缩 |
| `/v1/tasks` | POST/GET | 后台任务增删查 |
| `/v1/automations` | POST/GET/PATCH/DELETE | 定时任务调度 |
| `/v1/usage` | GET | 按天/模型/线程聚合 token 和费用 |
| `/v1/sessions` | GET/DELETE | 兼容旧版会话管理 |

#### 3.1.2 SSE 事件流协议

```
event: item.delta
data: {"seq":42,"thread_id":"thr_1","turn_id":"turn_1","event":"item.delta","payload":{"delta":"评语：","kind":"agent_message"}}

event: item.delta
data: {"seq":43,"thread_id":"thr_1","turn_id":"turn_1","event":"item.delta","payload":{"delta":"本文结构完整...","kind":"agent_message"}}

event: turn.completed
data: {"seq":44,"thread_id":"thr_1","turn_id":"turn_1","event":"turn.completed","payload":{"usage":{"input_tokens":1234,"output_tokens":567,"cost_usd":0.001}}}
```

事件类型：`thread.started`、`turn.started`、`item.delta`、`item.completed`、`turn.completed`、`turn.failed`、`turn.interrupted`、`approval.required`。

#### 3.1.3 启动参数

```
Usage: deepseek serve --http [OPTIONS]

Options:
  --host <HOST>        Bind host (default: 127.0.0.1)
  --port <PORT>        Bind port (default: 7878)
  --workers <N>        Background task workers 1-8 (default: 2)
  --cors-origin <URL>  Additional CORS origin (repeatable)
```

#### 3.1.4 关键启动命令

```bash
deepseek serve --http --host 127.0.0.1 --port 7878 --workers 4
```

### 3.2 代理层（nginx / Caddy）

#### 3.2.1 核心功能

- TLS 终止：Let's Encrypt 自动证书
- HTTP Basic Auth：单用户 bcrypt 认证
- SSE 长连接保护：禁用缓冲 (`flush_interval -1`)，超时 10 分钟
- 安全头注入：`X-Content-Type-Options: nosniff`

#### 3.2.2 Caddy 配置要点

```caddyfile
{$DOMAIN} {
    basicauth {
        admin {$AUTH_HASH}
    }
    reverse_proxy 127.0.0.1:7878 {
        flush_interval -1              # SSE 实时推送
        transport http {
            read_timeout  10m          # Agent Turn 可能持续数分钟
            write_timeout 10m
        }
    }
}
```

### 3.3 适配层（exam-bridge.py）

#### 3.3.1 设计动机

`deepseek serve --http` 暴露的是通用 Agent 协议（Thread/Turn/SSE），对下游系统来说概念负担较重。适配层的职责是：

> **把业务语义映射为 Agent 协议调用。下游系统只需 `POST /exam/process {"paper": "..."}`，不需要理解 Thread、Turn、SSE。**

#### 3.3.2 请求协议

**端点**: `POST /exam/process`

**请求体**:
```json
{
  "paper":       "试卷内容（必填）",
  "instruction": "批改指令（可选）。如：你是语文老师，请按高考评分标准批改这篇作文。",
  "model":       "deepseek-v4-pro | deepseek-v4-flash（可选，默认 pro）",
  "mode":        "yolo | agent（可选，默认 yolo = 自动批准所有工具）",
  "api_key":     "桥接层认证密钥（必填，或通过 Authorization: Bearer <key> 传递）"
}
```

**响应体**:
```json
{
  "status":    "completed | failed | no_output",
  "result":    "AI 处理结果文本",
  "usage":     {"input_tokens": 1234, "output_tokens": 567, "cost_usd": 0.001},
  "thread_id": "thr_abc123"
}
```

#### 3.3.3 内部处理流程

```
POST /exam/process
  │
  ├─ 1. 认证检查（BRIDGE_API_KEY）
  ├─ 2. POST /v1/threads                    ← 创建线程
  ├─ 3. POST /v1/threads/{id}/turns         ← 发送 Turn (含试卷内容 + 批改指令)
  ├─ 4. GET /v1/threads/{id}/events         ← 收集 SSE 流直到 turn.completed
  ├─ 5. 解析所有 item.delta → 拼接 result_text
  └─ 6. 返回 200 JSON
```

#### 3.3.4 零依赖设计

仅使用 Python 3 标准库：`http.server`、`urllib.request`、`json`、`logging`。不依赖 Flask、FastAPI、requests。

#### 3.3.5 配置环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `DEEPSEEK_API_BASE` | `http://127.0.0.1:7878` | 后端 API 地址 |
| `BRIDGE_HOST` | `127.0.0.1` | 桥接服务监听地址 |
| `BRIDGE_PORT` | `8888` | 桥接服务监听端口 |
| `BRIDGE_API_KEY` | `bridge-secret-change-me` | 桥接层认证密钥（生产环境必须修改） |
| `REQUEST_TIMEOUT` | `300` | 单次处理超时（秒） |

---

## 4. 部署方案

### 4.1 部署前提

| 条件 | 要求 |
|------|------|
| 操作系统 | Linux (glibc) / macOS (x64/ARM64) |
| DeepSeek API Key | `deepseek auth set --provider deepseek` |
| 二进制 | `deepseek` + `deepseek-tui` 均已安装 |
| Python 3 | 仅安装桥接层时需要 |

### 4.2 一键部署

```bash
# 仅部署 API 服务
./deploy/install-service.sh

# 部署 API + 考试桥接
./deploy/install-service.sh --with-bridge
```

安装脚本自动完成：
1. 检测操作系统（macOS / Linux）
2. 自动定位 `deepseek` 二进制路径（cargo / brew / 系统路径）
3. 验证 API key 配置
4. 创建日志目录 `/usr/local/var/log`
5. 安装并启动对应平台的服务（launchd / systemd）
6. 健康检查

### 4.3 手动部署步骤

#### macOS (launchd)

```bash
# 1. 安装 plist
cp deploy/com.deepseek.api.plist ~/Library/LaunchAgents/

# 2. 编辑 plist，确认二进制路径和 API key

# 3. 加载服务
launchctl load ~/Library/LaunchAgents/com.deepseek.api.plist

# 4. 验证
curl http://127.0.0.1:7878/health

# 5. (可选) 安装考试桥接
cp deploy/com.deepseek.exam-bridge.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.deepseek.exam-bridge.plist
curl http://127.0.0.1:8888/health
```

#### Linux (systemd)

```bash
# 1. 安装 unit 文件
sudo cp deploy/deepseek-api.service /etc/systemd/system/

# 2. 编辑 unit 文件，修改 User、Group、ExecStart 路径

# 3. 启用并启动
sudo systemctl daemon-reload
sudo systemctl enable --now deepseek-api

# 4. 验证
curl http://127.0.0.1:7878/health

# 5. (可选) 安装考试桥接
sudo cp deploy/exam-bridge.service /etc/systemd/system/
sudo systemctl enable --now exam-bridge
```

### 4.4 管理命令

| 操作 | macOS | Linux |
|------|-------|-------|
| 查看状态 | `launchctl list \| grep deepseek` | `systemctl status deepseek-api` |
| 停止服务 | `launchctl unload ~/Library/LaunchAgents/com.deepseek.api.plist` | `systemctl stop deepseek-api` |
| 启动服务 | `launchctl load ~/Library/LaunchAgents/com.deepseek.api.plist` | `systemctl start deepseek-api` |
| 查看日志 | `tail -f /usr/local/var/log/deepseek-api.log` | `journalctl -u deepseek-api -f` |
| 重启 | stop + start | `systemctl restart deepseek-api` |

---

## 5. 安全设计

### 5.1 网络边界

```
Internet ──▶ [Caddy :443] ──▶ [127.0.0.1:7878]   ← 仅本地回环
                ↑ TLS + Auth        ↑ 拒绝外部连接
```

- `deepseek serve --http` 默认绑定 `127.0.0.1`，不监听外部网卡
- Caddy 是唯一对外暴露的端口，承担 TLS + 认证
- API key 从不通过任何端点暴露

### 5.2 认证链路

```
下游系统 → Caddy Basic Auth (bcrypt)
         → exam-bridge API Key (Bearer token)
         → deepseek Runtime API (localhost, 无额外认证)
```

### 5.3 systemd 安全加固

已应用的 systemd 安全指令：

```ini
NoNewPrivileges=yes          # 禁止进程获取新权限
PrivateTmp=yes               # 隔离 /tmp
ProtectSystem=strict         # /usr、/etc 只读
ProtectHome=read-only        # $HOME 只读
ReadWritePaths=/home/xxx/.deepseek   # 仅 .deepseek 可写（会话持久化所需）
```

### 5.4 CORS 白名单

内置默认白名单：`localhost:3000`、`localhost:1420`、`tauri://localhost`。可通过 `--cors-origin` 追加，不支持通配符。

---

## 6. 容量与性能

### 6.1 资源估算

| 指标 | 空载 | 单 Turn 处理中 |
|------|------|---------------|
| 内存 | ~50 MB | ~200 MB（含上下文） |
| CPU | <1% | 5-15%（流解析 + 序列化） |
| 磁盘 | SQLite 持久化，每线程约 10-100 KB | |

### 6.2 并发模型

- API 层：actix-web 异步 I/O，单进程多 worker（1-8）
- 后台任务：独立 worker 池，任务重启后自动恢复
- SSE 流：每连接独立持有，Turn 完成即释放

### 6.3 超时策略

| 层级 | 超时 | 说明 |
|------|------|------|
| 单次 HTTP | 30s | Thread 创建、Task 查询等短请求 |
| SSE 流 | 300s（默认，可配） | Agent Turn 最长处理时间 |
| Caddy 代理 | 600s | 略大于 SSE 超时，避免代理提前断开 |

---

## 7. 考试系统接入指南

### 7.1 最小可行接入

考试系统只需实现一个 HTTP 调用函数：

```python
import requests

def grade_exam(paper: str, instruction: str, bridge_url: str, api_key: str) -> dict:
    """调用 DeepSeek 批改试卷，同步等待结果返回。"""
    resp = requests.post(
        f"{bridge_url}/exam/process",
        json={
            "paper": paper,
            "instruction": instruction,
            "model": "deepseek-v4-pro",
            "mode": "agent",
        },
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=300,  # 5 分钟
    )
    resp.raise_for_status()
    return resp.json()

# 使用
result = grade_exam(
    paper="作文：我的理想。学生的答案是...",
    instruction="你是语文老师，请按高考评分标准批改。要求：给出总分、分项得分、总评、改进建议。",
    bridge_url="http://127.0.0.1:8888",
    api_key="bridge-secret-change-me",
)
print(result["result"])
```

### 7.2 调用时序

```
考试系统                        exam-bridge                  deepseek serve
   │                                │                              │
   │── POST /exam/process ────────▶│                              │
   │                                │── POST /v1/threads ────────▶│
   │                                │◀─────── thread_id ──────────│
   │                                │── POST /v1/threads/{id}/turns ─▶│
   │                                │◀── SSE stream (item.delta × N) ─│
   │                                │        ...                   │
   │                                │◀── turn.completed ───────────│
   │◀──── 200 {result, usage} ─────│                              │
   │                                │                              │
```

### 7.3 错误处理

| HTTP 状态码 | 含义 | 处理建议 |
|-------------|------|---------|
| 200 | 成功 | 读取 `result` 字段 |
| 400 | 缺少 `paper` 字段 | 检查请求体 |
| 401 | 认证失败 | 检查 `BRIDGE_API_KEY` 或 `Authorization` 头 |
| 500 | 处理异常 | `error` 字段含具体错误信息，建议重试 |
| 超时 | 网络或模型耗时过长 | 增加 `timeout`，或换用 `deepseek-v4-flash` |

---

## 8. 运维手册

### 8.1 日志位置

| 组件 | 日志路径 |
|------|---------|
| deepseek API (macOS) | `/usr/local/var/log/deepseek-api.log` / `.err` |
| deepseek API (Linux) | `journalctl -u deepseek-api` |
| exam-bridge (macOS) | `/usr/local/var/log/exam-bridge.log` / `.err` |
| exam-bridge (Linux) | `journalctl -u exam-bridge` |
| Caddy | `/var/log/caddy/deepseek-api.log` |

### 8.2 健康检查

```bash
# 引擎层
curl http://127.0.0.1:7878/health

# 桥接层
curl http://127.0.0.1:8888/health
# → {"status":"ok","backend":"healthy","version":"1.0.0"}

# 机器可读诊断
deepseek doctor --json
```

### 8.3 升级流程

```bash
# 1. 停止服务
launchctl unload ~/Library/LaunchAgents/com.deepseek.api.plist  # macOS
# 或
sudo systemctl stop deepseek-api                                 # Linux

# 2. 升级二进制
cargo install deepseek-tui-cli --locked --force
cargo install deepseek-tui --locked --force

# 3. 启动服务
launchctl load ~/Library/LaunchAgents/com.deepseek.api.plist

# 4. 验证
deepseek --version
curl http://127.0.0.1:7878/health
```

### 8.4 用量监控

```bash
# 本月用量统计
curl "http://127.0.0.1:7878/v1/usage?group_by=day" | python3 -m json.tool

# 按模型统计
curl "http://127.0.0.1:7878/v1/usage?group_by=model"
```

---

## 9. 文件清单

| 文件 | 路径 | 用途 |
|------|------|------|
| 引擎服务 (macOS) | `deploy/com.deepseek.api.plist` | launchd 定义 |
| 引擎服务 (Linux) | `deploy/deepseek-api.service` | systemd unit |
| 代理配置 | `deploy/deepseek-api.caddy` | Caddy 反向代理 |
| 桥接脚本 | `deploy/exam-bridge.py` | 考试系统适配层 |
| 桥接服务 (macOS) | `deploy/com.deepseek.exam-bridge.plist` | launchd 定义 |
| 桥接服务 (Linux) | `deploy/exam-bridge.service` | systemd unit |
| 安装脚本 | `deploy/install-service.sh` | 一键部署 |
| 说明文档 | `deploy/README.md` | 快速上手指南 |
| 本技术方案 | `deploy/TECHNICAL_DESIGN.md` | 本文档 |

---

## 10. 附录

### 10.1 术语表

| 术语 | 含义 |
|------|------|
| Thread | 一个完整的对话会话 |
| Turn | 一次“用户提问 → Agent 处理 → 返回结果”的完整交互 |
| Item | Turn 内部的一个生命周期事件（消息、工具调用、文件修改等） |
| SSE | Server-Sent Events，服务端向客户端推送实时事件的 HTTP 协议 |
| Agent Mode | 需要人工批准的工具调用模式 |
| YOLO Mode | 自动批准所有工具调用，适合自动化流水线 |
| Compaction | 上下文窗口接近上限时的自动压缩机制 |

### 10.2 参考文档

- [DeepSeek TUI Architecture](https://github.com/Hmbown/DeepSeek-TUI/blob/main/docs/ARCHITECTURE.md)
- [Runtime API Reference](https://github.com/Hmbown/DeepSeek-TUI/blob/main/docs/RUNTIME_API.md)
- [Configuration Guide](https://github.com/Hmbown/DeepSeek-TUI/blob/main/docs/CONFIGURATION.md)
