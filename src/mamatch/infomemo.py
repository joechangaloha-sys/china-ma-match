"""Information memorandum (信息备忘录) drafts, part of the preparation pack.

An IM carries exact figures, so a buyer sees it only after signing an NDA. It still leaves out the
company's identity (names, brands, city, registry code) until the seller approves name disclosure;
those are masked in the adviser's notes and checked again after drafting. Every IM is a draft until
the adviser approves it, and states that it was prepared from seller-provided, unaudited data.

Claude writes the narrative when available; otherwise a template is used. The financial table and
the disclaimer are always generated here, never by the model.
"""

from sqlalchemy.orm import Session

from . import llm, reid
from .datacheck import FIN_FIELDS, years
from .models import InfoMemo, Target
from .teaser import facts

LANGUAGES = {"zh": "Simplified Chinese", "en": "English"}
IDENTITY_FIELDS = {"legal_name", "short_name", "owner_name", "brands", "city", "uscc", "registry_code", "contact"}

H = {  # headings
    "zh": {"overview": "一、公司概况", "business": "二、业务与客户", "operations": "三、经营与团队", "financials": "四、财务摘要（百万元）",
           "transaction": "五、交易安排", "disclaimer": "声明"},
    "en": {"overview": "1. Company overview", "business": "2. Business and customers", "operations": "3. Operations and team",
           "financials": "4. Financial summary (RMB m)", "transaction": "5. Proposed transaction", "disclaimer": "Disclaimer"},
}

NARRATIVE_SCHEMA = {
    "type": "object",
    "properties": {k: {"type": "array", "items": {"type": "string"}} for k in ("overview", "business", "operations")},
    "required": ["overview", "business", "operations"],
    "additionalProperties": False,
}

NARRATIVE_SYSTEM = (
    "You draft the narrative sections of an information memorandum for the sale of a Chinese private "
    "company, for buyers who have signed an NDA. Never name the company, its owner, brands or city: say "
    "'the Company' / '本公司'. Use only the facts given; do not invent customers, numbers or plans. "
    "2 to 4 short paragraphs per section."
)


def mask(target: Target, text: str) -> str:
    """Replace identifying terms in the adviser's notes before they go into an IM draft."""
    swaps = [(target.legal_name, "本公司"), (target.short_name, "本公司"), (target.owner_name, "创始人"),
             (target.uscc, "")] + [(b, "[品牌]") for b in target.brands or []]
    city = (target.city or "").removesuffix("市")
    if city:
        swaps.append((city, target.province))
    for term, repl in swaps:
        if term and len(term) >= 2:
            text = text.replace(term, repl)
    return text


def _fin_table(target: Target, language: str) -> dict:
    ys = years()
    rows = []
    for key, label in FIN_FIELDS.items():
        values = [(target.financials or {}).get(y, {}).get(key) for y in ys]
        if any(v not in (None, "") for v in values):
            name = label.split()[0] if language == "zh" else label.split(" ", 1)[1]
            rows.append([name] + ["—" if v in (None, "") else f"{float(v):g}" for v in values])
    return {"columns": [""] + ys, "rows": rows}


