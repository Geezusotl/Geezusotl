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
