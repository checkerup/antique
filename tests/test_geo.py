"""Tests for geolocation / timezone / locale matching from proxy country."""
import pytest

from src.core.fingerprint import Fingerprint, build_init_script, generate_fingerprint
from src.core.geo import (
    DEFAULT_COUNTRY,
    GeoProfile,
    apply_geo_to_fingerprint,
    country_for_timezone,
    geo_for_country,
    geo_from_proxy,
    supported_countries,
)


# ---------------------------------------------------------------------------
# Country table
# ---------------------------------------------------------------------------


def test_supported_countries_nonempty_and_sorted():
    cs = supported_countries()
    assert "US" in cs and "DE" in cs and "RU" in cs
    assert cs == sorted(cs)


def test_geo_for_known_country():
    g = geo_for_country("DE")
    assert g.country == "DE"
    assert g.timezone == "Europe/Berlin"
    assert g.locale == "de-DE"
    assert g.languages[0] == "de-DE"
    assert 47 < g.latitude < 55
    assert 5 < g.longitude < 16


def test_geo_for_country_is_case_insensitive():
    assert geo_for_country("de").country == "DE"
    assert geo_for_country("  us  ").country == "US"


def test_geo_for_unknown_falls_back_to_default():
    g = geo_for_country("ZZ")
    assert g.country == DEFAULT_COUNTRY
    g2 = geo_for_country("")
    assert g2.country == DEFAULT_COUNTRY


def test_country_for_timezone_reverse_lookup():
    assert country_for_timezone("Europe/Moscow") == "RU"
    assert country_for_timezone("Asia/Tokyo") == "JP"
    assert country_for_timezone("Mars/Olympus") is None


# ---------------------------------------------------------------------------
# Proxy derivation
# ---------------------------------------------------------------------------


def test_geo_from_proxy_country_override_wins():
    g = geo_from_proxy({"proxy_host": "1.2.3.4"}, country_override="FR")
    assert g.country == "FR"


def test_geo_from_proxy_uses_lookup_callable():
    def fake_lookup(host):
        assert host == "9.9.9.9"
        return "JP"
    g = geo_from_proxy({"proxy_host": "9.9.9.9"}, ip_country_lookup=fake_lookup)
    assert g.country == "JP"


def test_geo_from_proxy_uses_embedded_country():
    g = geo_from_proxy({"proxy_host": "1.2.3.4", "country": "GB"})
    assert g.country == "GB"


def test_geo_from_proxy_none_when_undeterminable():
    assert geo_from_proxy(None) is None
    assert geo_from_proxy({"proxy_host": "1.2.3.4"}) is None


# ---------------------------------------------------------------------------
# Applying to fingerprint
# ---------------------------------------------------------------------------


def test_apply_geo_makes_fingerprint_coherent():
    fp = generate_fingerprint(seed="geo")
    g = geo_for_country("JP")
    apply_geo_to_fingerprint(fp, g)
    assert fp.timezone == "Asia/Tokyo"
    assert fp.locale == "ja-JP"
    assert fp.languages[0] == "ja-JP"
    assert fp.accept_language.startswith("ja-JP")
    assert fp.spoof_geolocation is True
    assert fp.geo_latitude == g.latitude
    assert fp.geo_longitude == g.longitude


def test_apply_geo_returns_same_object():
    fp = Fingerprint()
    out = apply_geo_to_fingerprint(fp, geo_for_country("US"))
    assert out is fp


# ---------------------------------------------------------------------------
# Init-script injection
# ---------------------------------------------------------------------------


def test_init_script_contains_geolocation_patch_when_enabled():
    fp = generate_fingerprint(seed="g2")
    apply_geo_to_fingerprint(fp, geo_for_country("FR"))
    js = build_init_script(fp)
    assert "getCurrentPosition" in js
    assert "watchPosition" in js
    assert '"spoof_geolocation":true' in js
    # Coordinates inlined
    assert str(fp.geo_latitude) in js


def test_init_script_no_geo_when_disabled():
    fp = generate_fingerprint(seed="g3")
    # default: spoof_geolocation is False
    assert fp.spoof_geolocation is False
    js = build_init_script(fp)
    assert '"spoof_geolocation":false' in js


def test_launch_options_sets_geolocation_when_enabled():
    from src.core.fingerprint import to_playwright_launch_options
    fp = generate_fingerprint(seed="g4")
    apply_geo_to_fingerprint(fp, geo_for_country("SG"))
    opts = to_playwright_launch_options(fp)
    assert "geolocation" in opts
    assert opts["geolocation"]["latitude"] == fp.geo_latitude
    assert "geolocation" in opts["permissions"]


def test_launch_options_no_geolocation_by_default():
    from src.core.fingerprint import to_playwright_launch_options
    fp = generate_fingerprint(seed="g5")
    opts = to_playwright_launch_options(fp)
    assert "geolocation" not in opts
