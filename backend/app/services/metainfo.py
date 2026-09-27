"""元数据登记业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

from datetime import date
from typing import Any

from app.store import store

MODULE = "metainfo"
REQUIRED_FIELDS = ["元数据编号", "关联站点", "元数据类型"]
# 提交登记、确认生效前必须补齐的字段；缺失时提示里要指出是哪一条
ACTION_REQUIRED_FIELDS = ["元数据编号", "关联站点"]
STATUS_ORDER = ["待登记", "待补充", "已生效", "已作废"]
TERMINAL_STATUSES = ("已生效", "已作废")
# 状态机：动作 -> (允许执行的当前状态, 目标状态)；终态不在任何起始状态里，自然不可重开
ACTION_RULES = {
    "提交登记": (("待登记",), "待补充"),
    "确认生效": (("待补充",), "已生效"),
    "作废记录": (("待登记", "待补充"), "已作废"),
}
NEGATIVE_ACTIONS = ["作废记录"]


def _entry_label(entry: dict[str, Any]) -> str:
    """在提示里指到具体一条记录：优先用元数据编号，没填就退回记录 id。"""
    code = str(entry.get("元数据编号") or "").strip()
    if code:
        return f"元数据记录 {code}（#{entry.get('id')}）"
    return f"元数据记录 #{entry.get('id')}"


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

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        for field in ["元数据编号", "关联站点", "元数据类型", "变更内容", "登记人员"]:
            entry[field] = str(values.get(field) or "").strip()
        entry["版本号"] = ""
        entry["生效日期"] = ""
        entry["版本历史"] = []
        entry["status"] = STATUS_ORDER[0]
        entry["元数据状态"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        return entry, []

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"元数据记录 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于元数据登记可执行范围"
        label = _entry_label(entry)
        current = str(entry.get("status") or "")
        if current in TERMINAL_STATUSES:
            return None, f"{label}已处于终态（{current}），不允许再执行{action}"
        allowed_from, target = ACTION_RULES[action]
        if current not in allowed_from:
            return None, f"{label}当前状态为「{current}」，不能执行{action}"
        if action in ("提交登记", "确认生效"):
            missing = [field for field in ACTION_REQUIRED_FIELDS if not str(entry.get(field) or "").strip()]
            if missing:
                return None, f"{label}缺少必填字段：{'、'.join(missing)}，无法{action}"
        entry["status"] = target
        entry["元数据状态"] = target
        entry["pending"] = target not in TERMINAL_STATUSES
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        if action == "确认生效":
            self._record_version(entry, action)
        return entry, f"{label}已{action}"

    def _record_version(self, entry: dict[str, Any], action: str) -> None:
        """确认生效时把当前内容固化成一个版本，早先版本原样保留。"""
        history = entry.setdefault("版本历史", [])
        version = f"V{len(history) + 1}"
        today = date.today().isoformat()
        history.append({
            "版本号": version,
            "变更内容": entry.get("变更内容") or "",
            "登记人员": entry.get("登记人员") or "",
            "生效日期": today,
            "动作": action,
        })
        entry["版本号"] = version
        entry["生效日期"] = today
