"""Turn an announcement into a structured acquisition signal, then fold it into a buyer profile."""

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import llm
from ..models import Buyer, BuyerSignal
from ..taxonomy import REGIONS, SECTOR_KEYWORDS, SECTORS
from .cninfo import Announcement

SIGNAL_SCHEMA = {
    "type": "object",
    "properties": {
        "is_acquisition": {"type": "boolean", "description": "The announcing company is buying (not selling) equity or a business."},
        "is_related_party": {"type": "boolean"},
        "is_cross_border": {"type": "boolean"},
        "counterparty": {"type": "string", "description": "Name of the company being acquired, or empty."},
        "target_sectors": {"type": "array", "items": {"type": "string", "enum": list(SECTORS)}},
        "target_provinces": {"type": "array", "items": {"type": "string", "enum": list(REGIONS)}},
        "deal_size_rmb_m": {"type": ["number", "null"], "description": "Consideration in RMB millions if stated."},
        "rationale": {"type": "string", "description": "One sentence in Chinese on why the buyer is acquiring."},
    },
    "required": ["is_acquisition", "is_related_party", "is_cross_border", "counterparty",
                 "target_sectors", "target_provinces", "deal_size_rmb_m", "rationale"],
    "additionalProperties": False,
}

SYSTEM = (
    "You read Chinese listed-company announcements and extract acquisition signals for an M&A "
    "buyer index. Use only what the text states; leave fields empty or null when it does not say. "
    "Sector codes and province names must come from the allowed lists."
)

_SELL_WORDS = ("出售", "转让所持", "减持", "剥离")
_COUNTERPARTY = re.compile(r"(?:收购|购买|受让)(.+?(?:有限公司|有限责任公司|股份有限公司|公司))")
_CITY_PROVINCE = {"青岛": "山东", "烟台": "山东", "东莞": "广东", "深圳": "广东", "苏州": "江苏",
                  "宁波": "浙江", "杭州": "浙江", "无锡": "江苏", "南京": "江苏", "合肥": "安徽"}


def extract_offline(ann: Announcement) -> dict:
    title = ann.title
    counterparty = m.group(1) if (m := _COUNTERPARTY.search(title)) else ""
    scope = counterparty or title
    sectors = [code for code, words in SECTOR_KEYWORDS.items() if any(w in scope for w in words)]
    provinces = [p for p in REGIONS if p in counterparty]
    provinces += [p for city, p in _CITY_PROVINCE.items() if city in counterparty and p not in provinces]
    return {
        "is_acquisition": not any(w in title for w in _SELL_WORDS),
        "is_related_party": "关联交易" in title,
        "is_cross_border": "境外" in title or "海外" in title,
        "counterparty": counterparty,
        "target_sectors": sectors,
        "target_provinces": provinces,
        "deal_size_rmb_m": None,
        "rationale": "",
    }


def extract(ann: Announcement, body_text: str = "") -> tuple[dict, str]:
    """Returns (signal, generated_by)."""
    prompt = f"公司: {ann.sec_name} ({ann.sec_code})\n标题: {ann.title}\n"
    if body_text:
        prompt += f"\n正文节选:\n{body_text[:20000]}"
    result = llm.structured(SYSTEM, prompt, SIGNAL_SCHEMA, effort="low")
    if result is not None:
        return result, llm.label()
    return extract_offline(ann), "offline"


def upsert(session: Session, ann: Announcement, signal: dict, generated_by: str) -> BuyerSignal | None:
    """Record the signal and update the buyer profile. Returns None if already indexed or not a buy."""
    if not signal["is_acquisition"]:
        return None
    buyer = session.scalar(select(Buyer).where(Buyer.source == "cninfo", Buyer.external_id == ann.sec_code))
    if buyer is None:
        buyer = Buyer(name=ann.sec_name, kind="listed", source="cninfo", external_id=ann.sec_code,
                      sectors=[], target_sectors=[], target_regions=[])
        session.add(buyer)
        session.flush()
    elif session.scalar(select(BuyerSignal.id).where(BuyerSignal.buyer_id == buyer.id, BuyerSignal.url == ann.url)):
        return None

    # Related-party and cross-border deals say little about appetite for domestic private targets,
    # so they are kept as evidence but do not widen the profile.
    if not signal["is_related_party"] and not signal["is_cross_border"]:
        buyer.target_sectors = sorted(set(buyer.target_sectors) | set(signal["target_sectors"]))
        buyer.target_regions = sorted(set(buyer.target_regions) | set(signal["target_provinces"]))
        if (size := signal.get("deal_size_rmb_m")) is not None:
            buyer.deal_size_min = min(size, buyer.deal_size_min) if buyer.deal_size_min is not None else size
            buyer.deal_size_max = max(size, buyer.deal_size_max) if buyer.deal_size_max is not None else size
        if signal["rationale"]:
            buyer.rationale = signal["rationale"]

    sig = BuyerSignal(buyer=buyer, kind="announcement", title=ann.title, url=ann.url,
                      published_at=ann.published_at, extracted={**signal, "generated_by": generated_by})
    session.add(sig)
    return sig
