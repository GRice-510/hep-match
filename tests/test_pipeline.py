from __future__ import annotations
import datetime as dt
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import common
import fetch_papers as fetch
import translate_papers as tr


def feed(ident='2610.01234v1', title='A test paper', total=1):
    return f'''<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom" xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/">
<opensearch:totalResults>{total}</opensearch:totalResults><entry>
<id>http://arxiv.org/abs/{ident}</id><title>{title}</title><summary>We study $m^2$.</summary>
<published>2026-10-20T12:00:00Z</published><updated>2026-10-21T12:00:00Z</updated>
<author><name>A. Author</name></author><category term="hep-th"/><category term="hep-ph"/>
<arxiv:primary_category term="hep-th"/><arxiv:comment>20 pages</arxiv:comment></entry></feed>'''.encode()


class HelpersTest(unittest.TestCase):
    def test_config(self):
        cfg = common.config()
        self.assertTrue(cfg['categories'])
        self.assertIn(cfg['translation']['engine'], ('argos', 'none', 'deepl'))

    def test_math_all_delimiters(self):
        source = r'We study $m^2$, $$a+b$$, \(x\), and \[y\].'
        seen = []
        out = common.translate_math_safe(source, lambda t: seen.append(t) or t.upper())
        for formula in [r'$m^2$', r'$$a+b$$', r'\(x\)', r'\[y\]']:
            self.assertIn(formula, out)
            self.assertFalse(any(formula in item for item in seen))
        self.assertIn('WE STUDY', out)

    def test_multiline_display(self):
        self.assertEqual(common.translate_math_safe('$$a\n+b$$', lambda _: self.fail()), '$$a\n+b$$')

    def test_escaped_dollar(self):
        seen = []
        common.translate_math_safe(r'Cost \$5 and \$7', lambda t: seen.append(t) or t)
        self.assertEqual(len(seen), 1)

    def test_empty_translation_rejected(self):
        with self.assertRaises(ValueError):
            common.translate_math_safe('Hello', lambda _: '')

    def test_cache_invalidation(self):
        self.assertNotEqual(common.cache_key('argos', 'a'), common.cache_key('argos', 'b'))
        self.assertNotEqual(common.cache_key('argos', 'a'), common.cache_key('deepl', 'a'))

    def test_atomic_json(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / 'nested/file.json'
            common.atomic_json(path, {'日本語': '値'})
            self.assertEqual(common.load_json(path), {'日本語': '値'})
            self.assertFalse(path.with_name('file.json.tmp').exists())


class FeedTest(unittest.TestCase):
    def test_parse(self):
        rows, total = fetch.parse_feed(feed())
        self.assertEqual(total, 1)
        self.assertEqual(rows[0]['id'], '2610.01234')
        self.assertEqual(rows[0]['categories'], ['hep-th', 'hep-ph'])
        self.assertEqual(rows[0]['primary'], 'hep-th')
        self.assertEqual(rows[0]['version'], 1)

    def test_legacy_id(self):
        rows, _ = fetch.parse_feed(feed('hep-th/9901001v2'))
        self.assertEqual(rows[0]['id'], 'hep-th/9901001')
        self.assertEqual(rows[0]['version'], 2)

    def test_api_error_not_a_paper(self):
        with self.assertRaises(ValueError):
            fetch.parse_feed(feed('errors#bad_query'))
        with self.assertRaises(ValueError):
            fetch.parse_feed(b'<html>Service unavailable</html>')

    def test_recent_window_and_short_page(self):
        p = fetch.parse_feed(feed())[0][0]
        q = dict(p, id='2610.09999', published='2026-10-10T12:00:00Z')
        calls = []
        class Client:
            def get(self, params):
                calls.append(params)
                return ([p], 500) if len(calls) == 1 else ([q], 500)
        rows, truncated = fetch.collect(Client(), ['hep-th', 'hep-ph'], common.parse_date('2026-10-14T00:00:00Z'), 1000)
        self.assertEqual(len(rows), 1)
        self.assertFalse(truncated)
        self.assertEqual(calls[1]['start'], 1)
        self.assertIn('cat:hep-th OR cat:hep-ph', calls[0]['search_query'])

    def test_cap_warning(self):
        p = fetch.parse_feed(feed())[0][0]
        class Client:
            def get(self, params): return [p], 900
        rows, truncated = fetch.collect(Client(), ['hep-th'], common.parse_date('2026-10-14'), 1)
        self.assertTrue(truncated)

    def test_changed_abstract_drops_old_translation(self):
        p = fetch.parse_feed(feed())[0][0]
        old = dict(p, title_ja='題名', abstract_ja='旧訳')
        new = dict(p, abstract='Changed abstract')
        fetch.retain_translations([new], [old])
        self.assertEqual(new['title_ja'], '題名')
        self.assertNotIn('abstract_ja', new)

    def test_fetch_error_does_not_overwrite(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / 'latest.json'
            path.write_text('{"old":true}')
            with patch.object(fetch, 'DATA', path), patch.object(fetch, 'collect', side_effect=RuntimeError('down')):
                with self.assertRaises(RuntimeError): fetch.main()
            self.assertEqual(path.read_text(), '{"old":true}')


class TranslationTest(unittest.TestCase):
    def document(self):
        return {'translation': {}, 'papers': [{'id': '2610.01234', 'title': 'Mass $m$', 'abstract': 'Abstract text'}]}

    def test_math_and_cache(self):
        doc, cached, calls = self.document(), {}, []
        tr.apply_translations(doc, cached, 'test', ['title'], lambda t: calls.append(t) or '訳', tr.Budget(10, 100))
        self.assertEqual(doc['papers'][0]['title_ja'], '訳 $m$')
        tr.apply_translations(self.document(), cached, 'test', ['title'], lambda t: self.fail('cached field translated again'), tr.Budget(10, 100))
        self.assertEqual(len(calls), 1)

    def test_zero_budget_keeps_original(self):
        doc = self.document()
        tr.apply_translations(doc, {}, 'test', ['title'], lambda t: self.fail(), tr.Budget(10, 0))
        self.assertEqual(doc['translation']['status'], 'partial')
        self.assertNotIn('title_ja', doc['papers'][0])
        self.assertEqual(doc['papers'][0]['title'], 'Mass $m$')

    def test_missing_api_key(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(RuntimeError): tr.DeepLTranslator()

    def test_paid_endpoint_refused(self):
        with patch.dict(os.environ, {'DEEPL_API_KEY': 'test', 'DEEPL_API_BASE': 'https://api.deepl.com'}, clear=True):
            with patch.object(tr.urllib.request, 'urlopen') as call:
                with self.assertRaises(RuntimeError): tr.DeepLTranslator()
                call.assert_not_called()

    def test_arbitrary_host_refused(self):
        with patch.dict(os.environ, {'DEEPL_API_KEY': 'test', 'DEEPL_API_BASE': 'https://example.com'}, clear=True):
            with self.assertRaises(RuntimeError): tr.DeepLTranslator()

    def test_quota_exhaustion(self):
        with patch.dict(os.environ, {'DEEPL_API_KEY': 'test'}, clear=True), patch.object(tr.DeepLTranslator, 'request', return_value={'character_count': 100, 'character_limit': 100}):
            translator = tr.DeepLTranslator()
            with self.assertRaises(tr.BudgetExceeded): translator('hello')


if __name__ == '__main__':
    unittest.main()
