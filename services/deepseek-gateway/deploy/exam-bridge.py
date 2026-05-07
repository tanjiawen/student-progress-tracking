#!/usr/bin/env python3
"""
Exam Bridge — 考试系统与 DeepSeek TUI Runtime API 之间的适配层。

考试系统调用方式:

    POST /exam/process
    Content-Type: application/json

    {
        "paper": "请批改以下试卷...",
        "instruction": "你是一位语文老师，请批改这篇作文并给出评分和评语",
        "mode": "yolo",
        "model": "deepseek-v4-pro",
        "api_key": "bridge-secret-xxxx"   // 桥接层的认证 key
    }

返回:

    {
        "status": "completed",
        "result": "评语：本文结构完整...\\n评分：85/100",
        "usage": {"input_tokens": 1234, "output_tokens": 567, "cost_usd": 0.001}
    }

依赖: 仅 Python 3 标准库，无需 pip install。
"""

import json
import sys
import os
import time
import uuid
import threading
import ssl
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from urllib.parse import urljoin

# ── Configuration ──────────────────────────────────────────────────
DEEPSEEK_API_BASE = os.environ.get("DEEPSEEK_API_BASE", "http://127.0.0.1:7878")
BRIDGE_PORT = int(os.environ.get("BRIDGE_PORT", "8888"))
BRIDGE_HOST = os.environ.get("BRIDGE_HOST", "127.0.0.1")
BRIDGE_API_KEY = os.environ.get("BRIDGE_API_KEY", "bridge-secret-change-me")
REQUEST_TIMEOUT = int(os.environ.get("REQUEST_TIMEOUT", "300"))  # 5 min per request

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)]
)
log = logging.getLogger("exam-bridge")


# ── DeepSeek Runtime API Client ────────────────────────────────────

class DeepSeekClient:
    """Minimal client for the DeepSeek TUI Runtime API."""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    def _post(self, path: str, body: dict) -> dict:
        data = json.dumps(body).encode("utf-8")
        req = Request(
            self._url(path),
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except HTTPError as e:
            detail = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"API error {e.code}: {detail}") from e

    def _get(self, path: str) -> dict:
        req = Request(self._url(path), method="GET")
        try:
            with urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except HTTPError as e:
            detail = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"API error {e.code}: {detail}") from e

    def create_thread(self, model: str = "deepseek-v4-pro") -> dict:
        return self._post("/v1/threads", {"model": model})

    def send_turn(self, thread_id: str, message: str, mode: str = "yolo") -> dict:
        body = {
            "message": message,
            "mode": mode,
            "auto_approve": True,
        }
        return self._post(f"/v1/threads/{thread_id}/turns", body)

    def collect_events(self, thread_id: str, since_seq: int = 0, timeout: int = 300) -> list[dict]:
        """Read SSE stream and collect all events until turn completion."""
        events = []
        url = self._url(f"/v1/threads/{thread_id}/events?since_seq={since_seq}")
        req = Request(url, method="GET")
        req.add_header("Accept", "text/event-stream")

        try:
            with urlopen(req, timeout=timeout) as resp:
                buffer = ""
                # Stream line-by-line
                while True:
                    chunk = resp.read(4096)
                    if not chunk:
                        break
                    buffer += chunk.decode("utf-8", errors="replace")
                    while "\n\n" in buffer:
                        raw, buffer = buffer.split("\n\n", 1)
                        parsed = self._parse_sse(raw)
                        if parsed:
                            events.append(parsed)
                            if self._is_terminal(parsed):
                                return events
        except Exception as e:
            log.warning(f"SSE stream ended: {e}")
        return events

    @staticmethod
    def _parse_sse(raw: str) -> dict | None:
        data = ""
        for line in raw.split("\n"):
            if line.startswith("data: "):
                data += line[6:]
            elif line.startswith("data:"):
                data += line[5:]
        if not data.strip():
            return None
        try:
            return json.loads(data)
        except json.JSONDecodeError:
            return None

    @staticmethod
    def _is_terminal(event: dict) -> bool:
        name = event.get("event", "")
        return name in ("turn.completed", "turn.failed", "turn.interrupted")

    def health(self) -> bool:
        try:
            self._get("/health")
            return True
        except Exception:
            return False


# ── Process an exam ────────────────────────────────────────────────

