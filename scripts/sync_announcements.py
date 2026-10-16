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


def parse_feed(raw, now=None):
    if len(raw) > MAX_BYTES or re.search(br'<!\s*(DOCTYPE|ENTITY)', raw, re.I):
        raise ValueError('Oversized feed or forbidden XML declarations')
    root = ET.fromstring(raw)
    channel = root.find('channel')
    if root.tag != 'rss' or channel is None or not channel.findtext('title'):
        raise ValueError('Expected a valid RSS channel')
    now = now or datetime.now(timezone.utc)
    events = []
    seen = set()
    for item in channel.findall('item'):
        categories = {text(c.text, 100).casefold() for c in item.findall('category')}
        if 'studio announcements' not in categories:
            continue
        title = text(item.findtext('title'), 90)
        try:
            published = parsedate_to_datetime(item.findtext('pubDate', ''))
            if published.tzinfo is None:
                raise ValueError('Missing timezone')
        except (ValueError, TypeError, OverflowError):
            continue
        if not title or published > now or published < now - timedelta(days=90):
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


def fetch_feed():
    request = urllib.request.Request(FEED_URL, headers={'User-Agent': 'LetsDanceAnnouncements/1.0', 'Accept': 'application/rss+xml, application/xml, text/xml'})
    with urllib.request.urlopen(request, timeout=30) as response:
        if response.status != 200 or response.url != FEED_URL:
            raise ValueError('Unexpected RSS response or redirect')
        return response.read(MAX_BYTES + 1)


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
