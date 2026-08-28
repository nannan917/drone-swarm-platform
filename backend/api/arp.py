"""
ARP API 路由 - 无人机地址解析协议
"""
from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from schemas import ARPEntry, ARPResolveRequest
from arp.resolver import arp_resolver

router = APIRouter(prefix="/arp", tags=["arp"])


@router.get("/table", response_model=List[ARPEntry], summary="查看ARP表")
async def get_arp_table():
    """获取当前所有ARP解析条目（drone_id -> 通信地址映射）"""
    entries = arp_resolver.get_all_entries()
    return [e.to_dict() for e in entries]


@router.post("/resolve", summary="ARP地址解析")
async def resolve_address(request: ARPResolveRequest):
    """
    ARP Request: 根据drone_id解析通信地址
    命中缓存返回地址，未命中返回404
    """
    entry = arp_resolver.resolve(request.drone_id)
    if entry:
        return {"resolved": True, "entry": entry.to_dict()}
    return {"resolved": False, "message": f"No ARP entry for {request.drone_id}, please register first"}


@router.post("/refresh/{drone_id}", summary="刷新ARP条目TTL")
async def refresh_entry(drone_id: str):
    """刷新指定无人机的ARP缓存过期时间（模拟收到gratuitous ARP）"""
    success = arp_resolver.refresh_entry(drone_id)
    return {"success": success, "drone_id": drone_id}


@router.post("/cleanup", summary="清理过期ARP条目")
async def cleanup_expired():
    """手动触发ARP表老化清理"""
    count = arp_resolver.cleanup_expired()
    return {"cleaned": count, "remaining": arp_resolver.get_table_size()}


@router.get("/stats", summary="ARP统计信息")
async def arp_stats():
    return {
        "total_entries": arp_resolver.get_table_size(),
        "cache_ttl": 300,
        "table_path": "./data/arp_table.json",
    }
