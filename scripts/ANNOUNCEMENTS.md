# Public Wix announcements

The action reads https://www.letsdancecos.com/blog-feed.xml twice per hour
(GitHub scheduling can be delayed) and updates `app/announcements.json` only
when its contents change. No Wix login, secret, or third-party service is needed.
It explicitly requests a GitHub Pages rebuild, including on the next run if a
previous deployment failed. Existing branch-based Pages hosting is retained.

Publish a Wix Blog post in **Studio Announcements** to include it. Drafts and
scheduled future posts are not imported. Wix RSS omits category labels, so the
importer checks the category links in each public post's **Post categories**
section (not the navigation menu). Only the fixed studio HTTPS host and /post/
paths are permitted; redirects are rejected. A failed page fetch or unexpected
page preserves the existing feed. No private Wix APIs or credentials are used.
The first published past-closure sample was tested from the public RSS and post
page on October 20, 2026.

Only posts published within 90 days are included, newest first, up to 60.
Titles containing closed/closure become Closures; recital becomes Recitals;
others become News. The displayed date is the **publication date**, not an
inferred event date; write closure/event dates explicitly in the title/body.
Titles are limited to 90 characters and plain-text details to 400. HTML and
scripts are never rendered. RSS is a bounded recent-post feed, not an archive.
Unpublishing/removing a post or removing its category removes it on the next
successful import. A valid empty feed clears announcements; network failures,
invalid XML, forbidden declarations, or oversized responses preserve the last
file and fail the action visibly. GitHub emails follow the account's settings.

Run `python3 -m unittest discover -s scripts` and then
`python3 scripts/sync_announcements.py` to test. The workflow can also be run
manually from Actions. Only the repository's built-in GitHub token is used,
with contents/pages write permissions; feed text is never evaluated as code.
