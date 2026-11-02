import unittest
from unittest.mock import patch
from wait_for_wix_rss import wait_for_post

URL = 'https://www.letsdancecos.com/post/test'


def feed(url):
    return ('<rss><channel><title>Studio</title><item><link>' + url + '</link></item></channel></rss>').encode()


class WaitTests(unittest.TestCase):
    @patch('wait_for_wix_rss.parse_feed')
    def test_waits_for_exact_post(self, parse):
        responses = iter([feed(URL + '-other'), feed(URL)])
        sleeps = []
        wait_for_post(URL, fetch=lambda: next(responses), sleep=sleeps.append)
        self.assertEqual(sleeps, [20])
        self.assertEqual(parse.call_count, 2)

    def test_invalid_url_does_not_fetch(self):
        with self.assertRaises(ValueError):
            wait_for_post('https://evil.example/post/test', fetch=lambda: self.fail())

    @patch('wait_for_wix_rss.parse_feed', side_effect=ValueError('invalid RSS'))
    def test_invalid_feed_never_counts_as_ready(self, parse):
        with self.assertRaises(RuntimeError):
            wait_for_post(URL, fetch=lambda: feed(URL), sleep=lambda _: None, attempts=2)

    def test_real_parser_rejects_xml_declarations(self):
        with self.assertRaises(RuntimeError):
            wait_for_post(URL, fetch=lambda: b'<!DOCTYPE rss><rss/>', attempts=1)


if __name__ == '__main__':
    unittest.main()
