# NOTE: This is a copy of api/app/lib/normalize.py
# Keep in sync when making changes to normalization logic.
# The canonical source is api/app/lib/normalize.py.

"""Pure text normalization utilities — no database dependencies.

Extracted from dedup.py to allow import by db_operations.py without
creating a circular dependency (dedup.py → db_operations.run_query).
"""
from __future__ import annotations

import functools
import re
import unicodedata

# Japanese honorific suffixes to strip from the end of names.
# Ordered longest-first so "先生" is tried before single-char suffixes.
_HONORIFIC_SUFFIXES = ["先生", "ちゃん", "さん", "くん", "様", "氏"]

# Regex range for fullwidth ASCII: U+FF01 (！) to U+FF5E (～)
_FULLWIDTH_OFFSET = 0xFF01 - 0x21  # = 65248

CONDITION_ALIASES: dict[str, list[str]] = {
    "自閉症スペクトラム障害": [
        "ASD",
        "自閉スペクトラム",
        "自閉スペクトラム症",
        "自閉症",
        "アスペルガー症候群",
        "アスペルガー",
        "広汎性発達障害",
        "PDD",
    ],
    "注意欠如多動症": ["ADHD", "注意欠陥多動性障害", "ADD", "注意欠如多動性障害"],
    "知的障害": ["知的発達症", "精神遅滞", "知的発達障害"],
    "てんかん": ["癲癇", "epilepsy"],
    "ダウン症候群": ["ダウン症", "21トリソミー", "Down症候群"],
    "脳性麻痺": ["CP", "脳性まひ"],
}

# Reverse lookup: alias.lower() → canonical name
_CONDITION_ALIAS_LOOKUP: dict[str, str] = {
    alias.lower(): canonical
    for canonical, aliases in CONDITION_ALIASES.items()
    for alias in aliases
}
# Also map canonical names to themselves (case-insensitive lookup)
_CONDITION_ALIAS_LOOKUP.update(
    {canonical.lower(): canonical for canonical in CONDITION_ALIASES}
)


@functools.lru_cache(maxsize=1)
def _get_kakasi():
    """Return a cached pykakasi Kakasi instance (initialized once per process)."""
    import pykakasi  # noqa: PLC0415 — lazy import to keep startup cost low

    kks = pykakasi.Kakasi()
    return kks


def name_to_kana(name: str | None) -> str:
    """Convert a Japanese name to hiragana reading using pykakasi.

    Katakana is also converted to hiragana. Alphabetic characters
    are lowercased. Text is normalize_text()'d first.
    Returns "" for None/empty.

    Examples:
        "田中太郎"  → "たなかたろう"
        "タナカ"    → "たなか"
        "ＡＢＣ"   → "abc"
    """
    text = normalize_text(name)
    if not text:
        return ""

    kks = _get_kakasi()
    return "".join(item["hira"] for item in kks.convert(text))


def normalize_text(text: str | None) -> str:
    """Normalize a text string for consistent storage and comparison.

    Steps applied in order:
    1. Return "" for None or empty input.
    2. Unicode NFC normalization (combines decomposed characters).
    3. Fullwidth ASCII (U+FF01–U+FF5E) → halfwidth (U+0021–U+007E).
    4. Collapse consecutive whitespace to a single ASCII space.
    5. Strip leading/trailing whitespace.
    """
    if not text:
        return ""

    # NFC normalization: NFD "か" + combining dakuten → NFC "が"
    text = unicodedata.normalize("NFC", text)

    # Fullwidth ASCII → halfwidth using character-by-character translation
    chars = []
    for ch in text:
        cp = ord(ch)
        if 0xFF01 <= cp <= 0xFF5E:
            chars.append(chr(cp - _FULLWIDTH_OFFSET))
        else:
            chars.append(ch)
    text = "".join(chars)

    # Collapse whitespace (including ideographic space U+3000) and strip
    text = re.sub(r"[\s\u3000]+", " ", text).strip()

    return text


def normalize_condition(name: str | None) -> str:
    """Normalize a medical condition name to its canonical Japanese term.

    Applies normalize_text() first, then resolves known aliases (case-insensitive)
    to their canonical names using CONDITION_ALIASES. Unknown names pass through
    unchanged after text normalization.

    Examples:
        "ASD"             → "自閉症スペクトラム障害"
        "asd"             → "自閉症スペクトラム障害"
        "自閉スペクトラム" → "自閉症スペクトラム障害"
        "ADHD"            → "注意欠如多動症"
        "希少疾患X"        → "希少疾患X"
    """
    text = normalize_text(name)
    if not text:
        return ""
    return _CONDITION_ALIAS_LOOKUP.get(text.lower(), text)


def normalize_name(name: str | None) -> str:
    """Normalize a Japanese personal name for MERGE key consistency.

    Applies normalize_text() first, then strips common honorific suffixes
    (さん, 様, くん, ちゃん, 氏, 先生) from the end of the string only.

    Examples:
        "田中さん"  → "田中"
        "田中様"    → "田中"
        "さんま"    → "さんま"   (さん is not at the very end)
        "ＡＢＣさん" → "ABC"
    """
    text = normalize_text(name)
    if not text:
        return ""

    for suffix in _HONORIFIC_SUFFIXES:
        if text.endswith(suffix):
            text = text[: -len(suffix)]
            break  # strip at most one suffix

    return text