def _offline(target: Target, f: dict, notes: str, language: str) -> dict:
    d = target.disclosures or {}
    if language == "en":
        overview = [f"{target.code_name} is a {f['sector_en'].lower()} company in {target.province} province, "
                    f"operating for {f['years_operating']}, with {f['employees_band']} staff."]
        business = [notes] if notes else ["(Adviser to describe products, customers and market position.)"]
        if d.get("top_customer_share") not in (None, ""):
            business.append(f"The largest customer accounts for about {float(d['top_customer_share']):g}% of revenue.")
        operations = [{"owned": "The Company owns its land and plant.", "leased": "The Company leases its plant.",
                       "collective": "The plant is on collective land."}.get(d.get("land"), "Facilities: to be confirmed.")]
        transaction = [f"Proposed transaction: {f['deal_type']}.", f"Reason for sale: {f['sale_reason']}.",
                       f"Indicative valuation: {f['valuation_band']} RMB."]
    else:
        overview = [f"{target.code_name}为位于{target.province}的{f['sector_zh']}企业，经营{f['years_operating']}，员工{f['employees_band']}。"]
        business = [notes] if notes else ["（由顾问补充产品、客户及市场地位。）"]
        if d.get("top_customer_share") not in (None, ""):
            business.append(f"第一大客户约占营业收入的{float(d['top_customer_share']):g}%。")
        operations = [{"owned": "公司拥有自有土地和厂房。", "leased": "公司厂房为租赁。",
                       "collective": "公司厂房位于集体土地。"}.get(d.get("land"), "厂房情况：待确认。")]
        transaction = [f"交易方式：{f['deal_type']}。", f"出售原因：{f['sale_reason']}。", f"估值区间：{f['valuation_band']}。"]
    return {"overview": overview, "business": business, "operations": operations, "transaction": transaction}


def draft(session: Session, target: Target, language: str = "zh", use_llm: bool = True) -> InfoMemo:
    from . import fees

    if not fees.prep_pack_paid(target):
        raise ValueError("The info memo is part of the preparation pack.")
    if language not in LANGUAGES:
        raise ValueError("Unknown language")
    f = facts(target)
    notes = mask(target, target.description or "")
    parts = _offline(target, f, notes, language)
    generated_by = "offline"
    if use_llm:
        prompt = (f"Write in {LANGUAGES[language]}.\nFacts: {f}\nFinancials (RMB m): {target.financials}\n"
                  f"Checklist answers: {target.disclosures}\nAdviser notes (masked): {notes}")
        narrative = llm.structured(NARRATIVE_SYSTEM, prompt, NARRATIVE_SCHEMA)
        if narrative is not None:
            parts.update(narrative)
            generated_by = llm.label()

    h = H[language]
    firm = target.firm.name if target.firm else ""
    disclaimer = (f"本备忘录根据卖方提供、未经审计的资料编制{'，并由AI辅助起草' if generated_by != 'offline' else ''}，"
                  f"经{firm}审核。仅供已签署保密协议的买方评估之用，不构成任何保证或估值意见。"
                  if language == "zh" else
                  f"Prepared from unaudited information provided by the seller{', drafted with AI assistance' if generated_by != 'offline' else ''}, "
                  f"and reviewed by {firm}. For the evaluation of buyers who have signed an NDA only; no representation, "
                  "warranty or valuation opinion is given.")
    body = {
        "title": f"{target.code_name} · {'信息备忘录' if language == 'zh' else 'Information memorandum'}",
        "sections": [
            {"heading": h["overview"], "paragraphs": parts["overview"]},
            {"heading": h["business"], "paragraphs": parts["business"]},
            {"heading": h["operations"], "paragraphs": parts["operations"]},
            {"heading": h["financials"], "paragraphs": [], "table": _fin_table(target, language)},
            {"heading": h["transaction"], "paragraphs": parts["transaction"]},
            {"heading": h["disclaimer"], "paragraphs": [disclaimer]},
        ],
    }
    _, findings = reid.check(target, body)
    name_findings = [x for x in findings if x["field"] in IDENTITY_FIELDS]
    version = 1 + max((m.version for m in target.memos if m.language == language), default=0)
    memo = InfoMemo(target=target, version=version, language=language, body=body, name_findings=name_findings,
                    generated_by=generated_by)
    session.add(memo)
    session.flush()
    return memo


def approve(memo: InfoMemo) -> None:
    """The adviser approves; an IM that still names the company cannot be approved."""
    if memo.name_findings:
        raise ValueError("Remove the identifying details before approving this info memo.")
    memo.status = "approved"


def shared_memo(target: Target, language: str = "zh") -> InfoMemo | None:
    approved = [m for m in target.memos if m.status == "approved"]
    return next((m for m in approved if m.language == language), approved[0] if approved else None)
