"""Offline tests for campaign/scout/blog_sample.py. Run: python -m unittest campaign/scout/test_blog_sample.py"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import blog_sample as bs  # noqa: E402
import html_body  # noqa: E402


class BlogSampleTest(unittest.TestCase):
    def test_articles_pick_the_blog_prefix_and_skip_index_pages(self):
        urls = {f"https://x.io/blog/post-{i}/": None for i in range(5)}
        urls.update({"https://x.io/blog/": None, "https://x.io/blog/category/news/": None, "https://x.io/pricing/": None})
        prefix, posts = bs.articles(urls, "x.io")
        self.assertEqual(prefix, "/blog/")
        self.assertEqual(len(posts), 5)

    def test_body_with_menu_class_is_not_skipped(self):
        page = '<body class="jet-mega-menu-location"><nav><a href="/a">n</a></nav><article><p>Text <a href="/blog/b">b</a></p></article></body>'
        _, text, links = html_body.editorial(page)
        self.assertIn("Text", text)
        self.assertEqual(links, ["/blog/b"])

    def test_slug_tokens_drop_stopwords_and_brand(self):
        self.assertEqual(bs.slug_tokens("https://x.io/blog/best-x-kubernetes-cost-guide-2025/", "x"), ["kubernetes", "cost"])


if __name__ == "__main__":
    unittest.main()
