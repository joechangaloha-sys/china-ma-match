"""Explicit status for each seller mandate. Changes are made by people, never by an AI response.

The deal manager moves a mandate forward one step at a time, pauses or resumes matching, or
withdraws/rejects it. Publishing (listing.publish) and closing (fees.record_closing) also set it.
"""

from sqlalchemy.orm import Session

from . import auth
from .models import Target, User

STATUSES: dict[str, str] = {
    "draft": "草稿 Draft",
    "documents_requested": "待补资料 Documents requested",
    "extraction_review": "资料审核 Extraction review",
    "seller_approval": "待卖方确认 Seller approval",
    "in_market": "推介中 In market",
    "matching_paused": "暂停匹配 Matching paused",
    "introduction": "已引荐 Introduction",
    "nda": "保密协议 NDA",
    "disclosure": "受限披露 Restricted disclosure",
    "diligence": "尽职调查 Diligence",
    "loi": "意向书 LOI",
    "closing": "交割中 Closing",
    "closed": "已完成 Closed",
    "withdrawn": "卖方撤回 Withdrawn",
    "rejected": "不受理 Rejected",
}
_FORWARD = ["draft", "documents_requested", "extraction_review", "seller_approval", "in_market", "introduction",
            "nda", "disclosure", "diligence", "loi", "closing", "closed"]
TERMINAL = {"closed", "withdrawn", "rejected"}
# Statuses in which the mandate may be shown to buyers (listing or outreach).
MARKETABLE = {"in_market", "introduction", "nda", "disclosure", "diligence", "loi"}


def allowed_next(status: str) -> list[str]:
    if status in TERMINAL:
        return []
    if status == "matching_paused":
        return ["in_market", "withdrawn", "rejected"]
    nxt = []
    if status in _FORWARD and status != "closing":  # closing -> closed only through the closing form
        nxt.append(_FORWARD[_FORWARD.index(status) + 1])
    if status in MARKETABLE:
        nxt.append("matching_paused")
    return nxt + ["withdrawn", "rejected"]


def move(session: Session, target: Target, to: str, user: User | None, note: str = "") -> None:
    if to not in allowed_next(target.status):
        raise ValueError(f"Cannot move from {target.status} to {to}")
    auth.log(session, user, "status_change", target_id=target.id, from_status=target.status, to_status=to, note=note)
    target.status = to
    if to in ("matching_paused", "withdrawn", "rejected") and target.visibility == "listed":
        from . import listing

        listing.unpublish(target)
