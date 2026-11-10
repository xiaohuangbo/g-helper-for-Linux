from __future__ import annotations

import locale
import os

_lang = "zh"


def normalize(lang: str | None) -> str:
    if not lang or lang == "auto":
        lang = os.environ.get("LANG", "") or ""
        if not lang:
            try:
                lang = locale.getlocale()[0] or ""
            except Exception:
                lang = ""
    lang = lang.lower().replace("_", "-")
    return "zh" if lang.startswith("zh") else "en"


def set_language(lang: str | None) -> str:
    global _lang
    _lang = normalize(lang)
    return _lang


def language() -> str:
    return _lang


def t(zh: str, en: str) -> str:
    return zh if _lang == "zh" else en
