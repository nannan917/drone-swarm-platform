"""
WebSocket 连接管理器
管理所有前端WebSocket连接，负责实时遥测数据推送
"""
import asyncio
import json
import logging
from typing import Set, Dict, List
from fastapi import WebSocket

logger = logging.getLogger("drone-swarm.ws")


class ConnectionManager:
    """WebSocket连接管理器"""

    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        async with self._lock:
            self.active_connections.add(websocket)
        logger.info("WebSocket connected, total=%d", len(self.active_connections))

    async def disconnect(self, websocket: WebSocket):
        async with self._lock:
            self.active_connections.discard(websocket)
        logger.info("WebSocket disconnected, total=%d", len(self.active_connections))

    async def broadcast(self, message: dict):
        """向所有连接广播消息"""
        if not self.active_connections:
            return
        text = json.dumps(message, ensure_ascii=False, default=str)
        async with self._lock:
            connections = list(self.active_connections)
        for conn in connections:
            try:
                await conn.send_text(text)
            except Exception as e:
                logger.warning("WS send failed: %s", str(e))
                async with self._lock:
                    self.active_connections.discard(conn)

    async def send_to(self, websocket: WebSocket, message: dict):
        """向单个连接发送消息"""
        try:
            await websocket.send_text(json.dumps(message, ensure_ascii=False, default=str))
        except Exception as e:
            logger.warning("WS send failed: %s", str(e))
            async with self._lock:
                self.active_connections.discard(websocket)

    def get_connection_count(self) -> int:
        return len(self.active_connections)


# 全局单例
ws_manager = ConnectionManager()
