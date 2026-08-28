"""
MAVLink 通信服务
负责与无人机建立MAVLink连接、接收遥测、发送指令

支持两种模式（自动选择）：
1. 真实连接：通过 UDP/TCP/串口 连接真实飞控（PX4/ArduPilot）
   - UDP:    connection_address = "192.168.1.10:14550"
   - TCP:    connection_address = "192.168.1.10:5760"
   - 串口:   connection_address = "COM3" 或 "/dev/ttyUSB0"
2. 模拟模式：生成模拟遥测数据，用于开发演示
   - connection_type = "simulation" 时强制使用模拟
   - 真实连接失败时自动 fallback 到模拟模式
"""
import asyncio
import math
import random
import time
import threading
import queue
import logging
from datetime import datetime
from typing import Dict, Optional

from config import settings
from services.ws_manager import ws_manager

logger = logging.getLogger("drone-swarm.mavlink")

# 尝试导入 pymavlink，不可用时标记
try:
    from pymavlink import mavutil
    PYMAVLINK_AVAILABLE = True
except ImportError:
    PYMAVLINK_AVAILABLE = False
    logger.warning("pymavlink 未安装，将使用模拟模式。安装: pip install pymavlink")


class MAVLinkConnection:
    """单架无人机的 MAVLink 连接（支持真实连接 + 模拟 fallback）"""

    def __init__(self, drone_id: str, sys_id: int, connection_type: str, connection_address: str):
        self.drone_id = drone_id
        self.sys_id = sys_id
        self.connection_type = connection_type.lower()
        self.connection_address = connection_address
        self.connected = False
        self.mode = "simulation"  # real / simulation
        self._task: Optional[asyncio.Task] = None
        self._master = None  # pymavlink 连接对象
        self._recv_thread: Optional[threading.Thread] = None
        self._msg_queue: queue.Queue = queue.Queue()
        self._stop_event = threading.Event()

        # 遥测状态（真实/模拟共用）
        self._lat = 22.5431 + random.uniform(-0.01, 0.01)
        self._lon = 113.9440 + random.uniform(-0.01, 0.01)
        self._alt = 0.0
        self._relative_alt = 0.0
        self._heading = random.uniform(0, 360)
        self._ground_speed = 0.0
        self._vertical_speed = 0.0
        self._battery_voltage = 12.6
        self._battery_current = 0.0
        self._battery_percent = 100.0
        self._gps_sats = random.randint(8, 14)
        self._gps_fix_type = 0
        self._roll = 0.0
        self._pitch = 0.0
        self._yaw = self._heading
        self._status = "standby"
        self._armed = False
        self._flight_mode = "STABILIZE"

        # 模拟模式目标点
        self._target_lat = None
        self._target_lon = None
        self._target_alt = None

    # ============ 连接管理 ============

    async def connect(self):
        """建立连接：优先真实连接，失败则 fallback 模拟"""
        # 如果明确指定 simulation 模式，直接用模拟
        if self.connection_type == "simulation":
            await self._connect_simulation()
            return

        # 尝试真实连接
        if PYMAVLINK_AVAILABLE:
            try:
                await self._connect_real()
                return
            except Exception as e:
                logger.warning("[MAVLink] %s 真实连接失败(%s)，切换到模拟模式: %s",
                               self.drone_id, self.connection_address, str(e))

        # fallback 到模拟模式
        await self._connect_simulation()

    async def _connect_real(self):
        """建立真实 MAVLink 连接"""
        conn_str = self._build_connection_string()
        logger.info("[MAVLink] %s 尝试真实连接: %s (sys_id=%d)",
                    self.drone_id, conn_str, self.sys_id)

        # 在线程中建立连接（避免阻塞事件循环）
        self._master = await asyncio.to_thread(
            mavutil.mavlink_connection, conn_str, source_system=self.sys_id
        )

        # 等待心跳（超时 10 秒）
        try:
            heartbeat = await asyncio.wait_for(
                asyncio.to_thread(self._master.wait_heartbeat, timeout=10),
                timeout=12,
            )
            # 从心跳中获取真实的 sys_id
            if hasattr(heartbeat, 'get_srcSystem'):
                real_sys_id = heartbeat.get_srcSystem()
                if real_sys_id != self.sys_id:
                    logger.info("[MAVLink] %s 飞控实际 sys_id=%d (分配=%d)",
                                self.drone_id, real_sys_id, self.sys_id)
        except asyncio.TimeoutError:
            raise ConnectionError(f"等待飞控心跳超时（10秒），地址: {conn_str}")

        self.connected = True
        self.mode = "real"
        self._status = "standby"

        # 启动后台接收线程
        self._stop_event.clear()
        self._recv_thread = threading.Thread(
            target=self._real_recv_loop, daemon=True, name=f"mavlink-recv-{self.drone_id}"
        )
        self._recv_thread.start()

        # 启动异步遥测推送循环
        self._task = asyncio.create_task(self._real_telemetry_loop())

        logger.info("[MAVLink] %s 真实连接成功 (mode=real)", self.drone_id)

    def _build_connection_string(self) -> str:
        """根据连接类型构建 pymavlink 连接字符串"""
        addr = self.connection_address.strip()
        ctype = self.connection_type

        if ctype == "udp":
            # 支持 "host:port" 格式，默认用 udpin（监听入站）
            if ":" in addr:
                return f"udpin:{addr}"
            return f"udp:{addr}:14550"

        elif ctype == "tcp":
            if ":" in addr:
                return f"tcp:{addr}"
            return f"tcp:{addr}:5760"

        elif ctype == "serial":
            # 串口：地址可能是 "COM3" 或 "COM3:57600"
            if ":" in addr:
                port, baud = addr.rsplit(":", 1)
                return f"{port}:{baud}"
            return f"{addr}:{settings.MAVLINK_BAUDRATE}"

        # 默认尝试 UDP
        if ":" in addr:
            return f"udpin:{addr}"
        return addr

    async def _connect_simulation(self):
        """模拟模式连接"""
        await asyncio.sleep(0.2)
        self.connected = True
        self.mode = "simulation"
        self._status = "standby"
        self._task = asyncio.create_task(self._simulation_loop())
        logger.info("[MAVLink] %s 模拟模式已启动 (mode=simulation)", self.drone_id)

    async def disconnect(self):
        """断开连接"""
        self.connected = False
        self._stop_event.set()

        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        if self._master:
            try:
                self._master.close()
            except Exception:
                pass
            self._master = None

        if self._recv_thread and self._recv_thread.is_alive():
            self._recv_thread.join(timeout=2)

        logger.info("[MAVLink] %s 已断开 (mode=%s)", self.drone_id, self.mode)

    # ============ 真实连接：接收线程 ============

    def _real_recv_loop(self):
        """后台线程：持续接收 MAVLink 消息并解析"""
        logger.info("[MAVLink] %s 接收线程启动", self.drone_id)
        while not self._stop_event.is_set() and self._master:
            try:
                msg = self._master.recv_match(blocking=True, timeout=1.0)
                if msg is None:
                    continue
                msg_type = msg.get_type()
                self._parse_mavlink_message(msg_type, msg)
            except Exception as e:
                if not self._stop_event.is_set():
                    logger.debug("[MAVLink] %s 接收错误: %s", self.drone_id, str(e))
                time.sleep(0.1)
        logger.info("[MAVLink] %s 接收线程退出", self.drone_id)

    def _parse_mavlink_message(self, msg_type: str, msg):
        """解析 MAVLink 消息，更新遥测状态"""
        try:
            if msg_type == "HEARTBEAT":
                self._armed = (msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED) != 0
                # 解析飞行模式
                if msg.autopilot == mavutil.mavlink.MAV_AUTOPILOT_PX4:
                    self._flight_mode = mavutil.mode_string_v10(msg)
                else:
                    self._flight_mode = mavutil.mode_string_v10(msg)
                # 更新状态
                if self._armed:
                    if self._relative_alt > 1.0:
                        self._status = "flying"
                    else:
                        self._status = "armed"
                else:
                    self._status = "standby"

            elif msg_type == "GLOBAL_POSITION_INT":
                self._lat = msg.lat / 1e7
                self._lon = msg.lon / 1e7
                self._alt = msg.alt / 1000.0  # 绝对高度（mm -> m）
                self._relative_alt = msg.relative_alt / 1000.0
                self._ground_speed = math.sqrt(msg.vx**2 + msg.vy**2) / 100.0
                self._vertical_speed = -msg.vz / 100.0  # 注意符号
                self._heading = msg.hdg / 100.0 if msg.hdg != 65535 else self._heading
                self._yaw = self._heading

            elif msg_type == "ATTITUDE":
                self._roll = math.degrees(msg.roll)
                self._pitch = math.degrees(msg.pitch)
                self._yaw = math.degrees(msg.yaw)

            elif msg_type == "SYS_STATUS":
                # 电池电压（mV -> V）
                if msg.voltage_battery != 65535:
                    self._battery_voltage = msg.voltage_battery / 1000.0
                if msg.current_battery != -1:
                    self._battery_current = msg.current_battery / 100.0
                # 电池剩余容量（-1 表示未知）
                if msg.battery_remaining != -1:
                    self._battery_percent = msg.battery_remaining

            elif msg_type == "GPS_RAW_INT":
                self._gps_sats = msg.satellites_visible
                self._gps_fix_type = msg.fix_type

            elif msg_type == "BATTERY_STATUS":
                if msg.voltages and msg.voltages[0] != 65535:
                    total_mv = sum(v for v in msg.voltages if v != 65535)
                    self._battery_voltage = total_mv / 1000.0
                if msg.current_battery != -1:
                    self._battery_current = msg.current_battery / 100.0
                if msg.battery_remaining != -1:
                    self._battery_percent = msg.battery_remaining

            elif msg_type == "STATUSTEXT":
                severity = msg.severity
                text = msg.text.decode() if isinstance(msg.text, bytes) else str(msg.text)
                if severity <= 4:  # WARNING 及以下
                    logger.info("[MAVLink-FC] %s: %s", self.drone_id, text)

        except Exception as e:
            logger.debug("[MAVLink] %s 解析 %s 消息错误: %s", self.drone_id, msg_type, str(e))

    async def _real_telemetry_loop(self):
        """真实模式：定期推送遥测数据（数据由接收线程更新）"""
        try:
            while self.connected and self.mode == "real":
                telemetry = self._get_telemetry_dict()
                await ws_manager.broadcast({"type": "telemetry", "data": telemetry})
                await asyncio.sleep(settings.TELEMETRY_INTERVAL)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error("[MAVLink] %s 遥测推送错误: %s", self.drone_id, str(e))

    # ============ 模拟模式 ============

    async def _simulation_loop(self):
        """模拟模式遥测循环"""
        try:
            while self.connected and self.mode == "simulation":
                self._update_simulation()
                telemetry = self._get_telemetry_dict()
                await ws_manager.broadcast({"type": "telemetry", "data": telemetry})
                await asyncio.sleep(settings.TELEMETRY_INTERVAL)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error("[MAVLink] %s 模拟循环错误: %s", self.drone_id, str(e))

    def _update_simulation(self):
        """更新模拟状态"""
        if self._status in ("flying", "takeoff"):
            if self._target_lat is not None:
                dlat = self._target_lat - self._lat
                dlon = self._target_lon - self._lon
                dist = math.sqrt(dlat**2 + dlon**2)
                if dist > 0.00001:
                    step = min(dist, 0.00005)
                    self._lat += (dlat / dist) * step
                    self._lon += (dlon / dist) * step
                    self._ground_speed = random.uniform(8, 12)
                    self._heading = math.degrees(math.atan2(dlon, dlat)) % 360
                else:
                    self._target_lat = None
                    self._target_lon = None
                    self._ground_speed = 0
                    if self._status == "takeoff":
                        self._status = "flying"

            if self._target_alt is not None:
                if abs(self._relative_alt - self._target_alt) > 0.5:
                    direction = 1 if self._target_alt > self._relative_alt else -1
                    self._relative_alt += direction * 0.3
                    self._vertical_speed = direction * 1.5
                else:
                    self._target_alt = None
                    self._vertical_speed = 0

            self._roll = random.uniform(-3, 3)
            self._pitch = random.uniform(-2, 2)
            self._yaw = self._heading
            self._battery_percent = max(0, self._battery_percent - 0.01)
            self._battery_voltage = 9.0 + (self._battery_percent / 100) * 3.6
            self._battery_current = random.uniform(15, 25)

        elif self._status == "landing":
            if self._relative_alt > 0.1:
                self._relative_alt = max(0, self._relative_alt - 0.5)
                self._vertical_speed = -1.5
            else:
                self._relative_alt = 0
                self._vertical_speed = 0
                self._status = "standby"
                self._ground_speed = 0
                self._armed = False

        elif self._status == "return_to_home":
            self._ground_speed = random.uniform(5, 8)
            self._battery_percent = max(0, self._battery_percent - 0.005)

        self._gps_sats = max(6, min(16, self._gps_sats + random.randint(-1, 1)))

    # ============ 通用遥测输出 ============

    def _get_telemetry_dict(self) -> dict:
        return {
            "drone_id": self.drone_id,
            "sys_id": self.sys_id,
            "mode": self.mode,
            "status": self._status,
            "flight_mode": self._flight_mode,
            "armed": self._armed,
            "latitude": round(self._lat, 7),
            "longitude": round(self._lon, 7),
            "altitude": round(self._alt + self._relative_alt, 2),
            "relative_altitude": round(self._relative_alt, 2),
            "heading": round(self._heading, 1),
            "ground_speed": round(self._ground_speed, 2),
            "vertical_speed": round(self._vertical_speed, 2),
            "battery_voltage": round(self._battery_voltage, 2),
            "battery_current": round(self._battery_current, 2),
            "battery_percent": round(self._battery_percent, 1),
            "gps_satellites": self._gps_sats,
            "gps_fix_type": self._gps_fix_type,
            "roll": round(self._roll, 2),
            "pitch": round(self._pitch, 2),
            "yaw": round(self._yaw, 1),
            "timestamp": datetime.utcnow().isoformat(),
        }

    # ============ 指令接口 ============

    async def send_command(self, command: str, params: dict) -> dict:
        """发送控制指令（真实模式发送 MAVLink，模拟模式更新状态）"""
        logger.info("[MAVLink-CMD] %s command=%s params=%s mode=%s",
                    self.drone_id, command, params, self.mode)

        handlers = {
            "arm": self._cmd_arm,
            "disarm": self._cmd_disarm,
            "takeoff": self._cmd_takeoff,
            "land": self._cmd_land,
            "rtl": self._cmd_rtl,
            "go_to": self._cmd_go_to,
            "set_mode": self._cmd_set_mode,
        }
        handler = handlers.get(command)
        if handler:
            return await handler(params)
        return {"success": False, "message": f"Unknown command: {command}"}

    def _send_mavlink_command_long(self, command_id, param1=0, param2=0, param3=0,
                                     param4=0, param5=0, param6=0, param7=0):
        """发送 MAVLink COMMAND_LONG 指令（真实模式）"""
        if not self._master:
            return False
        try:
            self._master.mav.command_long_send(
                self._master.target_system,
                self._master.target_component,
                command_id,
                0,  # confirmation
                param1, param2, param3, param4, param5, param6, param7,
            )
            return True
        except Exception as e:
            logger.error("[MAVLink] %s 发送指令失败: %s", self.drone_id, str(e))
            return False

    async def _cmd_arm(self, params):
        if self.mode == "real":
            if not self._send_mavlink_command_long(
                mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM, param1=1
            ):
                return {"success": False, "message": "ARM 指令发送失败"}
            self._armed = True
            return {"success": True, "message": "ARM 指令已发送"}
        # 模拟模式
        if self._status not in ("standby", "armed"):
            return {"success": False, "message": "当前状态无法解锁"}
        self._status = "armed"
        self._armed = True
        return {"success": True, "message": "Drone armed (模拟)"}

    async def _cmd_disarm(self, params):
        if self.mode == "real":
            if not self._send_mavlink_command_long(
                mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM, param1=0
            ):
                return {"success": False, "message": "DISARM 指令发送失败"}
            self._armed = False
            return {"success": True, "message": "DISARM 指令已发送"}
        # 模拟模式
        if self._status not in ("armed", "standby"):
            return {"success": False, "message": "飞行中无法上锁"}
        self._status = "standby"
        self._armed = False
        return {"success": True, "message": "Drone disarmed (模拟)"}

    async def _cmd_takeoff(self, params):
        altitude = params.get("altitude", 30.0)
        if self.mode == "real":
            # 先确保 GUIDED 模式
            self._master.set_mode("GUIDED")
            await asyncio.sleep(0.5)
            # 先解锁
            self._send_mavlink_command_long(
                mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM, param1=1
            )
            await asyncio.sleep(1)
            # 发送起飞指令
            if not self._send_mavlink_command_long(
                mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
                param7=altitude,  # 最小高度/目标高度
            ):
                return {"success": False, "message": "TAKEOFF 指令发送失败"}
            self._status = "takeoff"
            return {"success": True, "message": f"起飞指令已发送，目标高度 {altitude}m"}
        # 模拟模式
        self._status = "takeoff"
        self._target_alt = altitude
        self._alt = 0
        self._armed = True
        return {"success": True, "message": f"Takeoff to {altitude}m (模拟)"}

    async def _cmd_land(self, params):
        if self.mode == "real":
            if not self._send_mavlink_command_long(
                mavutil.mavlink.MAV_CMD_NAV_LAND
            ):
                return {"success": False, "message": "LAND 指令发送失败"}
            self._status = "landing"
            return {"success": True, "message": "降落指令已发送"}
        # 模拟模式
        self._status = "landing"
        self._target_alt = 0
        return {"success": True, "message": "Landing (模拟)"}

    async def _cmd_rtl(self, params):
        if self.mode == "real":
            if not self._send_mavlink_command_long(
                mavutil.mavlink.MAV_CMD_NAV_RETURN_TO_LAUNCH
            ):
                return {"success": False, "message": "RTL 指令发送失败"}
            self._status = "return_to_home"
            return {"success": True, "message": "返航指令已发送"}
        # 模拟模式
        self._status = "return_to_home"
        return {"success": True, "message": "Returning to home (模拟)"}

    async def _cmd_go_to(self, params):
        lat = params.get("latitude")
        lon = params.get("longitude")
        alt = params.get("altitude", self._relative_alt)
        if lat is None or lon is None:
            return {"success": False, "message": "需要提供 latitude 和 longitude"}

        if self.mode == "real":
            # 使用 SET_POSITION_TARGET_GLOBAL_INT 发送目标位置
            try:
                self._master.mav.set_position_target_global_int_send(
                    0,  # time_boot_ms
                    self._master.target_system,
                    self._master.target_component,
                    mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT,
                    0b0000111111111000,  # type_mask: 只使用位置
                    int(lat * 1e7),
                    int(lon * 1e7),
                    alt,
                    0, 0, 0,  # vx, vy, vz
                    0, 0, 0,  # afx, afy, afz
                    0, 0,     # yaw, yaw_rate
                )
                self._status = "flying"
                return {"success": True, "message": f"飞往 ({lat}, {lon}, {alt}m)"}
            except Exception as e:
                return {"success": False, "message": f"GOTO 指令发送失败: {str(e)}"}

        # 模拟模式
        self._target_lat = lat
        self._target_lon = lon
        self._target_alt = alt
        if self._status in ("standby", "armed"):
            self._status = "flying"
        return {"success": True, "message": f"Going to ({lat}, {lon}, {alt}m) (模拟)"}

    async def _cmd_set_mode(self, params):
        mode = params.get("mode", "GUIDED")
        if self.mode == "real":
            try:
                self._master.set_mode(mode)
                self._flight_mode = mode
                return {"success": True, "message": f"飞行模式已设置为 {mode}"}
            except Exception as e:
                return {"success": False, "message": f"设置模式失败: {str(e)}"}
        # 模拟模式
        self._flight_mode = mode
        return {"success": True, "message": f"Mode set to {mode} (模拟)"}

    def get_status(self) -> str:
        return self._status

    def get_mode(self) -> str:
        return self.mode

    def is_connected(self) -> bool:
        return self.connected


