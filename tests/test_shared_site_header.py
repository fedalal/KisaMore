import unittest
from html.parser import HTMLParser

from cloud.app import main
from cloud.app.certificate_api import I18N, template_env


class HeaderParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.headers = 0
        self.in_language = False
        self.languages = []
        self.links = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "header" and "data-site-header" in attrs:
            self.headers += 1
        if tag == "select" and attrs.get("id") == "languageSelect":
            self.in_language = True
        if tag == "option" and self.in_language:
            self.languages.append(attrs.get("value"))
        if tag == "a" and attrs.get("data-site-text") in {"greenhouse", "battles", "pricing", "currency"}:
            self.links.append(attrs.get("href"))

    def handle_endtag(self, tag):
        if tag == "select":
            self.in_language = False


class SharedHeaderRoutes(unittest.IsolatedAsyncioTestCase):
    def assert_header(self, html):
        parser = HeaderParser()
        parser.feed(html)
        self.assertEqual(parser.headers, 1)
        self.assertEqual(parser.languages, ["en", "ru", "de", "fr", "es", "it", "pt", "pl", "zh"])
        self.assertEqual(parser.links, ["/#greenhouse", "/battle", "/pricing", "/wallet"])
        self.assertIn('id="accountButton"', html)

    async def test_all_html_routes_share_the_same_header(self):
        for route in (main.dashboard, main.battle_dashboard, main.pricing_page, main.wallet_page,
                      main.privacy_policy, main.delete_account_page, main.admin_dashboard):
            with self.subTest(route=route.__name__):
                response = await route()
                self.assert_header(response.body.decode("utf-8"))

    async def test_certificate_template_also_includes_the_header(self):
        html = template_env.get_template("battle_certificate.html").render(
            lang="en", t=I18N["en"],
            battle={"title":"Test", "rack":1, "start_date":"", "finished_date":"", "finished_year":"2026"},
            person={"name":"Test", "slot":1, "plant":"Plant", "winner":False},
            photos=[], resources=[], actions=[], action_count=0, qr_url="/qr")
        self.assert_header(html)


if __name__ == "__main__":
    unittest.main()
