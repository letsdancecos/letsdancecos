"""Allow public RSS to catch up with a Wix publish event before the normal import."""
import os
import time
import xml.etree.ElementTree as ET
from urllib.parse import urlsplit

from sync_announcements import fetch_feed, parse_feed


def valid_url(value):
    url = urlsplit(value)
    return (url.scheme == 'https' and url.netloc == 'www.letsdancecos.com'
            and url.path.startswith('/post/') and len(url.path) > 6
            and not url.query and not url.fragment and len(value) <= 1000)


def wait_for_post(url, fetch=fetch_feed, sleep=time.sleep, attempts=7):
    if not valid_url(url):
        raise ValueError('Invalid Wix post URL')
    for attempt in range(attempts):
        try:
            raw = fetch()
            # Use the existing parser's validation and public category checks.
            # No event data is written and no webhook text becomes app content.
            parse_feed(raw)
            channel = ET.fromstring(raw.decode('utf-8-sig')).find('channel')
            if any(item.findtext('link') == url for item in channel.findall('item')):
                return
        except Exception:
            # A temporary Wix failure must not bypass the normal import.
            pass
        if attempt + 1 < attempts:
            sleep(20)
    raise RuntimeError('Published post not yet available in public RSS; scheduled backup remains enabled')


if __name__ == '__main__':
    wait_for_post(os.environ.get('WIX_POST_URL', ''))