class MAVLinkService:
    """MAVLink服务：管理所有无人机连接"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._connections: Dict[str, MAVLinkConnection] = {}
        return cls._instance

    async def connect_drone(self, drone_id: str, sys_id: int,
                             connection_type: str, connection_address: str) -> MAVLinkConnection:
        """连接无人机"""
        if drone_id in self._connections and self._connections[drone_id].is_connected():
            return self._connections[drone_id]

        conn = MAVLinkConnection(drone_id, sys_id, connection_type, connection_address)
        await conn.connect()
        self._connections[drone_id] = conn
        return conn

    async def disconnect_drone(self, drone_id: str):
        """断开无人机连接"""
        conn = self._connections.pop(drone_id, None)
        if conn:
            await conn.disconnect()

    def get_connection(self, drone_id: str) -> Optional[MAVLinkConnection]:
        return self._connections.get(drone_id)

    def get_all_connections(self) -> Dict[str, MAVLinkConnection]:
        return dict(self._connections)

    def get_online_count(self) -> int:
        return sum(1 for c in self._connections.values() if c.is_connected())

    def get_real_count(self) -> int:
        return sum(1 for c in self._connections.values() if c.is_connected() and c.get_mode() == "real")

    def get_simulation_count(self) -> int:
        return sum(1 for c in self._connections.values() if c.is_connected() and c.get_mode() == "simulation")

    async def broadcast_command(self, command: str, params: dict, drone_ids: list = None) -> dict:
        """向多架无人机广播指令"""
        targets = drone_ids or list(self._connections.keys())
        results = {}
        for did in targets:
            conn = self._connections.get(did)
            if conn and conn.is_connected():
                results[did] = await conn.send_command(command, params)
            else:
                results[did] = {"success": False, "message": "Drone not connected"}
        return results


# 全局单例
mavlink_service = MAVLinkService()
