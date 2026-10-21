#!/usr/bin/env python3
"""Optional, bounded pretranslation. Default engine is local Argos, not a paid API."""
from __future__ import annotations
import json
import os
import sys
import time
import urllib.error
import urllib.request
from common import CACHE, DATA, atomic_json, cache_key, config, load_json, now_iso, translate_math_safe


class BudgetExceeded(RuntimeError):
    pass


class Budget:
    def __init__(self, seconds: float, characters: int):
        self.deadline = time.monotonic() + seconds
        self.remaining = characters
        self.used = 0

    def reserve(self, text: str) -> None:
        if time.monotonic() >= self.deadline or len(text) > self.remaining:
            raise BudgetExceeded('Translation budget reached')
        self.remaining -= len(text)
        self.used += len(text)


def argos_translator():
    import argostranslate.package as package
    import argostranslate.translate as translate
    installed = package.get_installed_packages()
    if not any(p.from_code == 'en' and p.to_code == 'ja' for p in installed):
        package.update_package_index()
        candidates = [p for p in package.get_available_packages() if p.from_code == 'en' and p.to_code == 'ja']
        if not candidates:
            raise RuntimeError('No English-to-Japanese Argos package available')
        candidate = sorted(candidates, key=lambda p: tuple(int(x) for x in p.package_version.split('.')), reverse=True)[0]
        package.install_from_path(candidate.download())
    return lambda text: translate.translate(text, 'en', 'ja')


class DeepLTranslator:
    def __init__(self):
        self.key = os.environ.get('DEEPL_API_KEY', '')
        if not self.key:
            raise RuntimeError('DEEPL_API_KEY is not configured; use Argos or none')
        self.base = os.environ.get('DEEPL_API_BASE', 'https://api-free.deepl.com').rstrip('/')
        if self.base not in ('https://api-free.deepl.com', 'https://api.deepl.com'):
            raise RuntimeError('Unapproved DeepL host')
        if self.base == 'https://api.deepl.com' and os.environ.get('ALLOW_PAID_DEEPL') != 'true':
            raise RuntimeError('Paid-capable DeepL endpoint is disabled. Explicit opt-in is required.')
        usage = self.request('/v2/usage')
        limit, count = usage.get('character_limit'), usage.get('character_count')
        if not isinstance(limit, int) or not isinstance(count, int):
            raise RuntimeError('Cannot verify DeepL usage; refusing translation')
        self.remaining = max(0, limit - count)

    def request(self, path: str, payload=None):
        body = json.dumps(payload).encode() if payload is not None else None
        request = urllib.request.Request(self.base + path, data=body, headers={
            'Authorization': 'DeepL-Auth-Key ' + self.key, 'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(request, timeout=40) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            # Do not print upstream bodies or authentication headers into public logs.
            raise RuntimeError(f'DeepL HTTP {exc.code}; translation stopped') from None
        except Exception:
            raise RuntimeError('DeepL unavailable; translation stopped') from None

    def __call__(self, text: str) -> str:
        if len(text) > self.remaining:
            raise BudgetExceeded('DeepL allowance exhausted; no automatic upgrade')
        self.remaining -= len(text)
        result = self.request('/v2/translate', {'text': [text], 'source_lang': 'EN', 'target_lang': 'JA'})
        return result['translations'][0]['text']


def apply_translations(doc, cached: dict, engine: str, fields: list[str], translate, budget: Budget, checkpoint=lambda: None):
    allowed_keys = set()
    for paper in doc['papers']:
        for field in fields:
            key = cache_key(engine, paper[field])
            allowed_keys.add(key)
            if cached.get(key):
                paper[field + '_ja'] = cached[key]
                paper[field + '_translator'] = engine
    completed = 0
    stopped = False
    # All titles first. An initial abstract backlog must not delay new titles.
    for field in ('title', 'abstract'):
        if field not in fields:
            continue
        for paper in doc['papers']:
            key = cache_key(engine, paper[field])
            if key in cached:
                continue
            try:
                def bounded(text):
                    budget.reserve(text)
                    return translate(text)
                value = translate_math_safe(paper[field], bounded)
            except BudgetExceeded:
                stopped = True
                break
            except Exception:
                # Stop on engine/network errors, preserving successful fields and old data.
                # Logs intentionally omit text and credentials.
                doc['translation']['status'] = 'engine_error'
                checkpoint()
                raise
            cached[key] = value
            paper[field + '_ja'] = value
            paper[field + '_translator'] = engine
            completed += 1
            checkpoint()
        if stopped:
            break
    # Keep only the current rolling window; saved reading lists live on the device.
    for key in list(cached):
        if key not in allowed_keys:
            del cached[key]
    doc['translation'].update({'engine': engine, 'status': 'partial' if stopped else 'complete',
        'processed_fields': completed, 'characters_this_run': budget.used, 'updated_at': now_iso(),
        'titles': sum(bool(p.get('title_ja')) for p in doc['papers']),
        'abstracts': sum(bool(p.get('abstract_ja')) for p in doc['papers'])})
    checkpoint()


def main():
    settings = config()['translation']
    engine = settings['engine']
    doc = load_json(DATA)
    if not doc or not doc.get('papers'):
        raise RuntimeError('Fetch papers before translating')
    doc['translation'] = {'engine': engine, 'status': 'initializing'}
    if engine == 'none':
        doc['translation']['status'] = 'disabled'
        atomic_json(DATA, doc)
        return
    cached = load_json(CACHE, {})
    def checkpoint():
        atomic_json(CACHE, cached)
        atomic_json(DATA, doc)
    checkpoint()
    try:
        translator = argos_translator() if engine == 'argos' else DeepLTranslator()
        budget = Budget(settings['seconds'], settings['max_characters'])
        apply_translations(doc, cached, engine, settings['fields'], translator, budget, checkpoint)
    except Exception:
        doc['translation']['status'] = 'engine_error'
        checkpoint()
        raise
    print(json.dumps(doc['translation'], ensure_ascii=False))


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'Translation incomplete ({type(exc).__name__}). Original papers remain available.', file=sys.stderr)
        sys.exit(1)
