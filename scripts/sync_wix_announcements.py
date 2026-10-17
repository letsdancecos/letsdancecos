#!/usr/bin/env python3
"""Import published Wix Blog posts into the public Let's Dance announcement feed.

Reads a PUBLIC Wix RSS URL. No Wix account, API keys, or parent data required.
No changes are written if fetching or parsing fails.
"""
from __future__ import annotations

import html
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sys
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

RSS_URL = "https://www.letsdancecos.com/blog-feed.xml"
OUTPUT = Path(__file__).resolve().parents[1] / "app" / "announcements.json"
CATEGORY = "studio announcements"
MAX_BYTES = 2_000_000
MAX_POSTS = 20


class PlainText(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag in {"script", "style"}:
            self.skip += 1
        elif tag in {"p", "br", "div", "li", "h1", "h2", "h3"}:
            self.parts.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"}:
            self.skip = max(0, self.skip - 1)
        elif tag in {"p", "div", "li", "h1", "h2", "h3"}:
            self.parts.append(" ")

    def handle_data(self, data: str) -> None:
        if not self.skip:
            self.parts.append(data)


def clean_text(value: str) -> str:
    parser = PlainText()
    parser.feed(value or "")
    return " ".join(html.unescape("".join(parser.parts)).split())


def kind(title: str, body: str) -> str:
    text = (title + " " + body[:120]).casefold()
    if re.search(r"\b(closed|closure|cancelled|canceled|no classes|holiday)\b", text):
        return "closure"
    if re.search(r"\b(recital|performance|rehearsal|showcase)\b", text):
        return "recital"
    return "news"


def parse_feed(raw: bytes) -> list[dict[str, str]]:
    root = ET.fromstring(raw)
    channel = root.find("channel")
    if root.tag.lower() != "rss" or channel is None:
        raise ValueError("URL did not return a valid RSS feed")

    items = channel.findall("item")
    announcements: list[dict[str, str]] = []
    for item in items[:MAX_POSTS]:
        title = clean_text(item.findtext("title") or "")[:90]
        if not title:
            continue

        categories = [clean_text(c.text or "").casefold() for c in item.findall("category")]
        # Wix currently offers a site-wide feed, not a category-only RSS URL.
        # If RSS includes categories, import only Studio Announcements.
        # If Wix omits category metadata entirely, treat the blog as a dedicated
        # announcement blog. Keep other blog content out of this account.
        if categories and CATEGORY not in categories:
            continue

        rich_content = item.findtext("{http://purl.org/rss/1.0/modules/content/}encoded")
        body = clean_text(rich_content or item.findtext("description") or "")[:400]
        announcements.append({
            "title": title,
            "category": kind(title, body),
            # Do not pretend publication date is the date of a studio event.
            "date": "",
            "details": body,
        })
    return announcements


def self_test() -> None:
    sample = b"""<?xml version="1.0"?>
    <rss version="2.0"><channel>
      <item><title>Studio closed October 17 and 19</title>
        <category>Studio Announcements</category>
        <description><![CDATA[<p>There are no classes.</p>]]></description></item>
      <item><title>A personal blog post</title><category>Other</category>
        <description>Not a studio announcement</description></item>
    </channel></rss>"""
    items = parse_feed(sample)
    assert len(items) == 1, items
    assert items[0]["category"] == "closure", items
    assert items[0]["date"] == "", items
    assert "no classes" in items[0]["details"], items
    try:
        parse_feed(b"<html>not an RSS feed</html>")
    except ValueError:
        pass
    else:
        raise AssertionError("HTML mistaken for an RSS feed")
    print("RSS importer self-test passed")


def main() -> int:
    if "--self-test" in sys.argv:
        self_test()
        return 0
    try:
        request = Request(RSS_URL, headers={"User-Agent": "LetsDanceStudios/1.0 (+GitHub Pages)"})
        with urlopen(request, timeout=25) as response:
            raw = response.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise ValueError("RSS feed exceeded size limit")
        events = parse_feed(raw)
    except (OSError, ET.ParseError, ValueError) as exc:
        print(f"RSS not ready: {exc}. Existing announcements preserved.")
        return 0

    payload = json.dumps({"events": events}, ensure_ascii=False, indent=2) + "\n"
    if OUTPUT.exists() and OUTPUT.read_text(encoding="utf-8") == payload:
        print(f"No changes; {len(events)} Wix announcements already in sync")
        return 0
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(payload, encoding="utf-8")
    print(f"Synced {len(events)} published Wix announcement(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
