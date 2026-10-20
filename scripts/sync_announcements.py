"""Import only public Studio Announcements; never expose Wix credentials or HTML."""
import json
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

FEED_URL = 'https://www.letsdancecos.com/blog-feed.xml'
OUTPUT = Path(__file__).resolve().parents[1] / 'app/announcements.json'
MAX_BYTES = 2_000_000


class PlainText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style', 'iframe'):
            self.hidden += 1
        if tag in ('p', 'br', 'div', 'li'):
            self.parts.append(' ')

    def handle_endtag(self, tag):
        if tag in ('script', 'style', 'iframe') and self.hidden:
            self.hidden -= 1
        self.parts.append(' ')

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def text(value, limit):
    parser = PlainText()
    parser.feed(value or '')
    return re.sub(r'\s+', ' ', ''.join(parser.parts)).strip()[:limit]


class PostCategories(HTMLParser):
    def __init__(self):
        super().__init__()
        self.is_post = False
        self.in_categories = False
        self.matches = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get('data-hook') == 'post-page':
            self.is_post = True
        if tag == 'ul' and attrs.get('aria-label') == 'Post categories':
            self.in_categories = True
        if self.in_categories and tag == 'a' and attrs.get('href') == 'https://www.letsdancecos.com/blog/categories/studio-announcements':
            self.matches = True

    def handle_endtag(self, tag):
        if tag == 'ul':
            self.in_categories = False


def is_announcement_page(raw):
    if len(raw) > MAX_BYTES:
        raise ValueError('Oversized post page')
    parser = PostCategories()
    parser.feed(raw.decode('utf-8-sig'))
    if not parser.is_post:
        raise ValueError('Expected public Wix post page')
    return parser.matches


def public_category(link):
    url = urlsplit(link)
    if url.scheme != 'https' or url.netloc != 'www.letsdancecos.com' or not url.path.startswith('/post/') or url.query or url.fragment:
        raise ValueError('Unexpected public post URL')
    return is_announcement_page(fetch_url(link))


def parse_feed(raw, now=None, category_check=public_category):
    if len(raw) > MAX_BYTES:
        raise ValueError('Oversized feed')
    # Wix serves UTF-8. Decode first so UTF-16 cannot bypass declaration checks.
    xml = raw.decode('utf-8-sig')
    if '\x00' in xml or re.search(r'<!\s*(DOCTYPE|ENTITY)', xml, re.I):
        raise ValueError('Oversized feed or forbidden XML declarations')
    root = ET.fromstring(xml)
    channel = root.find('channel')
    if root.tag != 'rss' or channel is None or not channel.findtext('title'):
        raise ValueError('Expected a valid RSS channel')
    now = now or datetime.now(timezone.utc)
    events = []
    seen = set()
    if len(channel.findall('item')) > 60:
        raise ValueError('Too many feed entries')
    for item in channel.findall('item'):
        categories = {text(c.text, 100).casefold() for c in item.findall('category')}
        title = text(item.findtext('title'), 90)
        try:
            published = parsedate_to_datetime(item.findtext('pubDate', ''))
            if published.tzinfo is None:
                raise ValueError('Missing timezone')
        except (ValueError, TypeError, OverflowError):
            continue
        if not title or published > now or published < now - timedelta(days=90):
            continue
        if categories:
            if 'studio announcements' not in categories:
                continue
        elif not category_check(item.findtext('link', '')):
            continue
        identity = item.findtext('guid') or item.findtext('link') or title
        if identity in seen:
            continue
        seen.add(identity)
        category = 'closure' if re.search(r'\b(closed|closure|closures)\b', title, re.I) else 'recital' if re.search(r'\brecitals?\b', title, re.I) else 'news'
        details = text(item.findtext('description') or item.findtext('{http://purl.org/rss/1.0/modules/content/}encoded'), 400)
        events.append((published, {'title': title, 'category': category, 'date': published.date().isoformat(), 'details': details}))
    events.sort(key=lambda row: row[0], reverse=True)
    return {'events': [event for _, event in events[:60]]}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('Unexpected redirect')


def fetch_url(url):
    request = urllib.request.Request(url, headers={'User-Agent': 'LetsDanceAnnouncements/1.0', 'Accept': 'application/rss+xml, application/xml, text/xml'})
    with urllib.request.build_opener(NoRedirect).open(request, timeout=30) as response:
        if response.status != 200 or response.url != url:
            raise ValueError('Unexpected RSS response or redirect')
        return response.read(MAX_BYTES + 1)


def fetch_feed():
    return fetch_url(FEED_URL)


def sync(fetch=fetch_feed, output=OUTPUT):
    # Parse everything before touching the existing feed. Errors fail the action.
    data = parse_feed(fetch())
    if output.exists() and json.loads(output.read_text(encoding='utf-8')) == data:
        print(f'Unchanged: {len(data["events"])} public announcements')
        return
    temporary = output.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(output)
    print(f'Updated: {len(data["events"])} public announcements')


if __name__ == '__main__':
    try:
        sync()
    except Exception as exc:
        print(f'RSS import failed; existing announcements preserved: {exc}', file=sys.stderr)
        sys.exit(1)
