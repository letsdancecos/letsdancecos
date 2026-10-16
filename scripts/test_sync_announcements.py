import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from sync_announcements import parse_feed, sync

NOW = datetime(2026, 10, 16, 23, tzinfo=timezone.utc)


def rss(items=''):
    return ('<rss><channel><title>Studio</title>' + items + '</channel></rss>').encode()


def item(title='Studio closed on Oct 17th and 19th', category='Studio Announcements', date='Fri, 16 Oct 2026 20:00:00 GMT'):
    return f'<item><title>{title}</title><category>{category}</category><pubDate>{date}</pubDate><description>&lt;p&gt;Hello&lt;/p&gt;&lt;script&gt;bad()&lt;/script&gt;</description></item>'


class ImportTests(unittest.TestCase):
    def test_filters_sanitizes_and_deduplicates(self):
        data = parse_feed(rss(item() + item() + item(category='Other') + item(date='Fri, 16 Oct 2027 20:00:00 GMT') + item(date='Fri, 16 Jan 2026 20:00:00 GMT') + item(date='bad')), NOW)
        self.assertEqual(data, {'events': [{'title': 'Studio closed on Oct 17th and 19th', 'category': 'closure', 'date': '2026-10-16', 'details': 'Hello'}]})

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
