"""元数据登记接口：维护元数据记录，覆盖提交登记、确认生效、作废记录等动作。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.metainfo import MetainfoService

router = APIRouter(prefix="/api/metainfo", tags=["元数据登记"])

service = MetainfoService()

STATUSES = ["待登记", "待补充", "已生效", "已作废"]


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按元数据编号检索"),
    status: str | None = Query(default=None, description="待登记、待补充、已生效、已作废"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """按元数据编号与状态过滤元数据登记列表；没有数据时返回空页，不报错。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total = service.list_entries(keyword=keyword, status=status, page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/export")
def export_entries() -> dict[str, Any]:
    """导出元数据登记清单：返回当前过滤条件下的全量数据。"""
    items, total = service.list_entries(page=1, size=10000)
    return {"module": "metainfo", "total": total, "items": items}


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条元数据记录明细；不存在时给出可读的错误说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"元数据记录 {entry_id} 不存在或已归档")
    return entry


@router.get("/{entry_id}/versions")
def list_versions(entry_id: int) -> dict[str, Any]:
    """读取单条记录的版本历史，与列表、详情共用同一份数据；没有版本数据时返回空列表。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"元数据记录 {entry_id} 不存在或已归档")
    versions = service.list_versions(entry_id) or []
    return {
        "entry_id": entry_id,
        "元数据编号": entry.get("元数据编号"),
        "total": len(versions),
        "items": versions,
    }


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """登记一条元数据记录，缺字段时指明是哪条记录、缺哪些字段，而不是静默丢弃。"""
    entry, missing = service.create_entry(payload.values)
    if missing:
        code = str(payload.values.get("元数据编号") or "").strip()
        prefix = f"元数据记录 {code} " if code else "新登记的元数据记录 "
        return ActionResult(ok=False, message=f"{prefix}缺少必填字段：{'、'.join(missing)}")
    return ActionResult(ok=True, message="元数据记录已登记", entry=entry)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(entry_id: int, payload: EntryPayload) -> ActionResult:
    """对单条元数据记录执行提交登记、确认生效、作废记录；终态与越权动作会被拦下并说明原因。"""
    action = str(payload.values.get("action") or "").strip()
    entry, message = service.run_action(entry_id, action)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)
