"""Regression checks for visible Kisa currency formatting on KisaMore web pages."""
from pathlib import Path
import re

STATIC = Path(__file__).parent / "app" / "static"
DISPLAY_FILES = (
    "index.html", "dashboard.js", "battle_site.html", "battle_site.js",
    "pricing.html", "pricing.js", "admin.html", "admin.js",
    "admin_battles.js", "battle_certificate.html",
)


def test_currency_amounts_use_only_symbol():
    for name in DISPLAY_FILES:
        content = (STATIC / name).read_text(encoding="utf-8")
        assert not re.search(r"\bKISA\b", content), name
        assert not re.search(r"\d+\s+Kisa\b", content), name
        assert not re.search(r"(?:\$\s*\d|\bUSD\b)", content), name


def test_menu_shows_currency_name_and_icon():
    for name in ("index.html", "battle_site.html", "pricing.html"):
        content = (STATIC / name).read_text(encoding="utf-8")
        assert 'data-i18n="navKisa">Kisa Ⓚ</a>' in content, name


def test_market_and_battle_currency_amounts():
    dashboard = (STATIC / "dashboard.js").read_text(encoding="utf-8")
    battle = (STATIC / "battle_site.js").read_text(encoding="utf-8")
    pricing = (STATIC / "pricing.html").read_text(encoding="utf-8")
    assert '${plant.rental_price_kisa} Ⓚ' in dashboard
    assert '20 Ⓚ' in pricing and '30 Ⓚ' in pricing
    assert "price+\" Ⓚ\"" in battle
