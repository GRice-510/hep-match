"""Shared data and TeX helpers. No credentials or personal reading data here."""
from __future__ import annotations
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'site/data/latest.json'
CACHE = ROOT / 'data/translations.json'
UTC = dt.timezone.utc
ID_RE = re.compile(r'(?:\d{4}\.\d{4,5}|[a-z-]+(?:\.[A-Z]{2})?/\d{7})(?:v\d+)?\Z')
# Capture only complete TeX math spans; escaped dollar signs are prose.
MATH_RE = re.compile(r'((?<!\\)\$\$[\s\S]*?(?<!\\)\$\$|(?<!\\)\$(?!\$)[^$\n]*?(?<!\\)\$|\\\([\s\S]*?\\\)|\\\[[\s\S]*?\\\])')


def load_json(path: Path, default=None):
    if not path.exists():
        return default
    with path.open(encoding='utf-8') as stream:
        return json.load(stream)


def atomic_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.tmp')
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    os.replace(temp, path)


def now_iso() -> str:
    return dt.datetime.now(UTC).isoformat(timespec='seconds').replace('+00:00', 'Z')


def parse_date(text: str) -> dt.datetime:
    result = dt.datetime.fromisoformat(text.replace('Z', '+00:00'))
    return result.replace(tzinfo=UTC) if result.tzinfo is None else result.astimezone(UTC)


def config() -> dict:
    cfg = load_json(ROOT / 'config.json')
    cats = cfg.get('categories', [])
    if not isinstance(cats, list) or not cats or len(cats) > 12:
        raise ValueError('categories must contain 1 to 12 arXiv categories')
    if any(not isinstance(c, str) or not re.fullmatch(r'[a-z-]+(?:\.[A-Z]{2})?', c) for c in cats):
        raise ValueError('Invalid arXiv category')
    if not 1 <= cfg.get('days', 0) <= 30 or not 1 <= cfg.get('max_results', 0) <= 5000:
        raise ValueError('days must be 1..30 and max_results 1..5000')
    tr = cfg.get('translation', {})
    if tr.get('engine') not in ('none', 'argos', 'deepl'):
        raise ValueError('Unsupported translation engine')
    if not set(tr.get('fields', [])).issubset({'title', 'abstract'}):
        raise ValueError('Unsupported translation fields')
    if not 0 <= tr.get('seconds', 0) <= 900 or not 0 <= tr.get('max_characters', 0) <= 500000:
        raise ValueError('Translation budget out of range')
    return cfg


def cache_key(engine: str, text: str) -> str:
    # Bump the scheme when preprocessing changes; source edits invalidate old translations.
    return engine + ':math-v1:' + hashlib.sha256(text.encode('utf-8')).hexdigest()


def translate_math_safe(text: str, translate: Callable[[str], str]) -> str:
    """Never send TeX math to a translation engine, including browser-side equivalents.

    Prose between math spans is translated separately. This trades some fluency
    for exact preservation of the author's formulas. Empty/failed translations
    raise rather than poisoning the translation cache.
    """
    result = []
    for index, part in enumerate(MATH_RE.split(text)):
        if index % 2 or not part.strip():
            result.append(part)
            continue
        before = part[:len(part) - len(part.lstrip())]
        after = part[len(part.rstrip()):]
        translated = translate(part.strip())
        if not isinstance(translated, str) or not translated.strip():
            raise ValueError('Translation returned no text')
        if len(translated) > max(200, len(part) * 8):
            raise ValueError('Translation output is unexpectedly long')
        result.append(before + translated.strip() + after)
    return ''.join(result)