def process_exam(paper: str, instruction: str = "", mode: str = "yolo",
                 model: str = "deepseek-v4-pro") -> dict:
    """Send exam to DeepSeek and wait for the complete result."""
    client = DeepSeekClient(DEEPSEEK_API_BASE)

    # 1. Create thread
    log.info("Creating thread...")
    thread = client.create_thread(model=model)
    thread_id = thread.get("id") or thread.get("thread_id")
    if not thread_id:
        raise RuntimeError(f"Failed to create thread: {thread}")

    # 2. Build prompt
    if instruction:
        full_prompt = f"{instruction}\n\n---\n\n{paper}"
    else:
        full_prompt = paper

    # 3. Send turn
    log.info(f"Sending turn on thread {thread_id}...")
    turn = client.send_turn(thread_id, full_prompt, mode=mode)
    log.info(f"Turn started: {turn}")

    # Get the starting sequence number — events start after this turn
    # The turn response may include an initial seq; start from 0 to be safe
    since_seq = 0

    # 4. Collect events
    log.info("Collecting response (SSE stream)...")
    events = client.collect_events(thread_id, since_seq=since_seq, timeout=REQUEST_TIMEOUT)

    # 5. Extract the final text output
    result_text = ""
    usage = {}
    for ev in events:
        if ev.get("event") == "item.delta":
            payload = ev.get("payload", {})
            if payload.get("kind") == "agent_message":
                result_text += payload.get("delta", "")
        # Try to capture usage from lifecycle events
        if ev.get("event") == "turn.completed":
            payload = ev.get("payload", {})
            usage = payload.get("usage", {})

    # 6. Return structured result
    status = "completed" if result_text else "no_output"
    return {
        "status": status,
        "result": result_text.strip(),
        "usage": usage,
        "thread_id": thread_id,
    }


# ── HTTP Handler ───────────────────────────────────────────────────

class ExamHandler(BaseHTTPRequestHandler):
    """HTTP server handler for exam processing requests."""

    def log_message(self, format, *args):
        log.info(f"{self.client_address[0]} - {format % args}")

    def _check_auth(self) -> bool:
        """Verify the request carries the bridge API key."""
        # Accept key via Authorization header or api_key in JSON body
        auth = self.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            return auth[7:] == BRIDGE_API_KEY
        # For POST, also check body (handled in do_POST)
        return False

    def _send_json(self, status_code: int, body: dict):
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()
        self.wfile.write(json.dumps(body, ensure_ascii=False).encode("utf-8"))

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def do_GET(self):
        if self.path == "/health":
            client = DeepSeekClient(DEEPSEEK_API_BASE)
            backend = client.health()
            self._send_json(200, {
                "status": "ok",
                "backend": "healthy" if backend else "unreachable",
                "version": "1.0.0",
            })
        else:
            self._send_json(404, {"error": "not found"})

    def do_POST(self):
        if self.path != "/exam/process":
            self._send_json(404, {"error": "not found", "usage": "POST /exam/process"})
            return

        # Read request body
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self._send_json(400, {"error": "invalid JSON"})
            return

        # Authenticate — key can come from header or body
        auth = self.headers.get("Authorization", "")
        api_key = data.get("api_key", "")
        if auth.startswith("Bearer "):
            key = auth[7:]
        elif api_key:
            key = api_key
        else:
            key = ""

        if key != BRIDGE_API_KEY:
            self._send_json(401, {"error": "unauthorized", "hint": "Use Bearer token or 'api_key' in body"})
            return

        # Extract parameters
        paper = data.get("paper", "")
        if not paper:
            self._send_json(400, {"error": "missing 'paper' field"})
            return

        instruction = data.get("instruction", "")
        mode = data.get("mode", "yolo")
        model = data.get("model", "deepseek-v4-pro")

        # Process
        log.info(f"Processing exam (model={model}, mode={mode}, paper_len={len(paper)})")
        try:
            result = process_exam(paper, instruction, mode, model)
            self._send_json(200, result)
        except Exception as e:
            log.error(f"Processing failed: {e}")
            self._send_json(500, {"error": str(e)})


# ── Main ───────────────────────────────────────────────────────────

def main():
    # Check backend health first
    client = DeepSeekClient(DEEPSEEK_API_BASE)
    if not client.health():
        log.error(f"DeepSeek API backend unreachable at {DEEPSEEK_API_BASE}")
        log.error("Start it first:  deepseek serve --http --port 7878")
        sys.exit(1)
    log.info(f"Backend healthy: {DEEPSEEK_API_BASE}")

    server = HTTPServer((BRIDGE_HOST, BRIDGE_PORT), ExamHandler)
    log.info(f"Exam Bridge listening on http://{BRIDGE_HOST}:{BRIDGE_PORT}")
    log.info(f"Bridge API key: {BRIDGE_API_KEY[:4]}...{BRIDGE_API_KEY[-4:] if len(BRIDGE_API_KEY) > 8 else ''}")
    log.info("Endpoints:")
    log.info("  GET  /health          — health check")
    log.info("  POST /exam/process    — submit exam for processing")
    log.info("")
    log.info("Example:")
    log.info(f'  curl -X POST http://{BRIDGE_HOST}:{BRIDGE_PORT}/exam/process \\')
    log.info(f'    -H "Authorization: Bearer {BRIDGE_API_KEY}" \\')
    log.info('    -H "Content-Type: application/json" \\')
    log.info('    -d \'{"paper": "请批改这篇作文...", "instruction": "你是语文老师，请评分并给出评语"}\'')

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("Shutting down...")
        server.shutdown()


if __name__ == "__main__":
    main()
