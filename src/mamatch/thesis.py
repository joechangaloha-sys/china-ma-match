"""Turn a buyer's own words about what they want to buy into structured criteria.

The buyer writes a few sentences; Claude (or keyword rules) proposes sectors, provinces, size,
earnings floor, funding range and exclusions; the buyer corrects and confirms them on the form.
Nothing proposed here is saved until the buyer submits it.
"""

import re

from . import llm
from .taxonomy import DEAL_TYPES, REGIONS, SECTOR_KEYWORDS, SECTORS

SCHEMA = {
    "type": "object",
    "properties": {
        "target_sectors": {"type": "array", "items": {"type": "string", "enum": list(SECTORS)}},
        "excluded_sectors": {"type": "array", "items": {"type": "string", "enum": list(SECTORS)}},
        "target_regions": {"type": "array", "items": {"type": "string", "enum": list(REGIONS)}},
        "target_deal_types": {"type": "array", "items": {"type": "string", "enum": list(DEAL_TYPES)}},
        "deal_size_min": {"type": ["number", "null"], "description": "RMB millions"},
        "deal_size_max": {"type": ["number", "null"], "description": "RMB millions"},
        "earnings_min": {"type": ["number", "null"], "description": "Minimum annual net profit, RMB millions"},
        "funding_min": {"type": ["number", "null"], "description": "RMB millions available for one deal"},
        "funding_max": {"type": ["number", "null"]},
        "experience": {"type": "string", "description": "One sentence on the buyer's relevant operating experience"},
    },
    "required": ["target_sectors", "excluded_sectors", "target_regions", "target_deal_types", "deal_size_min",
                 "deal_size_max", "earnings_min", "funding_min", "funding_max", "experience"],
    "additionalProperties": False,
}

SYSTEM = (
    "You structure a buyer's acquisition thesis for a Chinese small-business M&A service. Use only what "
    "the buyer wrote; leave a field empty or null when they did not say. Amounts in RMB millions "
    "(1亿 = 100, 1000万 = 10). Sector codes and provinces must come from the allowed lists."
)

_RANGE = re.compile(r"(\d+(?:\.\d+)?)\s*(?:-|–|~|～|到|至)\s*(\d+(?:\.\d+)?)\s*(亿|千万|百万|万|m|million)?", re.I)
_SCALE = {"亿": 100, "千万": 10, "百万": 1, "万": 0.01, "m": 1, "million": 1, None: 1}


def structure_offline(text: str) -> dict:
    out = {k: [] for k in ("target_sectors", "excluded_sectors", "target_regions", "target_deal_types")}
    out.update(deal_size_min=None, deal_size_max=None, earnings_min=None, funding_min=None, funding_max=None,
               experience="")
    for clause in re.split(r"[。；;，,\n]", text):
        exclude = any(w in clause for w in ("不考虑", "不要", "排除", "not ", "exclude"))
        for code, words in SECTOR_KEYWORDS.items():
            if any(w.lower() in clause.lower() for w in words):
                (out["excluded_sectors"] if exclude else out["target_sectors"]).append(code)
    out["target_sectors"] = sorted(set(out["target_sectors"]) - set(out["excluded_sectors"]))
    out["excluded_sectors"] = sorted(set(out["excluded_sectors"]))
    out["target_regions"] = [p for p in REGIONS if p in text]
    if m := _RANGE.search(text):
        unit = (m.group(3) or "").lower() or None
        scale = _SCALE.get(unit if unit in _SCALE else m.group(3), 1)
        out["deal_size_min"], out["deal_size_max"] = float(m.group(1)) * scale, float(m.group(2)) * scale
    if "控股" in text:
        out["target_deal_types"].append("majority")
    if "全资" in text or "100%" in text:
        out["target_deal_types"].append("full_sale")
    return out


def structure(text: str, use_llm: bool = True) -> tuple[dict, str]:
    if use_llm and text.strip():
        result = llm.structured(SYSTEM, f"<thesis>\n{text[:4000]}\n</thesis>", SCHEMA, effort="low")
        if result is not None:
            return result, llm.label()
    return structure_offline(text), "rules"
