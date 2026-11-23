"""Copied from add-vee scripts/html_body.py (commit 1ccb7ab, 2026-11-23) so the scout's blog sample counts links exactly
like add-vee's link graph does. Keep in sync if add-vee changes its editorial-body rule.

Shared, deterministic extraction of a page's *editorial body* from raw HTML -- stdlib only.

Used by compute_link_graph.py (which links count) and fetch_blog_raw.py (reading-packet text). Both need the same
answer to "what did the author actually put in this article", so the rule lives in one place.

Skipped as template/automatic regions (with everything nested inside them):
  - semantic tags: header, nav, footer, aside, script, style, noscript, svg, template, form
  - ARIA landmarks: role="navigation" | "banner" | "contentinfo" | "complementary" | "search"
  - class/id tokens that name site chrome or auto-filled widgets: nav/navbar/menu/header/footer/sidebar/breadcrumb/
    cookie/newsletter/subscribe/related/recommended/you-might/share/social, Webflow CMS lists (w-dyn-list) and
    hidden conditional elements (w-condition-invisible).
Why classes matter: on a real run (a Webflow site) the navbar and footer were plain <div class="navbar w-nav"> /
<div class="footer ...">, so a tag-name-only rule kept every template link, and the "You might also like" CMS
widget added three automatic post links to every article. Neither is an author's linking decision.
"""
import re
from html.parser import HTMLParser

SKIP_TAGS = {"header", "nav", "footer", "aside", "script", "style", "noscript", "svg", "template", "form"}
SKIP_ROLES = {"navigation", "banner", "contentinfo", "complementary", "search"}
SKIP_TOKEN_RE = re.compile(
    r"(^|[-_])(nav|navbar|navigation|menu|megamenu|header|footer|sidebar|breadcrumbs?|cookie|cookies|newsletter|"
    r"subscribe|related|recommended|share|social)($|[-_])|you-might|w-dyn-list|w-condition-invisible", re.I)
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}
BLOCK = {"p", "div", "li", "tr", "section", "article", "main", "blockquote", "h1", "h2", "h3", "h4", "h5", "h6"}


NEVER_SKIP = {"html", "body", "main", "article"}  # scout fix 2026-11-23: an Elementor site put "jet-mega-menu-location"
# on <body>, and the class rule then dropped the whole page (mybites.io: 0 chars of body). Page containers are never chrome.


def _skippable(tag, attrs):
    if tag in NEVER_SKIP:
        return False
    if tag in SKIP_TAGS:
        return True
    a = dict(attrs)
    if (a.get("role") or "").lower() in SKIP_ROLES:
        return True
    tokens = f"{a.get('class') or ''} {a.get('id') or ''}".split()
    return any(SKIP_TOKEN_RE.search(t) for t in tokens)


class _Body(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []          # open tags while inside a skipped region (depth tracking)
        self.links, self.parts, self.title, self._in_title = [], [], "", False

    def handle_starttag(self, tag, attrs):
        if tag == "title":
            self._in_title = True
        if self.stack:
            if tag not in VOID:
                self.stack.append(tag)
            return
        if _skippable(tag, attrs):
            if tag not in VOID:
                self.stack.append(tag)
            return
        if tag == "a":
            href = dict(attrs).get("href")
            if href:
                self.links.append(href)
        if tag in ("h1", "h2", "h3", "h4"):
            self.parts.append("\n\n" + "#" * int(tag[1]) + " ")
        elif tag in BLOCK or tag == "br":
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        if self.stack:
            # pop back to the matching open tag (tolerates unclosed children)
            if tag in self.stack:
                while self.stack and self.stack.pop() != tag:
                    pass
            return
        if tag in BLOCK:
            self.parts.append("\n")

    def handle_data(self, data):
        if self._in_title:
            self.title += data
            return
        if not self.stack:
            self.parts.append(data)


def editorial(raw_html):
    """Return (title, body_text, body_links) for one page. body_links are raw href values, unresolved."""
    p = _Body()
    p.feed(raw_html)
    p.close()
    text = re.sub(r"[ \t\r\f\v]+", " ", "".join(p.parts))
    text = re.sub(r"\n\s*\n+", "\n\n", text).strip()
    return p.title.strip(), text, p.links
