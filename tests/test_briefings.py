"""Checks for briefing input validation, safe links and generated downloads."""
import contextlib
import copy
import io
import json
import sys
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'scripts'))
import analog_briefings
import build as site_build


class Links(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.links = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self.links.append(dict(attrs))


class BriefingChecks(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.content = Path(self.directory.name) / 'content'
        (self.content / 'analog-briefings').mkdir(parents=True)
        selection = {'title': 'Example engineering paper', 'publishedDate': '2026-10-15',
                     'url': 'https://example.invalid/paper', 'bestRead': True}
        selection.update({key: 'Example summary.' for _, key in analog_briefings.FIELDS})
        self.issue = {'date': '2026-10-16', 'title': '模拟电路周报',
                      'overview': '本期阅读摘要。', 'selections': [selection]}

    def save(self, *, stale_index=False):
        directory = self.content / 'analog-briefings'
        (directory / '2026-10-16.json').write_text(json.dumps(self.issue), encoding='utf-8')
        record = {key: self.issue[key] for key in ('date', 'title', 'overview')}
        record['count'] = 99 if stale_index else len(self.issue['selections'])
        (directory / 'index.json').write_text(json.dumps({'issues': [record]}), encoding='utf-8')

    def test_valid_issue_and_downloads(self):
        self.save()
        issues = analog_briefings.load_issues(self.content)
        site = {'nameFull': 'AI 芯动力', 'nav': []}
        generated = dict(analog_briefings.pages(site, issues, site_build))
        self.assertEqual(json.loads(generated['briefings/data/2026-10-16.json']), self.issue)
        self.assertIn(self.issue['title'], generated['briefings/data/2026-10-16.md'])
        self.assertIn('briefings/index.html', generated)
        links = Links(generated['briefings/2026-10-16/index.html']).links
        source = next(link for link in links if link.get('href') == self.issue['selections'][0]['url'])
        self.assertIn('noopener', source['rel'])
        self.assertEqual(source['target'], '_blank')
        self.assertEqual(len([link for link in links if 'download' in link]), 2)

    def test_non_https_or_malformed_source_is_rejected(self):
        original = copy.deepcopy(self.issue)
        for url in ('http://example.invalid/paper', 'javascript:alert(1)', 'https://user:password@example.invalid/paper', 'https://example.invalid/a b', None):
            with self.subTest(url=url):
                self.issue = copy.deepcopy(original)
                self.issue['selections'][0]['url'] = url
                self.save()
                with self.assertRaises(ValueError):
                    analog_briefings.load_issues(self.content)

    def test_non_object_selection_is_rejected(self):
        self.issue['selections'] = ['invalid entry']
        self.save()
        with self.assertRaises(ValueError):
            analog_briefings.load_issues(self.content)

    def test_date_must_match_filename(self):
        self.issue['date'] = '2026-10-17'
        self.save()
        with self.assertRaises(ValueError):
            analog_briefings.load_issues(self.content)

    def test_index_cannot_silently_drift_from_published_issue(self):
        self.save(stale_index=True)
        with self.assertRaises(ValueError):
            analog_briefings.load_issues(self.content)

    def test_exactly_one_best_read_is_required(self):
        self.issue['selections'][0]['bestRead'] = False
        self.save()
        with self.assertRaises(ValueError):
            analog_briefings.load_issues(self.content)

    def test_empty_issue_is_allowed(self):
        self.issue['selections'] = []
        self.save()
        self.assertEqual(analog_briefings.load_issues(self.content)[0]['selections'], [])

    def test_untrusted_text_is_escaped_when_rendered(self):
        self.issue['title'] = '<script>alert(1)</script>'
        self.issue['selections'][0]['title'] = '<img src=x onerror=alert(1)>'
        html = dict(analog_briefings.pages({'nameFull': 'AI 芯动力', 'nav': []}, [self.issue], site_build))['briefings/2026-10-16/index.html']
        self.assertNotIn('<script>alert(1)</script>', html)
        self.assertNotIn('<img src=x', html)

    def test_invalid_briefing_cannot_overwrite_published_pages(self):
        self.save(stale_index=True)
        output = Path(self.directory.name) / 'docs'
        output.mkdir()
        homepage = output / 'index.html'
        homepage.write_text('existing published page', encoding='utf-8')
        with patch.object(site_build, 'CONTENT', self.content), patch.object(site_build, 'DIST', output), patch.object(site_build, 'validate', return_value=[]), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(site_build.build(), 1)
        self.assertEqual(homepage.read_text(), 'existing published page')


if __name__ == '__main__':
    unittest.main()
