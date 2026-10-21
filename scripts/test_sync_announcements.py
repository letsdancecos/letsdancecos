import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from sync_announcements import parse_feed, sync, is_announcement_page, public_category
from unittest.mock import patch

NOW = datetime(2026, 10, 16, 23, tzinfo=timezone.utc)


def rss(items=''):
    return ('<rss><channel><title>Studio</title>' + items + '</channel></rss>').encode()


def item(title='Studio closed on Oct 17th and 19th', category='Studio Announcements', date='Fri, 16 Oct 2026 20:00:00 GMT'):
    return f'<item><title>{title}</title><category>{category}</category><pubDate>{date}</pubDate><description>&lt;p&gt;Hello&lt;/p&gt;&lt;script&gt;bad()&lt;/script&gt;</description></item>'


class ImportTests(unittest.TestCase):
    def test_filters_sanitizes_and_deduplicates(self):
        data = parse_feed(rss(item() + item() + item(category='Other') + item(date='Fri, 16 Oct 2027 20:00:00 GMT') + item(date='Fri, 16 Jan 2026 20:00:00 GMT') + item(date='bad')), NOW)
        self.assertEqual(len(data['events']), 1)
        event = data['events'][0]
        self.assertEqual(len(event.pop('id')), 64)
        self.assertEqual(event.pop('published_at'), '2026-10-16T20:00:00+00:00')
        self.assertEqual(event, {'title': 'Studio closed on Oct 17th and 19th', 'category': 'closure', 'date': '2026-10-16', 'details': 'Hello'})

    def test_guid_identity_survives_title_edits(self):
        first = item().replace('</item>', '<guid>stable-post-id</guid></item>')
        second = first.replace('Studio closed on Oct 17th and 19th', 'Updated title')
        self.assertEqual(parse_feed(rss(first), NOW)['events'][0]['id'],
                         parse_feed(rss(second), NOW)['events'][0]['id'])

    def test_real_wix_items_without_category(self):
        payload = rss(item().replace('<category>Studio Announcements</category>', '<link>https://www.letsdancecos.com/post/test</link>'))
        self.assertEqual(len(parse_feed(payload, NOW, lambda link: True)['events']), 1)
        self.assertEqual(parse_feed(payload, NOW, lambda link: False), {'events': []})

    def test_public_page_category_not_navigation(self):
        link = '<a href="https://www.letsdancecos.com/blog/categories/studio-announcements">Studio Announcements</a>'
        page = '<div data-hook="post-page">' + link + '</div>'
        self.assertFalse(is_announcement_page(page.encode()))
        self.assertTrue(is_announcement_page((page + '<ul aria-label="Post categories">' + link + '</ul>').encode()))
        with self.assertRaises(ValueError):
            is_announcement_page(b'<html>Challenge or error</html>')
        for url in ('https://evil.example/post/x', 'http://www.letsdancecos.com/post/x', 'https://www.letsdancecos.com@evil.example/post/x'):
            with self.assertRaises(ValueError):
                public_category(url)

    def test_category_fetch_failure_preserves_feed(self):
        payload = rss(item().replace('<category>Studio Announcements</category>', '<link>https://www.letsdancecos.com/post/test</link>'))
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'announcements.json'
            original = b'{"events": []}'
            output.write_bytes(original)
            with patch('sync_announcements.fetch_url', side_effect=TimeoutError):
                with self.assertRaises(TimeoutError):
                    sync(lambda: payload, output)
            self.assertEqual(output.read_bytes(), original)

    def test_empty_valid_feed(self):
        self.assertEqual(parse_feed(rss(), NOW), {'events': []})

    def test_encoded_xml_declarations_rejected(self):
        with self.assertRaises((ValueError, UnicodeError)):
            parse_feed('<!DOCTYPE rss><rss/>'.encode('utf-16'), NOW)

    def test_errors_preserve_existing_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'announcements.json'
            original = b'{"events": [{"title": "Keep me"}]}\n'
            for payload in (b'<html>failure</html>', b'<rss>', b'<!DOCTYPE rss><rss/>', b'x' * 2_000_001):
                output.write_bytes(original)
                with self.assertRaises(Exception):
                    sync(lambda: payload, output)
                self.assertEqual(output.read_bytes(), original)
            def failed_fetch():
                raise TimeoutError('fetch failed')
            with self.assertRaises(TimeoutError):
                sync(failed_fetch, output)
            self.assertEqual(output.read_bytes(), original)


if __name__ == '__main__':
    unittest.main()
