"""Check the data a seller submits before anything is shown to buyers.

The rules target what usually breaks small Chinese private-company deals: books that do not match
invoiced revenue (tax exposure on transfer), staff without social insurance, permits or land tied
to the founder, customer concentration, related-party revenue, owner guarantees. Each finding
carries a question the adviser can put to the seller.

Claude then reviews the same data for anything the rules missed; without Claude the rule-based
findings stand alone.
"""

from datetime import date

from sqlalchemy.orm import Session

from . import llm
from .models import DataCheck, Target

FIN_FIELDS = {  # per year, RMB m
    "revenue": "营业收入 Revenue",
    "gross_profit": "毛利 Gross profit",
    "net_profit": "净利润 Net profit",
    "total_assets": "总资产 Total assets",
    "total_liabilities": "总负债 Total liabilities",
    "cash": "货币资金 Cash",
}

DISCLOSURES = {  # field: (label, type)
    "invoiced_revenue": ("最近一年开票收入（百万元）Invoiced revenue, latest year (RMB m)", "number"),
    "top_customer_share": ("第一大客户收入占比（%）Largest customer share of revenue (%)", "number"),
    "related_party_share": ("关联交易收入占比（%）Related-party share of revenue (%)", "number"),
    "employees_insured": ("缴纳社保人数 Employees with social insurance", "number"),
    "permits_personal": ("关键资质/许可是否登记在个人名下 Key permits held by the owner personally", "bool"),
    "land": ("土地/厂房 Land and plant", "choice:owned=自有 Owned,leased=租赁 Leased,collective=集体土地 Collective land"),
    "lease_years_left": ("租约剩余年限 Years left on lease", "number"),
    "owner_guarantees": ("实控人是否为公司债务提供个人担保 Owner guarantees company debt", "bool"),
    "pending_disputes": ("是否有未决诉讼或纠纷 Pending litigation or disputes", "bool"),
    "notes": ("其他说明 Other notes", "text"),
}

SEVERITY = {"high": "高 High", "medium": "中 Medium", "low": "低 Low"}


def years() -> list[str]:
    """The last three full financial years."""
    y = date.today().year
    return [str(y - 3), str(y - 2), str(y - 1)]


def _f(target: Target, year: str, key: str) -> float | None:
    v = (target.financials or {}).get(year, {}).get(key)
    return float(v) if v not in (None, "") else None


def _d(target: Target, key: str):
    v = (target.disclosures or {}).get(key)
    return None if v in (None, "") else v


def _finding(code: str, severity: str, category: str, message: str, question: str) -> dict:
    return {"code": code, "severity": severity, "category": category, "message": message, "question": question}


