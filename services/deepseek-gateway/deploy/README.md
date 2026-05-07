# Deploy DeepSeek TUI as a System Service

This directory contains service definitions that wrap `deepseek serve --http`
into a daemon that starts at boot and survives restarts.

## Files

| File | Platform | Purpose |
|------|----------|---------|
| `bin/` | both | 🆕 预编译二进制 (deepseek + deepseek-tui)，支持完全离线安装 |
| `install-service.sh` | macOS / Linux | One-command installer — auto-detects OS, uses bundled binaries, installs & starts |
| `com.deepseek.api.plist` | macOS | launchd service definition |
| `deepseek-api.service` | Linux | systemd unit file |
| `deepseek-api.caddy` | both | Caddy reverse proxy with auto-TLS + HTTP basic auth |

## Quick start

```bash
# 0. 离线包已内置二进制（deploy/bin/），架构匹配则无需安装
#    如果架构不匹配，先装: npm install -g deepseek-tui

# 1. Ensure API key is configured
deepseek auth set --provider deepseek

# 2. Install the API service
./deploy/install-service.sh

# 3. Install API + Exam Bridge (考试系统接入)
./deploy/install-service.sh --with-bridge

# 4. (Optional) Expose via HTTPS with Caddy
#    Edit deploy/deepseek-api.caddy — set your domain and auth hash, then:
caddy run --config deploy/deepseek-api.caddy
```

## Exam Bridge — 考试系统接入

`exam-bridge.py` 是一个零依赖的 Python HTTP 适配层，考试系统只需一个 POST 请求即可：

```bash
curl -X POST http://127.0.0.1:8888/exam/process \
  -H "Authorization: Bearer your-bridge-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "paper": "题目：请解释光合作用的过程。\\n学生答案：光合作用是植物用阳光制造食物的过程...",
    "instruction": "你是生物老师，请批改这道题。评分标准：满分10分，按要点给分。请给出评分、评分理由和改进建议。",
    "model": "deepseek-v4-pro",
    "mode": "agent"
  }'
```

返回：

```json
{
  "status": "completed",
  "result": "评分：7/10\\n评分理由：学生正确指出了光合作用的基本定义...\\n改进建议：缺少对光反应和暗反应的区分...",
  "usage": {"input_tokens": 345, "output_tokens": 200, "cost_usd": 0.0004},
  "thread_id": "thr_abc123"
}
```

考试系统只需要向 `POST /exam/process` 发试卷，阻塞等待结果即可。无需理解 SSE、Thread、Turn 等概念。

## Architecture

```
  考试系统                    Internet
     │                          │
     │ POST /exam/process       │ HTTPS (Caddy)
     ▼                          ▼
┌──────────────┐          ┌──────────┐    HTTPS / SSE     ┌────────────────────┐
│ exam-bridge  │          │  Caddy   │ ◄────────────────► │  Client (browser,  │
│ :8888        │          │  :443    │                    │  workbench, curl)   │
│ Python 适配层 │          │  TLS +   │                    └────────────────────┘
└──────┬───────┘          │  auth    │
       │                  └────┬─────┘
       │ 127.0.0.1:7878        │ 127.0.0.1:7878
       ▼                       ▼
┌──────────────────────────────────────┐
│            deepseek serve            │
│              --http                  │
│              :7878                   │
│  • REST endpoints                    │
│  • SSE streaming                     │
│  • Durable tasks                     │
└──────────────────────────────────────┘
```

## Management Commands

### macOS (launchd)
```bash
launchctl list | grep deepseek              # check status
launchctl unload ~/Library/LaunchAgents/com.deepseek.api.plist  # stop
launchctl load ~/Library/LaunchAgents/com.deepseek.api.plist    # start
tail -f /usr/local/var/log/deepseek-api.log                     # logs
```

### Linux (systemd)
```bash
sudo systemctl status deepseek-api          # check status
sudo systemctl stop deepseek-api            # stop
sudo systemctl start deepseek-api           # start
sudo journalctl -u deepseek-api -f          # tail logs
```

## API Endpoints

Once running, the full Runtime API is available at `http://127.0.0.1:7878`:

| Endpoint | Description |
|----------|-------------|
| `GET /health` | Health check |
| `POST /v1/threads` | Create a new conversation thread |
| `POST /v1/threads/{id}/turns` | Send a message and start a turn |
| `GET /v1/threads/{id}/events?since_seq=0` | SSE stream of turn events |
| `POST /v1/tasks` | Enqueue a background task |
| `GET /v1/tasks/{id}` | Check task status |
| `GET /v1/usage` | Token/cost aggregation |

Full reference: [docs/RUNTIME_API.md](../docs/RUNTIME_API.md)

## Security Notes

- The server binds to `127.0.0.1` — no external network access unless proxied.
- Caddy provides TLS (Let's Encrypt) and HTTP basic auth.
- The API key is never exposed through any endpoint.
- For production, tighten the systemd security directives (already partially hardened in the unit file).
