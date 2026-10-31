"""Chinese / English display.

Labels across the app are written bilingually, Chinese first ("出售项目 Opportunities",
"100%股权转让 / Full sale"). `tr` picks one side for the reader's language; `val` turns
banded figures ("30–50百万元", "20年以上") into the reader's language. Internal and public pages both use the selected edition; bilingual labels must be localised explicitly.
"""

import re

LANGS = {"zh": "中文", "en": "English"}
_CJK = re.compile(r"[　-〿一-鿿＀-￯]")


def tr(text, lang: str) -> str:
    """Pick the Chinese or English half of a bilingual label; one-language text passes through."""
    if not text or not isinstance(text, str):
        return text
    cjk = [m.end() for m in _CJK.finditer(text)]
    if not cjk:
        return text
    cut = cjk[-1]
    zh, en = text[:cut], text[cut:].strip(" /·:：-")
    if not re.search(r"[A-Za-z]", en):  # Chinese only (any trailing figures belong to it)
        return text
    if lang == "en":
        return en
    return zh.rstrip(" /·")


def val(text, lang: str) -> str:
    """Localise a band or figure label produced by teaser.band and friends."""
    if not text or not isinstance(text, str) or lang != "en":
        return tr(text, lang) if isinstance(text, str) else text
    t = text.strip()
    from .taxonomy import REGION_EN

    if t in REGION_EN:
        return REGION_EN[t]
    if t == "未披露":
        return "Not disclosed"
    for unit, fmt in (("百万元以上", "RMB {}m+"), ("百万元", "RMB {}m"), ("人以上", "{}+ staff"), ("人", "{} staff"),
                      ("年以上", "{}+ years"), ("年", "{} years")):
        if t.endswith(unit) and not _CJK.search(t[: -len(unit)]):
            return fmt.format(t[: -len(unit)])
    if t.startswith("51%以上"):
        return "51%+ (majority)"
    return tr(t, lang)


# Match reasons are stored as the English sentences matching.py writes; these patterns give each one
# in the reader's language, with sector, region and family names localised.
FAMILIES = {"mobility": ("汽车与交通", "mobility"), "equipment": ("设备与电子", "equipment"),
            "materials": ("材料", "materials"), "packaging": ("包装", "packaging"), "consumer": ("消费品", "consumer"),
            "healthcare": ("医疗健康", "healthcare"), "tech": ("科技", "technology"), "services": ("服务", "services")}
_REASONS = [
    (r"Stated interest in (?P<sector>.+)", "明确希望收购{sector}企业", "Stated interest in {sector}"),
    (r"Same business as target \((?P<sector>.+)\): horizontal consolidation", "与本公司同业（{sector}），可横向整合",
     "Same business ({sector}): horizontal consolidation"),
    (r"Adjacent sector in the same family \((?P<family>.+)\)", "相邻行业（同属{family}领域）",
     "Adjacent sector in the same field ({family})"),
    (r"No sector fit", "行业不匹配", "No sector fit"),
    (r"Buyer excludes this sector", "买方不考虑该行业", "Buyer excludes this sector"),
    (r"Deal type not wanted", "买方不考虑这种交易方式", "Deal type not wanted"),
    (r"Funding \(up to RMB (?P<amount>[\d.]+)m\) below the asking price", "资金（最多{amount}百万元）低于期望价格",
     "Funding (up to RMB {amount}m) below the asking price"),
    (r"Earnings below the buyer's minimum", "利润低于买方的最低要求", "Earnings below the buyer's minimum"),
    (r"No regional restriction stated", "买方不限地区", "No regional restriction"),
    (r"Has bought or targets companies in (?P<region>.+)", "曾在{region}收购或以{region}企业为目标",
     "Has bought, or targets companies, in {region}"),
    (r"Active in the same region \((?P<region>.+)\)", "在同一区域（{region}）活跃", "Active in the same region ({region})"),
    (r"Headquartered in (?P<region>.+)", "总部位于{region}", "Headquartered in {region}"),
    (r"Deal size fits stated range(?: \(RMB (?P<lo>[\d.]+)–(?P<hi>[\d.]+)m\))?", "交易规模符合买方的目标范围",
     "Deal size fits the buyer's stated range"),
    (r"Deal size outside stated range", "交易规模不在买方的目标范围内", "Deal size outside the buyer's stated range"),
    (r"Acquisition announcement in the last 6 months \((?P<date>[\d-]+)\)", "近6个月内有收购公告（{date}）",
     "Acquisition announcement in the last 6 months ({date})"),
    (r"Acquisition announcement within 2 years \((?P<date>[\d-]+)\)", "近2年内有收购公告（{date}）",
     "Acquisition announcement within 2 years ({date})"),
    (r"Public inquiry", "通过公开项目咨询", "Inquiry from a public listing"),
]


def reason(text: str, lang: str) -> str:
    """One match reason in the reader's language; unknown text is shown as it is."""
    for pattern, zh, en in _REASONS:
        m = re.fullmatch(pattern, text.strip())
        if not m:
            continue
        parts = {k: v for k, v in m.groupdict().items() if v is not None}
        if "sector" in parts:
            parts["sector"] = tr(parts["sector"], lang)
        if "region" in parts:
            parts["region"] = val(parts["region"], lang) if lang == "en" else parts["region"]
        if "family" in parts:
            parts["family"] = FAMILIES.get(parts["family"], (parts["family"], parts["family"]))[0 if lang == "zh" else 1]
        return (zh if lang == "zh" else en).format(**parts)
    return tr(text, lang)
