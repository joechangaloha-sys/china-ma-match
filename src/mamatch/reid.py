"""Re-identification check for anonymised teasers.

Chinese business-registry data (Qichacha, Tianyancha) makes small companies easy to identify
from a few facts, so the check is stricter than a Japanese ノンネーム review: any name, brand,
city below province level, exact figure or registry code in the teaser is flagged.
"""

import re
from dataclasses import asdict, dataclass

from .models import Target


@dataclass
class Finding:
    field: str
    matched: str
    severity: float  # 0..1 contribution to the risk score
    message: str


_USCC = re.compile(r"\b[0-9A-HJ-NPQRTUWXY]{2}\d{6}[0-9A-HJ-NPQRTUWXY]{10}\b")
_PHONE = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)|0\d{2,3}-?\d{7,8}")
_CONTACT = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+|https?://\S+|www\.\S+")
# Figures with 3+ significant digits (e.g. "1.27亿", "8,350万", "326人") are too precise to share.
_EXACT_NUMBER = re.compile(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+\.\d{2,}|\d{3,}(?=\s*(?:万|亿|人|名|平方|㎡|吨|台|件))")
_YEAR = re.compile(r"(?:19|20)\d{2}\s*年")
_RANGE = re.compile(r"\d+(?:\.\d+)?\s*[–~～-]\s*\d+(?:\.\d+)?|\d+(?:\.\d+)?(?=\D{0,4}以上)")


def _texts(body: dict) -> str:
    parts: list[str] = []

    def walk(v):
        if isinstance(v, str):
            parts.append(v)
        elif isinstance(v, dict):
            for x in v.values():
                walk(x)
        elif isinstance(v, list):
            for x in v:
                walk(x)

    walk(body)
    return "\n".join(parts)


def check(target: Target, body: dict) -> tuple[float, list[dict]]:
    text = _texts(body)
    findings: list[Finding] = []

    def flag_term(field: str, term: str, severity: float, message: str):
        if term and len(term) >= 2 and term in text:
            findings.append(Finding(field, term, severity, message))

    flag_term("legal_name", target.legal_name, 1.0, "Company legal name appears in the teaser.")
    flag_term("short_name", target.short_name, 0.9, "Company short name appears in the teaser.")
    flag_term("owner_name", target.owner_name, 0.9, "Owner's name appears in the teaser.")
    for brand in target.brands or []:
        flag_term("brands", brand, 0.8, f"Brand or product name '{brand}' identifies the company.")
    city = (target.city or "").removesuffix("市")
    flag_term("city", city, 0.4, "City is more precise than province; use the province or region.")
    if target.uscc:
        flag_term("uscc", target.uscc, 1.0, "Unified social credit code appears in the teaser.")

    for m in _USCC.finditer(text):
        findings.append(Finding("registry_code", m.group(), 1.0, "Looks like a unified social credit code."))
    for m in _PHONE.finditer(text):
        findings.append(Finding("contact", m.group(), 0.8, "Phone number in the teaser."))
    for m in _CONTACT.finditer(text):
        findings.append(Finding("contact", m.group(), 0.8, "Email or website in the teaser."))
    banded = _RANGE.sub("", text)  # ranges such as "100–200百万元" or "1000人以上" are already safe
    for m in _EXACT_NUMBER.finditer(banded):
        findings.append(Finding("exact_figure", m.group(), 0.25, "Exact figure; use a range such as '1–2亿元'."))
    for m in _YEAR.finditer(banded):
        findings.append(Finding("exact_year", m.group(), 0.2, "Exact founding or event year; use '20年以上' etc."))

    # Combine as independent risks: 1 - Π(1 - s).
    survive = 1.0
    for f in findings:
        survive *= 1 - f.severity
    score = round(1 - survive, 3)
    return score, [asdict(f) for f in findings]


def risk_label(score: float) -> str:
    if score >= 0.6:
        return "high"
    if score >= 0.25:
        return "medium"
    return "low"
