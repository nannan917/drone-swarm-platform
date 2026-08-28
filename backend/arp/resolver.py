"""
ARP 解析器核心实现

设计思路（类比网络ARP协议）：
- ARP Request: 已知 drone_id（逻辑地址），查询 sys_id + 通信地址（物理地址）
- ARP Reply: 返回解析结果，并缓存到本地ARP表
- ARP Table: 维护映射关系，带老化时间（TTL）
- Gratuitous ARP: 无人机主动宣告自己的地址（注册/心跳时触发）
"""
import json
import os
import time
import logging
import threading
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from config import settings

logger = logging.getLogger("drone-swarm.arp")


class ARPEntryData:
    """ARP表条目"""
    def __init__(self, drone_id: str, sys_id: int, connection_type: str,
                 connection_address: str, ttl: int = None):
        self.drone_id = drone_id
        self.sys_id = sys_id
        self.connection_type = connection_type
        self.connection_address = connection_address
        self.resolved_at = time.time()
        self.ttl = ttl or settings.ARP_CACHE_TTL
        self.expires_at = self.resolved_at + self.ttl

    def is_expired(self) -> bool:
        return time.time() > self.expires_at

    def refresh(self, ttl: int = None):
        """刷新条目（收到心跳/ gratuitous ARP时调用）"""
        self.resolved_at = time.time()
        self.ttl = ttl or settings.ARP_CACHE_TTL
        self.expires_at = self.resolved_at + self.ttl

    def to_dict(self) -> dict:
        return {
            "drone_id": self.drone_id,
            "sys_id": self.sys_id,
            "connection_type": self.connection_type,
            "connection_address": self.connection_address,
            "resolved_at": datetime.fromtimestamp(self.resolved_at).isoformat(),
            "expires_at": datetime.fromtimestamp(self.expires_at).isoformat(),
            "ttl": self.ttl,
        }


class ARPResolver:
    """
    无人机地址解析器

    使用单例模式，全局共享一个ARP表
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._table: Dict[str, ARPEntryData] = {}
        self._sys_id_counter = 10  # sys_id从10开始分配，1-9保留
        self._initialized = True
        self._load_from_disk()
        logger.info("ARP Resolver initialized, %d entries loaded", len(self._table))

    # ============ 核心API ============

    def resolve(self, drone_id: str) -> Optional[ARPEntryData]:
        """
        ARP Request: 根据drone_id解析地址
        命中缓存且未过期 -> 返回缓存
        未命中或已过期 -> 返回None（调用方需触发注册流程）
        """
        entry = self._table.get(drone_id)
        if entry is None:
            logger.info("[ARP-REQUEST] %s -> MISS (not in table)", drone_id)
            return None
        if entry.is_expired():
            logger.info("[ARP-REQUEST] %s -> MISS (expired)", drone_id)
            del self._table[drone_id]
            return None
        logger.info("[ARP-REPLY] %s -> sys_id=%d addr=%s:%s",
                    drone_id, entry.sys_id, entry.connection_type, entry.connection_address)
        return entry

    def register(self, drone_id: str, connection_type: str, connection_address: str,
                 sys_id: int = None) -> ARPEntryData:
        """
        Gratuitous ARP / 注册: 无人机主动宣告地址
        如果已存在则更新，不存在则新建并分配sys_id
        """
        existing = self._table.get(drone_id)
        if existing:
            existing.connection_type = connection_type
            existing.connection_address = connection_address
            if sys_id is not None:
                existing.sys_id = sys_id
            existing.refresh()
            logger.info("[ARP-UPDATE] %s -> sys_id=%d addr=%s:%s",
                        drone_id, existing.sys_id, connection_type, connection_address)
            self._save_to_disk()
            return existing

        assigned_sys_id = sys_id or self._allocate_sys_id()
        entry = ARPEntryData(drone_id, assigned_sys_id, connection_type, connection_address)
        self._table[drone_id] = entry
        logger.info("[ARP-REGISTER] %s -> sys_id=%d addr=%s:%s (new entry)",
                    drone_id, assigned_sys_id, connection_type, connection_address)
        self._save_to_disk()
        return entry

    def unregister(self, drone_id: str) -> bool:
        """注销: 从ARP表移除"""
        if drone_id in self._table:
            del self._table[drone_id]
            logger.info("[ARP-UNREGISTER] %s removed", drone_id)
            self._save_to_disk()
            return True
        return False

    def refresh_entry(self, drone_id: str) -> bool:
        """刷新条目TTL（收到心跳时调用）"""
        entry = self._table.get(drone_id)
        if entry:
            entry.refresh()
            return True
        return False

    def get_all_entries(self) -> List[ARPEntryData]:
        """获取所有有效条目"""
        return [e for e in self._table.values() if not e.is_expired()]

    def get_table_size(self) -> int:
        return len(self._table)

    def cleanup_expired(self) -> int:
        """清理过期条目，返回清理数量"""
        expired = [k for k, v in self._table.items() if v.is_expired()]
        for k in expired:
            del self._table[k]
        if expired:
            logger.info("[ARP-CLEANUP] removed %d expired entries", len(expired))
            self._save_to_disk()
        return len(expired)

    # ============ 内部方法 ============

    def _allocate_sys_id(self) -> int:
        """分配唯一的MAVLink System ID"""
        used_ids = {e.sys_id for e in self._table.values()}
        while self._sys_id_counter in used_ids:
            self._sys_id_counter += 1
            if self._sys_id_counter > 250:  # MAVLink sys_id最大255
                self._sys_id_counter = 10
        sid = self._sys_id_counter
        self._sys_id_counter += 1
        return sid

    def _save_to_disk(self):
        """持久化ARP表到JSON文件"""
        try:
            data = {
                "version": "1.0",
                "saved_at": datetime.utcnow().isoformat(),
                "entries": [
                    {
                        "drone_id": e.drone_id,
                        "sys_id": e.sys_id,
                        "connection_type": e.connection_type,
                        "connection_address": e.connection_address,
                        "resolved_at": e.resolved_at,
                        "ttl": e.ttl,
                    }
                    for e in self._table.values()
                ]
            }
            os.makedirs(os.path.dirname(settings.ARP_TABLE_PATH), exist_ok=True)
            with open(settings.ARP_TABLE_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error("[ARP-PERSIST] failed to save: %s", str(e))

    def _load_from_disk(self):
        """从JSON文件恢复ARP表"""
        try:
            if not os.path.exists(settings.ARP_TABLE_PATH):
                return
            with open(settings.ARP_TABLE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            for item in data.get("entries", []):
                entry = ARPEntryData(
                    drone_id=item["drone_id"],
                    sys_id=item["sys_id"],
                    connection_type=item["connection_type"],
                    connection_address=item["connection_address"],
                    ttl=item.get("ttl", settings.ARP_CACHE_TTL),
                )
                entry.resolved_at = item.get("resolved_at", time.time())
                entry.expires_at = entry.resolved_at + entry.ttl
                if not entry.is_expired():
                    self._table[entry.drone_id] = entry
            logger.info("[ARP-LOAD] restored %d entries from disk", len(self._table))
        except Exception as e:
            logger.error("[ARP-LOAD] failed: %s", str(e))


# 全局单例
arp_resolver = ARPResolver()
