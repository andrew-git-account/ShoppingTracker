"""
Navigation bar tests (SP-050).

The navbar used to be one non-wrapping row, wider than a phone, so every
logged-in page scrolled sideways at 375px. The fix is CSS inside the existing
mobile media query. The CSS tests read the stylesheet as text (no browser) to
check the rule lives in the right place; the markup tests make sure the links,
their order, admin-only visibility and the active highlighting did not change.
"""

import re
from pathlib import Path

CSS_PATH = Path(__file__).resolve().parent.parent / 'static' / 'css' / 'style.css'
# Comments are stripped so a comment between two rules can't hide a selector from the helpers
CSS = re.sub(r'/\*.*?\*/', '', CSS_PATH.read_text(encoding='utf-8'), flags=re.DOTALL)


def media_block(query: str) -> str:
    """Body of the first @media block with this query, found by matching braces."""
    start = CSS.index(query)
    body_start = CSS.index('{', start) + 1
    depth = 1
    i = body_start
    while depth:
        depth += {'{': 1, '}': -1}.get(CSS[i], 0)
        i += 1
    return CSS[body_start:i - 1]


def rule_body(css: str, selector: str) -> str:
    """Declarations of the first rule whose selector is exactly `selector`."""
    match = re.search(r'(?:^|\})\s*' + re.escape(selector) + r'\s*\{([^}]*)\}', css)
    assert match, f'rule {selector!r} not found'
    return match.group(1)


def nav_links(html: str):
    """[(text, class attribute)] for each link in the <ul class="nav-tabs"> list."""
    nav = html.split('<ul class="nav-tabs">')[1].split('</ul>')[0]
    links = []
    for attrs, text in re.findall(r'<a ([^>]*)>(.*?)</a>', nav, flags=re.DOTALL):
        cls = re.search(r'class="([^"]*)"', attrs)
        links.append((re.sub(r'\s+', ' ', text).strip(), cls.group(1) if cls else ''))
    return links


class TestMobileNavCss:

    def test_tabs_wrap_inside_the_mobile_media_query(self):
        mobile = media_block('@media (max-width: 768px)')

        assert 'flex-wrap: wrap' in rule_body(mobile, '.nav-tabs')

    def test_tab_links_are_tighter_on_mobile(self):
        mobile = media_block('@media (max-width: 768px)')

        assert 'padding' in rule_body(mobile, '.nav-tabs a')

    def test_desktop_navbar_rules_are_unchanged(self):
        # The top-level (desktop) rules must not wrap and keep their original padding
        outside = CSS.replace(media_block('@media (max-width: 768px)'), '')

        assert 'flex-wrap' not in rule_body(outside, '.nav-tabs')
        assert 'var(--spacing-lg)' in rule_body(outside, '.nav-tabs a')
        assert 'white-space: nowrap' in rule_body(outside, '.nav-tabs a')


class TestNavMarkupUnchanged:

    NON_ADMIN = ['Upload', 'Upload Statement', 'History', 'Statistics', 'Contact', 'Log out']
    ADMIN = ['Upload', 'Upload Statement', 'History', 'Statistics',
             'LLM Usage', 'Users', 'Categories', 'Contact', 'Log out']

    def test_non_admin_sees_the_same_tabs_in_the_same_order(self, logged_in_client):
        html = logged_in_client.get('/history').get_data(as_text=True)

        assert [t.replace('✉️ ', '') for t, _ in nav_links(html)] == self.NON_ADMIN

    def test_admin_sees_the_extra_admin_tabs_in_the_same_order(self, admin_client):
        html = admin_client.get('/history').get_data(as_text=True)

        assert [t.replace('✉️ ', '') for t, _ in nav_links(html)] == self.ADMIN

    def test_only_the_current_tab_is_highlighted(self, logged_in_client):
        html = logged_in_client.get('/history').get_data(as_text=True)

        active = [text for text, cls in nav_links(html) if 'active' in cls.split()]
        assert active == ['History']

    def test_logged_out_page_has_no_nav_tabs(self, client):
        html = client.get('/login').get_data(as_text=True)

        assert nav_links(html) == []
