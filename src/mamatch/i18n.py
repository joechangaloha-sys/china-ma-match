"""Chinese / English display.

Labels across the app are written bilingually, Chinese first ("出售项目 Opportunities",
"100%股权转让 / Full sale"). `tr` picks one side for the reader's language; `val` turns
banded figures ("30–50百万元", "20年以上") into the reader's language. Internal pages stay
bilingual on purpose: deal managers work in both.
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
