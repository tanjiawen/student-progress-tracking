"""WebSocket connection manager."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import WebSocket
from starlette.websockets import WebSocketState


class ConnectionManager:
    """WebSocket 连接管理器"""

    def __init__(self) -> None:
        self.active_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user_id: str) -> None:
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        self.active_connections[user_id].append(websocket)

    def disconnect(self, websocket: WebSocket, user_id: str) -> None:
        if user_id in self.active_connections:
            try:
                self.active_connections[user_id].remove(websocket)
            except ValueError:
                pass
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]

    def build_message(self, msg_type: str, data: dict) -> dict:
        return {
            "type": msg_type,
            "data": data,
            "timestamp": datetime.now(UTC).isoformat(),
        }

    async def send_to_user(self, user_id: str, message: dict) -> None:
        if user_id not in self.active_connections:
            return
        dead_sockets: list[WebSocket] = []
        for ws in self.active_connections[user_id]:
            try:
                if ws.client_state == WebSocketState.CONNECTED:
                    await ws.send_json(message)
                else:
                    dead_sockets.append(ws)
            except Exception:
                dead_sockets.append(ws)
        for ws in dead_sockets:
            self.disconnect(ws, user_id)

    async def send_to_users(self, user_ids: list[str], message: dict) -> None:
        for uid in user_ids:
            await self.send_to_user(uid, message)

    async def broadcast(self, message: dict) -> None:
        all_user_ids = list(self.active_connections.keys())
        for uid in all_user_ids:
            await self.send_to_user(uid, message)


manager = ConnectionManager()
