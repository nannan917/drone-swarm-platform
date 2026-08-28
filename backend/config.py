"""
无人机集群管理平台 - 全局配置
"""
import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # 服务配置
    APP_NAME: str = "Drone Swarm Management Platform"
    APP_VERSION: str = "1.0.0"
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = True

    # 数据库
    DATABASE_URL: str = "sqlite+aiosqlite:///./data/drone_swarm.db"

    # MAVLink 配置
    MAVLINK_BAUDRATE: int = 57600
    MAVLINK_DEFAULT_SYS_ID: int = 1
    MAVLINK_UDP_PORT: int = 14550

    # 集群配置
    MAX_DRONES: int = 50
    HEARTBEAT_TIMEOUT: int = 10  # 秒，超过此时间无心跳视为离线
    TELEMETRY_INTERVAL: float = 0.5  # 遥测推送间隔（秒）

    # ARP 配置
    ARP_CACHE_TTL: int = 300  # ARP缓存过期时间（秒）
    ARP_TABLE_PATH: str = "./data/arp_table.json"

    # 安全
    API_TOKEN: str = "drone-swarm-admin-token"

    class Config:
        env_file = ".env"


settings = Settings()

# 确保数据目录存在
os.makedirs("./data", exist_ok=True)
