"""元数据登记业务规则：状态流转、版本留痕、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

import re
from datetime import date
from typing import Any

from app.store import store

MODULE = "metainfo"
REQUIRED_FIELDS = ["元数据编号", "关联站点", "元数据类型"]
STATUS_ORDER = ["待登记", "待补充", "已生效", "已作废"]
# 已生效、已作废都是终态：一旦进入就不允许再执行任何动作，更不能作废后重新提交登记。
TERMINAL_STATUSES = ["已生效", "已作废"]
# 每个动作只允许从特定前置状态发起，落到固定的目标状态。
ACTION_RULES = {
    "提交登记": {"from": ["待登记", "待补充"], "to": "已生效"},
    "确认生效": {"from": ["待登记", "待补充"], "to": "已生效"},
    "作废记录": {"from": ["待登记", "待补充"], "to": "已作废"},
}
DEFAULT_VERSION = "V1.0"
_VERSION_PATTERN = re.compile(r"[Vv]?(\d+)\.(\d+)")


def _next_version(current: Any, has_history: bool) -> str:
    """推算下一段版本号：首次生效沿用当前号，已有历史则递增小版本，保证可追溯。"""
    match = _VERSION_PATTERN.fullmatch(str(current or "").strip())
    if match is None:
        return DEFAULT_VERSION
    major, minor = int(match.group(1)), int(match.group(2))
    if has_history:
        minor += 1
    return f"V{major}.{minor}"


class MetainfoService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("元数据编号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def list_versions(self, entry_id: int) -> list[dict[str, Any]] | None:
        """读取单条记录的版本历史；记录不存在时返回 None，没有版本数据时返回空列表。"""
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None
        return list(entry.get("versions") or [])

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        for field in REQUIRED_FIELDS:
            entry[field] = str(values.get(field)).strip()
        entry["版本号"] = str(values.get("版本号") or "").strip() or DEFAULT_VERSION
        entry["变更内容"] = str(values.get("变更内容") or "").strip()
        entry["登记人员"] = str(values.get("登记人员") or "").strip()
        entry["生效日期"] = None
        entry["versions"] = []
        self._apply_status(entry, "待登记")
        rows.append(entry)
        return entry, []

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"元数据记录 {entry_id} 不存在或已归档"
        rule = ACTION_RULES.get(action)
        if rule is None:
            return None, f"动作「{action}」不属于元数据登记可执行范围"
        code = entry.get("元数据编号") or f"记录{entry_id}"
        current = str(entry.get("status") or "")
        if current in TERMINAL_STATUSES:
            return None, f"元数据记录 {code} 已处于终态「{current}」，不能重新{action}"
        if current not in rule["from"]:
            return None, f"元数据记录 {code} 当前状态为「{current}」，不允许执行「{action}」"
        target = rule["to"]
        if target == "已生效":
            self._record_version(entry, action)
        self._apply_status(entry, target)
        return entry, f"元数据记录 {code} 已{action}，当前状态「{target}」"

    def _apply_status(self, entry: dict[str, Any], status: str) -> None:
        """状态落库时同步展示字段与标记位，保证列表、详情、版本看到的是同一份数据。"""
        entry["status"] = status
        entry["元数据状态"] = status
        entry["pending"] = status not in TERMINAL_STATUSES
        entry["abnormal"] = status == "已作废"

    def _record_version(self, entry: dict[str, Any], action: str) -> None:
        """确认生效时把版本变化写进历史：版本号、生效日期一旦落库就不再变动。"""
        history = entry.setdefault("versions", [])
        version = _next_version(entry.get("版本号"), has_history=bool(history))
        today = date.today().isoformat()
        entry["版本号"] = version
        entry["生效日期"] = today
        history.append({
            "版本号": version,
            "变更内容": entry.get("变更内容") or "—",
            "登记人员": entry.get("登记人员") or "—",
            "生效日期": today,
            "动作": action,
        })