def rules(target: Target) -> list[dict]:
    out: list[dict] = []
    ys = years()
    latest = ys[-1]

    missing = [f"{y} {FIN_FIELDS[k].split()[0]}" for y in ys for k in ("revenue", "net_profit")
               if _f(target, y, k) is None]
    if missing:
        out.append(_finding("missing_financials", "high" if len(missing) > 2 else "medium", "completeness",
                            "财务数据不完整 Financial data incomplete: " + "、".join(missing),
                            "请补充最近三年的收入和净利润（审计报告或纳税申报表）。Please provide three years of revenue and net profit."))
    unanswered = [DISCLOSURES[k][0].split()[0] for k in ("invoiced_revenue", "top_customer_share", "employees_insured",
                                                         "permits_personal", "land", "owner_guarantees")
                  if _d(target, k) is None]
    if unanswered:
        out.append(_finding("missing_disclosures", "medium", "completeness",
                            "尽调问卷未答完 Checklist not complete: " + "、".join(unanswered),
                            "请回答尽调问卷中的剩余问题。Please answer the remaining checklist questions."))

    rev = _f(target, latest, "revenue")
    if rev is not None and target.revenue is not None and abs(rev - target.revenue) > 0.05 * max(rev, target.revenue):
        out.append(_finding("intake_mismatch", "medium", "consistency",
                            f"{latest}年收入 {rev:g} 与访谈时的 {target.revenue:g}（百万元）不一致 Revenue differs from the intake figure.",
                            "以哪一个数字为准？差异原因是什么？Which figure is right, and why do they differ?"))

    inv = _d(target, "invoiced_revenue")
    if rev and inv is not None and float(inv) < 0.9 * rev:
        gap = 1 - float(inv) / rev
        out.append(_finding("invoice_gap", "high", "tax",
                            f"开票收入比账面收入低 {gap:.0%}：可能存在未开票收入，股权转让时有补税风险 Invoiced revenue is {gap:.0%} below book revenue: possible unreported income and back-tax exposure on transfer.",
                            "未开票部分的收入如何入账、是否申报纳税？Is the uninvoiced revenue booked and taxed?"))

    for prev, cur in zip(ys, ys[1:]):
        a, b = _f(target, prev, "revenue"), _f(target, cur, "revenue")
        if a and b and abs(b - a) / a > 0.5:
            out.append(_finding(f"revenue_swing_{cur}", "medium", "consistency",
                                f"{prev}→{cur} 收入变动 {(b - a) / a:+.0%} Revenue moved {(b - a) / a:+.0%} in one year.",
                                "变动的原因是什么，是否可持续？What drove the change, and will it last?"))

    np_ = _f(target, latest, "net_profit")
    if rev and np_ is not None:
        margin = np_ / rev
        if margin < 0:
            out.append(_finding("loss", "high", "profitability", f"{latest}年亏损 Net loss in {latest}.",
                                "亏损原因及扭亏计划？Why the loss, and what is the plan?"))
        elif margin > 0.35:
            out.append(_finding("high_margin", "medium", "consistency",
                                f"净利率 {margin:.0%} 明显高于制造业常见水平 Net margin {margin:.0%} is unusually high.",
                                "是否有一次性收益或未计费用（如股东未领工资）？Any one-off gains or unbooked costs, e.g. unpaid owner salary?"))
    gp = _f(target, latest, "gross_profit")
    if rev and gp is not None and np_ is not None and np_ > gp:
        out.append(_finding("np_above_gp", "high", "consistency", "净利润高于毛利 Net profit above gross profit.",
                            "请核对是否有营业外收入或数据录入错误。Check for non-operating income or an entry error."))

    assets, liab = _f(target, latest, "total_assets"), _f(target, latest, "total_liabilities")
    if assets and liab is not None and liab / assets > 0.7:
        out.append(_finding("leverage", "medium", "balance_sheet", f"资产负债率 {liab / assets:.0%} Liabilities are {liab / assets:.0%} of assets.",
                            "主要负债构成及到期安排？What are the main debts and when are they due?"))

    if target.asking_value and np_ and np_ > 0:
        multiple = target.asking_value / np_
        if multiple > 15 or multiple < 3:
            out.append(_finding("valuation_multiple", "low", "valuation",
                                f"期望估值约为净利润的 {multiple:.1f} 倍 Asking value is {multiple:.1f}x net profit.",
                                "估值依据是什么？买方通常参考 5–10 倍。What supports the price? Buyers often look at 5–10x."))

    insured = _d(target, "employees_insured")
    if insured is not None and target.employees and float(insured) < 0.8 * target.employees:
        out.append(_finding("social_insurance", "high", "labour",
                            f"仅 {int(float(insured))}/{target.employees} 名员工缴纳社保：补缴风险 Only {int(float(insured))} of {target.employees} staff have social insurance: back-payment exposure.",
                            "未缴社保员工的情况及补缴估算？Who is not covered, and what would back-payment cost?"))

    top = _d(target, "top_customer_share")
    if top is not None and float(top) > 40:
        out.append(_finding("customer_concentration", "medium", "commercial",
                            f"第一大客户占收入 {float(top):g}% Largest customer is {float(top):g}% of revenue.",
                            "合同期限及控制权变更条款？Contract term and change-of-control clauses?"))
    rp = _d(target, "related_party_share")
    if rp is not None and float(rp) > 20:
        out.append(_finding("related_party", "medium", "commercial",
                            f"关联交易占收入 {float(rp):g}% Related parties are {float(rp):g}% of revenue.",
                            "交割后这些交易是否继续、价格是否公允？Will these continue after closing, at market prices?"))

    if _d(target, "permits_personal") is True:
        out.append(_finding("permits_personal", "high", "legal",
                            "关键资质登记在实控人个人名下，股权转让后可能失效 Key permits are in the owner's name and may not transfer with the shares.",
                            "能否在交割前转入公司名下？Can they be moved into the company before closing?"))
    land = _d(target, "land")
    if land == "collective":
        out.append(_finding("collective_land", "high", "legal", "使用集体土地 Plant is on collective land.",
                            "是否有合法的租赁或流转手续？Is there a valid lease or transfer?"))
    elif land == "leased":
        left = _d(target, "lease_years_left")
        if left is not None and float(left) < 5:
            out.append(_finding("short_lease", "medium", "legal", f"厂房租约剩余 {float(left):g} 年 Lease has {float(left):g} years left.",
                                "能否续租？出租方是谁？Can it be renewed, and who is the landlord?"))
    if _d(target, "owner_guarantees") is True:
        out.append(_finding("owner_guarantees", "medium", "finance",
                            "实控人为公司债务提供个人担保 Owner personally guarantees company debt.",
                            "交割时如何解除担保？How will the guarantees be released at closing?"))
    if _d(target, "pending_disputes") is True:
        out.append(_finding("disputes", "medium", "legal", "存在未决诉讼或纠纷 Pending litigation or disputes.",
                            "请说明涉案金额和进展。Amounts involved and status?"))

    order = {"high": 0, "medium": 1, "low": 2}
    return sorted(out, key=lambda f: order[f["severity"]])


