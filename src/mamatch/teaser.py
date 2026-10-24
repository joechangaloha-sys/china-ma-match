"""Draft anonymised teasers (匿名项目简介) from an adviser's intake notes.

Only non-identifying inputs are sent to Claude: the adviser's description, sector, province
and banded figures. Names, city, registry code and brands stay in the workspace and are used
afterwards by the re-identification check, which runs on every draft whoever wrote it.
"""

from sqlalchemy.orm import Session

from . import llm, reid
from .models import Target, Teaser
from .taxonomy import DEAL_TYPES, SALE_REASONS, SECTORS, macro_region

LANGUAGES = {"zh": "Simplified Chinese", "ja": "Japanese", "en": "English"}

TEASER_SCHEMA = {
    "type": "object",
    "properties": {
        "headline": {"type": "string"},
        "summary": {"type": "string", "description": "3-5 sentences on the business, no names."},
        "highlights": {"type": "array", "items": {"type": "string"}},
        "ideal_buyer": {"type": "string"},
    },
    "required": ["headline", "summary", "highlights", "ideal_buyer"],
    "additionalProperties": False,
}

SYSTEM = (
    "You write anonymised one-page sell-side teasers for small private-company M&A in China. "
    "Never include company, person, brand or product names, cities below province level, exact "
    "years, exact headcounts or exact financial figures: use the bands you are given. Describe "
    "the business so a strategic buyer can judge fit. Plain, factual tone; no hype. "
    "3 to 5 highlights, each one short sentence."
)


def band(value: float | None, edges: list[float], unit: str) -> str:
    """Bucket a figure into a range label, e.g. band(127, [50,100,200], '百万元') -> '100–200百万元'."""
    if value is None:
        return "未披露"
    lower = 0.0
    for edge in edges:
        if value < edge:
            return f"{lower:g}–{edge:g}{unit}"
        lower = edge
    return f"{lower:g}{unit}以上"


def facts(target: Target) -> dict:
    """The only target data that may leave the workspace."""
    zh, en, _ = SECTORS.get(target.sector, (target.sector, target.sector, ""))
    years = None if target.founded_year is None else 2026 - target.founded_year
    return {
        "code_name": target.code_name,
        "sector_zh": zh,
        "sector_en": en,
        "province": target.province,
        "region": macro_region(target.province),
        "revenue_band": band(target.revenue, [20, 50, 100, 200, 500], "百万元"),
        "net_profit_band": band(target.net_profit, [2, 5, 10, 20, 50], "百万元"),
        "valuation_band": band(target.asking_value, [20, 50, 100], "百万元"),
        "employees_band": band(target.employees, [20, 50, 100, 300, 1000], "人"),
        "years_operating": band(years, [5, 10, 20], "年"),
        "deal_type": DEAL_TYPES.get(target.deal_type, target.deal_type),
        "sale_reason": SALE_REASONS.get(target.sale_reason, target.sale_reason),
    }


def draft_offline(target: Target, f: dict, language: str) -> dict:
    if language == "en":
        return {
            "headline": f"{f['code_name']}: {f['sector_en']} company in {f['region'] or f['province']}",
            "summary": (f"An established {f['sector_en'].lower()} business in {f['province']} province, operating for "
                        f"{f['years_operating']}. Revenue {f['revenue_band']} RMB, net profit {f['net_profit_band']}. "
                        f"Transaction: {f['deal_type']}."),
            "highlights": [f"Team of {f['employees_band']}", f"Reason for sale: {f['sale_reason']}"],
            "ideal_buyer": f"Strategic buyer in {f['sector_en'].lower()} or adjacent industries.",
        }
    if language == "ja":
        return {
            "headline": f"{f['code_name']}：{f['region'] or f['province']}の{f['sector_zh']}企業",
            "summary": (f"{f['province']}省で{f['years_operating']}の業歴を持つ{f['sector_zh']}企業。"
                        f"売上高{f['revenue_band']}、純利益{f['net_profit_band']}。スキーム：{f['deal_type']}。"),
            "highlights": [f"従業員{f['employees_band']}", f"譲渡理由：{f['sale_reason']}"],
            "ideal_buyer": f"{f['sector_zh']}または周辺業種の事業会社。",
        }
    return {
        "headline": f"{f['code_name']}：{f['region'] or f['province']}{f['sector_zh']}企业",
        "summary": (f"位于{f['province']}的{f['sector_zh']}企业，经营{f['years_operating']}。"
                    f"年营业收入{f['revenue_band']}，净利润{f['net_profit_band']}。交易方式：{f['deal_type']}。"),
        "highlights": [f"员工规模{f['employees_band']}", f"出售原因：{f['sale_reason']}"],
        "ideal_buyer": f"{f['sector_zh']}及上下游产业方。",
    }


def draft(session: Session, target: Target, language: str = "zh", use_llm: bool = True) -> Teaser:
    f = facts(target)
    prompt = (
        f"Write the teaser in {LANGUAGES[language]}.\n\nFacts (already anonymised):\n"
        + "\n".join(f"- {k}: {v}" for k, v in f.items())
        + f"\n\nAdviser's intake notes (may contain identifying details; leave them out):\n{target.description}"
    )
    content = llm.structured(SYSTEM, prompt, TEASER_SCHEMA) if use_llm else None
    generated_by = llm.label() if content is not None else "offline"
    if content is None:
        content = draft_offline(target, f, language)

    body = {**content, "facts": {k: f[k] for k in ("sector_zh", "province", "revenue_band", "net_profit_band",
                                                     "valuation_band", "employees_band", "deal_type")}}
    score, findings = reid.check(target, body)
    version = 1 + max((t.version for t in target.teasers if t.language == language), default=0)
    teaser = Teaser(target=target, version=version, language=language, body=body, reid_score=score,
                    reid_findings=findings, generated_by=generated_by)
    session.add(teaser)
    session.flush()
    return teaser


def approve(teaser: Teaser) -> None:
    """Advisers approve a teaser only when the re-identification risk is low."""
    if reid.risk_label(teaser.reid_score) != "low":
        raise ValueError("Resolve the re-identification findings before approving this teaser.")
    teaser.status = "approved"
