#!/usr/bin/env python3
"""Fetch a rolling arXiv digest, keeping previous data if a request fails."""
from __future__ import annotations
import datetime as dt
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from common import DATA, UTC, ID_RE, atomic_json, config, load_json, now_iso, parse_date

NS = {'a': 'http://www.w3.org/2005/Atom', 'ar': 'http://arxiv.org/schemas/atom',
      'o': 'http://a9.com/-/spec/opensearch/1.1/'}
API = 'https://export.arxiv.org/api/query'
MAX_BYTES = 12 * 1024 * 1024


def clean(text: str | None) -> str:
    return re.sub(r'\s+', ' ', text or '').strip()


def parse_feed(raw: bytes) -> tuple[list[dict], int]:
    if len(raw) > MAX_BYTES:
        raise ValueError('Oversized arXiv feed')
    root = ET.fromstring(raw)
    if root.tag != '{' + NS['a'] + '}feed':
        raise ValueError('Response is not an Atom feed')
    papers = []
    for entry in root.findall('a:entry', NS):
        raw_id = (entry.findtext('a:id', '', NS)).rstrip('/').split('/abs/')[-1]
        if not ID_RE.fullmatch(raw_id):
            raise ValueError('Invalid arXiv entry, possibly an API error')
        match = re.search(r'v(\d+)$', raw_id)
        version = int(match.group(1)) if match else 1
        ident = re.sub(r'v\d+$', '', raw_id)
        cats = list(dict.fromkeys(c.get('term', '') for c in entry.findall('a:category', NS)))
        primary = entry.find('ar:primary_category', NS)
        primary_cat = primary.get('term', '') if primary is not None else (cats[0] if cats else '')
        published = entry.findtext('a:published', '', NS)
        updated = entry.findtext('a:updated', published, NS)
        parse_date(published)
        parse_date(updated)
        title = clean(entry.findtext('a:title', '', NS))
        abstract = clean(entry.findtext('a:summary', '', NS))
        if not title or not abstract:
            raise ValueError('Incomplete arXiv metadata')
        papers.append({'id': ident, 'version': version, 'title': title, 'abstract': abstract,
                       'authors': [clean(a.findtext('a:name', '', NS)) for a in entry.findall('a:author', NS)],
                       'categories': cats, 'primary': primary_cat, 'published': published,
                       'updated': updated, 'comment': clean(entry.findtext('ar:comment', '', NS)),
                       'abs_url': 'https://arxiv.org/abs/' + ident,
                       'pdf_url': 'https://arxiv.org/pdf/' + ident})
    total = int(root.findtext('o:totalResults', str(len(papers)), NS))
    return papers, total


class ArxivClient:
    def __init__(self):
        self.last_request = 0.0
        contact = os.environ.get('ARXIV_CONTACT', '').replace('\n', '').replace('\r', '')
        self.agent = 'HEP-Match/1.0 (+https://github.com/GRice-510/hep-match)'
        if contact:
            self.agent += ' (mailto:' + contact + ')'

    def get(self, query: dict) -> tuple[list[dict], int]:
        url = API + '?' + urllib.parse.urlencode(query)
        for attempt in range(5):
            time.sleep(max(0, 3.2 - (time.monotonic() - self.last_request)))
            self.last_request = time.monotonic()
            try:
                request = urllib.request.Request(url, headers={'User-Agent': self.agent})
                with urllib.request.urlopen(request, timeout=50) as response:
                    raw = response.read(MAX_BYTES + 1)
                rows, total = parse_feed(raw)
                if not rows and total > query['start']:
                    raise ValueError('Unexpected empty page')
                return rows, total
            except (urllib.error.URLError, TimeoutError, ValueError, ET.ParseError) as exc:
                print(f'arXiv request attempt {attempt + 1}/5 failed: '
                      f'{type(exc).__name__}: {exc}', file=sys.stderr)
                if attempt == 4:
                    raise RuntimeError('arXiv fetch failed; previous data has not been changed') from exc
                # Give rate limits and temporary service failures time to recover.
                delay = 30 * (2 ** attempt)
                if isinstance(exc, urllib.error.HTTPError):
                    retry_after = exc.headers.get('Retry-After', '') if exc.headers else ''
                    if retry_after.isdigit():
                        delay = max(delay, int(retry_after))
                time.sleep(min(delay, 600))
        raise RuntimeError('Unreachable')


def collect(client, categories: list[str], since: dt.datetime, limit: int) -> tuple[list[dict], bool]:
    query = '(' + ' OR '.join('cat:' + c for c in categories) + ')'
    found: dict[str, dict] = {}
    start = 0
    truncated = False
    while start < limit:
        rows, total = client.get({'search_query': query, 'sortBy': 'submittedDate',
                                  'sortOrder': 'descending', 'start': start,
                                  'max_results': min(100, limit - start)})
        if not rows:
            break
        reached_old = False
        for paper in rows:
            if parse_date(paper['published']) < since:
                reached_old = True
                continue
            previous = found.get(paper['id'])
            if previous is None or paper['version'] > previous['version']:
                found[paper['id']] = paper
        start += len(rows)
        if reached_old or start >= total:
            break
        if start >= limit:
            truncated = True
    return sorted(found.values(), key=lambda p: (p['published'], p['id']), reverse=True), truncated


def retain_translations(papers: list[dict], previous: list[dict]) -> None:
    old = {p['id']: p for p in previous}
    for paper in papers:
        item = old.get(paper['id'], {})
        for field in ('title', 'abstract'):
            if item.get(field) == paper[field] and item.get(field + '_ja'):
                paper[field + '_ja'] = item[field + '_ja']
                paper[field + '_translator'] = item.get(field + '_translator', 'unknown')


def main() -> None:
    cfg = config()
    since = dt.datetime.now(UTC) - dt.timedelta(days=cfg['days'])
    papers, truncated = collect(ArxivClient(), cfg['categories'], since, cfg['max_results'])
    if not papers:
        raise RuntimeError('No recent papers returned. Keeping the previous digest; check arXiv and the date window.')
    old = load_json(DATA, {'papers': []})
    retain_translations(papers, old.get('papers', []))
    doc = {'schema_version': 1, 'generated_at': now_iso(), 'since': since.isoformat(),
           'categories': cfg['categories'], 'truncated': truncated,
           'translation': {'engine': cfg['translation']['engine'], 'status': 'pending'},
           'papers': papers}
    atomic_json(DATA, doc)
    print(f'Fetched {len(papers)} papers; truncated={truncated}')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        sys.exit(1)