REVIEW_SCHEMA = {
    "type": "object",
    "properties": {"findings": {"type": "array", "items": {
        "type": "object",
        "properties": {
            "severity": {"type": "string", "enum": ["high", "medium", "low"]},
            "category": {"type": "string"},
            "message": {"type": "string", "description": "Chinese, then a short English gloss."},
            "question": {"type": "string", "description": "Question for the seller, Chinese then English."},
        },
        "required": ["severity", "category", "message", "question"],
        "additionalProperties": False,
    }}},
    "required": ["findings"],
    "additionalProperties": False,
}

REVIEW_SYSTEM = (
    "You review data a Chinese private-company seller submitted before a sale. Find inconsistencies, "
    "gaps and deal risks a buyer's due diligence would raise (tax, social insurance, permits, land, "
    "customers, related parties, guarantees, quality of earnings). Do not repeat findings already "
    "listed. Be specific and brief; at most 6 findings."
)


def run(session: Session, target: Target, use_llm: bool = True) -> DataCheck:
    from . import fees

    if not fees.prep_pack_paid(target):
        raise ValueError("The data check is part of the preparation pack.")
    findings = rules(target)
    generated_by = "rules"
    if use_llm:
        prompt = (f"Sector: {target.sector}; province: {target.province}; employees: {target.employees}\n"
                  f"Financials (RMB m): {target.financials}\nChecklist: {target.disclosures}\n"
                  f"Adviser notes: {target.description}\nAlready found: {[f['message'] for f in findings]}")
        extra = llm.structured(REVIEW_SYSTEM, prompt, REVIEW_SCHEMA)
        if extra is not None:
            findings += [{**f, "code": "ai_review"} for f in extra["findings"]]
            generated_by = f"rules+{llm.label()}"
    dc = DataCheck(target=target, findings=findings, generated_by=generated_by)
    session.add(dc)
    session.flush()
    return dc
