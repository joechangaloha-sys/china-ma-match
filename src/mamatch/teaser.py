"""Draft anonymised teasers (匿名项目简介) from an adviser's intake notes.

AI calls are currently disabled pending provider/data-transfer review. Drafts use structured
fields and deterministic templates. Names, city, registry code and brands stay in the workspace and are used
afterwards by the re-identification check, which runs on every draft whoever wrote it.
"""

from sqlalchemy.orm import Session

from . import reid, release
from .models import Target, Teaser
from .taxonomy import DEAL_TYPES, SALE_REASONS, SECTORS, macro_region

LANGUAGES = {"zh": "Simplified Chinese", "en": "English"}

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


# Band edges shared by teasers, listing cards and the public search, so a search can only ever
# narrow a company to the same band its card already shows. Pilot deals are small (RMB 2–20m).
REVENUE_EDGES = [5, 10, 20, 50, 100, 200, 500]  # RMB m
PROFIT_EDGES = [1, 2, 5, 10, 20, 50]  # RMB m
VALUATION_EDGES = [5, 10, 20, 50, 100]  # RMB m
EMPLOYEE_EDGES = [10, 20, 50, 100, 300, 1000]
YEARS_EDGES = [3, 5, 10, 20]


def band(value: float | None, edges: list[float], unit: str) -> str:
    """Bucket a figure into a range label, e.g. band(127, [50,100,200], '百万元') -> '100–200百万元'."""
    if value is None:
        return "未披露"
    if value < 0:
        return "亏损"
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
        "revenue_band": band(target.revenue, REVENUE_EDGES, "百万元"),
        "net_profit_band": band(target.net_profit, PROFIT_EDGES, "百万元"),
        "valuation_band": band(target.asking_value, VALUATION_EDGES, "百万元"),
        "employees_band": band(target.employees, EMPLOYEE_EDGES, "人"),
        "years_operating": band(years, YEARS_EDGES, "年"),
        "deal_type": DEAL_TYPES.get(target.deal_type, target.deal_type),
        "sale_reason": SALE_REASONS.get(target.sale_reason, target.sale_reason),
    }


def localised(f: dict, language: str) -> dict:
    """Facts with labels and bands in one language (the stored facts are bilingual)."""
    from . import i18n

    lang = "en" if language == "en" else "zh"
    out = dict(f)
    for k in ("deal_type", "sale_reason"):
        out[k] = i18n.tr(f[k], lang)
    if lang == "en":
        for k in ("revenue_band", "net_profit_band", "valuation_band", "employees_band", "years_operating", "region", "province"):
            out[k] = i18n.val(f[k], "en")
    if f.get("net_profit_band") == "亏损" and language == "en":
        out["net_profit_band"] = "Loss-making"
    return out


def draft_offline(target: Target, f: dict, language: str) -> dict:
    f = localised(f, language)
    if language == "en":
        return {
            "headline": f"{f['code_name']}: {f['sector_en']} company in {f['region'] or f['province']}",
            "summary": (f"An established {f['sector_en'].lower()} business in {f['province']} province, operating for "
                        f"{f['years_operating']}. Revenue {f['revenue_band']}, net profit {f['net_profit_band']}. "
                        f"Transaction: {f['deal_type']}."),
            "highlights": [f"Team of {f['employees_band']}", f"Reason for sale: {f['sale_reason']}"],
            "ideal_buyer": f"Strategic buyer in {f['sector_en'].lower()} or adjacent industries.",
        }
    return {
        "headline": f"{f['code_name']}：{f['region'] or f['province']}{f['sector_zh']}企业",
        "summary": (f"位于{f['province']}的{f['sector_zh']}企业，经营{f['years_operating']}。"
                    f"年营业收入{f['revenue_band']}，净利润{f['net_profit_band']}。交易方式：{f['deal_type']}。"),
        "highlights": [f"员工规模{f['employees_band']}", f"出售原因：{f['sale_reason']}"],
        "ideal_buyer": f"{f['sector_zh']}及上下游产业方。",
    }


def draft(session: Session, target: Target, language: str = "zh", use_llm: bool = True) -> Teaser:
    if language not in LANGUAGES:
        raise ValueError("Unknown language")
    f = facts(target)
    # Provider/data-transfer review is pending: do not transmit intake notes or call AI.
    content = draft_offline(target, f, language)
    generated_by = "offline"

    body = {**content, "facts": {k: f[k] for k in ("sector_zh", "province", "revenue_band", "net_profit_band",
                                                     "valuation_band", "employees_band", "deal_type")}}
    # The public card carries additional assertions (products, stake, premises, etc.).
    # Review them alongside the teaser, before the same source snapshot can be listed.
    from . import listing
    body['listing_claims'] = {k: v for k, v in listing.card(target).items()
                              if k not in {'ready', 'checks', 'checks_as_of'}}
    score, findings = reid.check(target, body)
    version = 1 + max((t.version for t in target.teasers if t.language == language), default=0)
    teaser = Teaser(target=target, version=version, language=language, body=body, reid_score=score,
                    reid_findings=findings, generated_by=generated_by, source_hash=release.source_digest(target))
    session.add(teaser)
    session.flush()
    return teaser


def approve(teaser: Teaser, user=None) -> None:
    # Preserve the conservative stored-risk check as well as recomputing it at release.
    if reid.risk_label(teaser.reid_score) != "low":
        raise ValueError("Resolve the re-identification findings before approving this teaser.")
    release.approve(teaser, user)


def seller_approve(teaser: Teaser, user=None) -> None:
    release.seller_approve(teaser, user)
