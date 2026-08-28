"""
WebSocket 路由 - 实时遥测数据推送
"""
import json
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from services.ws_manager import ws_manager

logger = logging.getLogger("drone-swarm.ws")

router = APIRouter(tags=["websocket"])


@router.websocket("/ws/telemetry")
async def telemetry_websocket(websocket: WebSocket):
    """
    实时遥测WebSocket端点
    连接后持续接收：
    - telemetry: 无人机遥测数据
    - drone_registered / drone_removed: 无人机注册/移除
    - mission_created / mission_started / mission_cancelled: 任务事件
    - swarm_command: 编队指令
    - event: 系统事件
    """
    await ws_manager.connect(websocket)
    try:
        # 发送连接确认
        await ws_manager.send_to(websocket, {
            "type": "connected",
            "message": "Telemetry stream connected",
            "client_count": ws_manager.get_connection_count(),
        })
        while True:
            # 接收客户端消息（如订阅特定无人机）
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                logger.info("WS received: %s", msg)
                # 可以处理订阅/取消订阅等消息
                await ws_manager.send_to(websocket, {
                    "type": "ack",
                    "received": msg,
                })
            except json.JSONDecodeError:
                logger.warning("WS invalid JSON: %s", data)
    except WebSocketDisconnect:
        await ws_manager.disconnect(websocket)
    except Exception as e:
        logger.error("WS error: %s", str(e))
        await ws_manager.disconnect(websocket)
