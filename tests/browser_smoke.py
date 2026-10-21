"""End-to-end tests with deterministic fixture papers, never published as new papers."""
from __future__ import annotations
import functools
import http.server
import json
from pathlib import Path
import threading
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
rows = [{'id': f'2610.{10000+i}', 'version': 1, 'title': f'Test paper {i}: $m^2$',
         'abstract': ('A controlled browser test about extra dimensions. ' * 25),
         'title_ja': f'検証用の論文 {i}：$m^2$', 'title_translator': 'argos',
         'authors': ['A. Author'], 'primary': 'hep-th', 'categories': ['hep-th'],
         'published': '2026-10-20T00:00:00Z'} for i in range(3)]
feed = {'schema_version': 1, 'generated_at': '2026-10-21T01:00:00Z', 'categories': ['hep-th'],
        'translation': {'engine': 'argos', 'status': 'complete'}, 'papers': rows}


def main():
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(ROOT / 'site'))
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            for width, height in [(1280, 900), (390, 844)]:
                context = browser.new_context(viewport={'width': width, 'height': height}, service_workers='block')
                page = context.new_page()
                errors = []
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.route('**/cdn.jsdelivr.net/**', lambda route: route.abort())
                page.route('**/data/latest.json', lambda route: route.fulfill(json=feed))
                page.goto(f'http://127.0.0.1:{server.server_port}/')
                page.wait_for_selector('#paper-content h2')
                assert page.locator('#remaining').inner_text() == '3'
                assert page.locator('body').evaluate('(e)=>e.scrollWidth<=innerWidth'), 'Horizontal overflow'
                page.locator('#keep').click()
                page.wait_for_timeout(250)
                assert page.locator('#saved-count').inner_text() == '1'
                assert page.locator('#remaining').inner_text() == '2'
                page.locator('#undo').click()
                assert page.locator('#saved-count').inner_text() == '0'
                assert page.locator('#remaining').inner_text() == '3'
                page.locator('#keep').click()
                page.wait_for_timeout(250)
                page.reload()
                page.wait_for_selector('#paper-content h2')
                assert page.locator('#saved-count').inner_text() == '1', 'Save did not persist'
                page.locator('#saved-open').click()
                assert page.locator('.saved-item').count() == 1
                with page.expect_download() as download_info:
                    page.locator('#export-bib').click()
                downloaded = Path(download_info.value.path()).read_text()
                assert 'archivePrefix = {arXiv}' in downloaded
                page.locator('[data-close="saved-dialog"]').click()
                page.locator('#search').fill('no-result-xyz')
                assert page.locator('#empty').is_visible()
                page.locator('#search').fill('')
                page.locator('#language').click()
                assert 'Test paper' in page.locator('#paper-content h2').inner_text()
                # Simulate the pointer sequence used by the touch/mouse swipe state machine.
                page.locator('#card').dispatch_event('pointerdown', {'pointerId': 1, 'clientX': 150, 'clientY': 300, 'button': 0, 'isPrimary': True})
                page.locator('#card').dispatch_event('pointermove', {'pointerId': 1, 'clientX': 152, 'clientY': 340, 'button': 0, 'isPrimary': True})
                page.locator('#card').dispatch_event('pointerup', {'pointerId': 1, 'clientX': 152, 'clientY': 340, 'button': 0, 'isPrimary': True})
                assert page.locator('#remaining').inner_text() == '2', 'Vertical scroll was treated as swipe'
                # Screenshots are test artifacts only; no fake papers in site/data.
                screenshot = ROOT / 'test-results' / f'ui-{width}.png'
                screenshot.parent.mkdir(exist_ok=True)
                page.screenshot(path=str(screenshot), full_page=True)
                assert not errors, '\n'.join(errors)
                context.close()
            print('Browser smoke passed: desktop + mobile viewport, save/undo/reload/export/search/vertical-scroll.')
        finally:
            browser.close()
    server.shutdown()


if __name__ == '__main__':
    main()
