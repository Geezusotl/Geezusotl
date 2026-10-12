"""Check failure handling and preservation boundaries of the news updater."""

import datetime
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import updateNews as news


class NewsChecks(unittest.TestCase):
    now = datetime.datetime(2026, 10, 12, tzinfo=datetime.timezone.utc)

    def testTrackingAndUnsafeLinks(self):
        self.assertEqual(news.cleanUrl("https://example.com/a?utm_source=x&topic=ai&fbclid=y"), "https://example.com/a?topic=ai")
        for url in ["javascript:alert(1)", "data:text/html,hello", "https://user:pass@example.com/x"]:
            self.assertIsNone(news.cleanUrl(url))

    def testFeedSortingAndDuplicateRemoval(self):
        xml = b'<rss><channel><item><title>Old</title><link>https://example.com/a?utm_source=x</link><pubDate>Sat, 10 Oct 2026 12:00:00 GMT</pubDate></item><item><title>Duplicate</title><link>https://example.com/a</link></item><item><title>New</title><link>https://example.com/b</link><pubDate>Sun, 11 Oct 2026 12:00:00 GMT</pubDate></item><item><title>Future</title><link>https://example.com/c</link><pubDate>Tue, 13 Oct 2026 12:00:00 GMT</pubDate></item></channel></rss>'
        self.assertEqual([item["title"] for item in news.parseFeed(xml, self.now)], ["New", "Old"])

    def testAtomAndMarkupEscaping(self):
        xml = b'<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>Some [news]</title><link href="https://example.com/x"/><updated>2026-10-11T10:00:00Z</updated></entry></feed>'
        item = news.parseFeed(xml, self.now)[0]
        self.assertEqual(item["url"], "https://example.com/x")
        self.assertEqual(news.markdownText("[news] <script>"), r"\[news\] &lt;script&gt;")

    def testRejectsEntities(self):
        with self.assertRaises(ValueError):
            news.parseFeed(b'<!DOCTYPE rss [<!ENTITY x "test">]><rss/>', self.now)

    def testMultipleSourcesKeepRecentDiverseHeadlines(self):
        category = {"name": "AI", "feeds": [{"source": "Industry", "url": "https://industry.example/feed"}, {"source": "Company", "url": "https://company.example/feed"}]}
        def fetch(feed, now):
            if feed["source"] == "Industry":
                return [{"title": str(i), "url": f"https://example.com/{i}", "published": f"2026-10-{11-i:02d}T00:00:00+00:00", "source": "Industry"} for i in range(4)]
            return [{"title": "Announcement", "url": "https://company.example/news", "published": "2026-10-08T00:00:00+00:00", "source": "Company"}, {"title": "Duplicate", "url": "https://example.com/0", "published": "2026-10-01T00:00:00+00:00", "source": "Company"}]
        with patch.object(news, "fetchFeed", side_effect=fetch):
            items = news.fetchCategory(category, self.now, 3)
        self.assertEqual([item["title"] for item in items], ["0", "1", "Announcement"])
        state = {"lastChecked": self.now.isoformat(), "categories": {"AI": {"items": items}}}
        rendered = news.renderNews([category], state)
        self.assertIn("· Company ·", rendered)
        self.assertIn("· Industry ·", rendered)

    def testOneFailedFeedStillReturnsCurrentNews(self):
        category = {"name": "AI", "feeds": [{"source": "Offline", "url": "https://offline.example/feed"}, {"source": "Working", "url": "https://working.example/feed"}]}
        item = {"title": "Fresh news", "url": "https://working.example/news", "published": "2026-10-11T00:00:00+00:00", "source": "Working"}
        def fetch(feed, now):
            if feed["source"] == "Offline":
                raise TimeoutError
            return [item]
        with patch.object(news, "fetchFeed", side_effect=fetch):
            self.assertEqual(news.fetchCategory(category, self.now, 3), [item])

    def testStaleSecondPublisherIsNotRevived(self):
        category = {"feeds": [{"source": "Current"}, {"source": "Old"}]}
        def fetch(feed, now):
            if feed["source"] == "Old":
                return [{"title": "Old", "url": "https://example.com/old", "published": "2026-08-01T00:00:00+00:00", "source": "Old"}]
            return [{"title": str(i), "url": f"https://example.com/{i}", "published": "2026-10-11T00:00:00+00:00", "source": "Current"} for i in range(3)]
        with patch.object(news, "fetchFeed", side_effect=fetch):
            self.assertEqual({item["source"] for item in news.fetchCategory(category, self.now, 2)}, {"Current"})

    def testFeedTitleFilters(self):
        xml = b'<rss><channel><item><title>AI company announces a model</title><link>https://example.com/news</link></item><item><title>AI event promotion</title><link>https://example.com/promo</link></item><item><title>General gadget</title><link>https://example.com/gadget</link></item></channel></rss>'
        from io import BytesIO
        feed = {"source": "Industry", "url": "https://example.com/feed", "includeTitlePattern": r"(?i)\bai\b", "excludeTitleTerms": ["event promotion"]}
        with patch.object(news.urllib.request, "urlopen", return_value=BytesIO(xml)):
            self.assertEqual([item["title"] for item in news.fetchFeed(feed, self.now)], ["AI company announces a model"])

    def testOnlyNewsRegionChanges(self):
        text = "Approved bio\n" + news.begin + "\nold\n" + news.end + "\nApproved riddle"
        result = news.replaceNews(text, "new")
        self.assertEqual(result, "Approved bio\n" + news.begin + "\nnew\n" + news.end + "\nApproved riddle")
        with self.assertRaises(ValueError):
            news.replaceNews(text + news.begin, "new")

    def testFailureRetainsPreviousHeadlines(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            item = {"title": "Saved story", "url": "https://example.com/story", "published": "2026-10-11T00:00:00+00:00"}
            state = {"lastChecked": "2026-10-11T00:00:00+00:00", "categories": {"AI": {"items": [item], "lastSuccess": "2026-10-11T00:00:00+00:00"}}}
            (folder / "newsSources.json").write_text(json.dumps({"perCategory": 2, "categories": [{"name": "AI", "source": "Publisher", "url": "https://example.com/feed"}]}))
            (folder / "newsCache.json").write_text(json.dumps(state))
            (folder / "README.md").write_text("BIO\n" + news.begin + "\nold\n" + news.end + "\nRIDDLE")
            with patch.object(news, "root", folder), patch.object(news, "fetchCategory", side_effect=TimeoutError), patch("sys.argv", ["updateNews.py"]):
                news.main()
            saved = json.loads((folder / "newsCache.json").read_text())
            self.assertEqual(saved["categories"]["AI"]["items"], [item])
            readme = (folder / "README.md").read_text()
            self.assertTrue(readme.startswith("BIO\n"))
            self.assertTrue(readme.endswith("\nRIDDLE"))
            self.assertIn("Saved story", readme)
            self.assertIn("Source unavailable", readme)


if __name__ == "__main__":
    unittest.main()
