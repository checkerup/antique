"""Geolocation / timezone / locale matching from a proxy's exit country.

Every serious anti-detect browser (Dolphin, AdsPower, GoLogin, Undetectable,
Multilogin) auto-aligns the browser's timezone, locale, languages and
``navigator.geolocation`` to the **proxy's exit IP country**. A US proxy with
a Moscow timezone and ru-RU locale is an instant, trivial linkage signal.

This module is the local, offline equivalent. It maps an ISO country code (or
a best-effort guess from an IP via a caller-supplied lookup) to a coherent
``GeoProfile`` and applies it onto a ``Fingerprint``.

Everything here is pure Python with static tables so it is fully unit-testable
without network access. Actual IP->country resolution is left to the caller
(e.g. the proxy health-check already returns the exit IP); we accept either a
country code directly or an ``ip_country_lookup`` callable.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, List, Optional


@dataclass
class GeoProfile:
    """A coherent geo bundle for one country."""

    country: str            # ISO-3166 alpha-2, uppercase
    timezone: str           # IANA tz id
    locale: str             # BCP-47, e.g. en-US
    languages: List[str]    # navigator.languages
    latitude: float         # approximate city-level lat
    longitude: float        # approximate city-level lon
    accuracy: float = 50.0  # meters reported to the Geolocation API


# Country -> (timezone, locale, [languages], lat, lon).
# Coordinates point at the country's primary city so geolocation lands in-country.
_GEO_TABLE: Dict[str, tuple] = {
    "US": ("America/New_York", "en-US", ["en-US", "en"], 40.7128, -74.0060),
    "GB": ("Europe/London", "en-GB", ["en-GB", "en"], 51.5074, -0.1278),
    "DE": ("Europe/Berlin", "de-DE", ["de-DE", "de", "en"], 52.5200, 13.4050),
    "FR": ("Europe/Paris", "fr-FR", ["fr-FR", "fr", "en"], 48.8566, 2.3522),
    "ES": ("Europe/Madrid", "es-ES", ["es-ES", "es", "en"], 40.4168, -3.7038),
    "IT": ("Europe/Rome", "it-IT", ["it-IT", "it", "en"], 41.9028, 12.4964),
    "NL": ("Europe/Amsterdam", "nl-NL", ["nl-NL", "nl", "en"], 52.3676, 4.9041),
    "PL": ("Europe/Warsaw", "pl-PL", ["pl-PL", "pl", "en"], 52.2297, 21.0122),
    "RU": ("Europe/Moscow", "ru-RU", ["ru-RU", "ru", "en"], 55.7558, 37.6173),
    "UA": ("Europe/Kyiv", "uk-UA", ["uk-UA", "uk", "ru", "en"], 50.4501, 30.5234),
    "TR": ("Europe/Istanbul", "tr-TR", ["tr-TR", "tr", "en"], 41.0082, 28.9784),
    "BR": ("America/Sao_Paulo", "pt-BR", ["pt-BR", "pt", "en"], -23.5505, -46.6333),
    "CA": ("America/Toronto", "en-CA", ["en-CA", "en", "fr"], 43.6532, -79.3832),
    "MX": ("America/Mexico_City", "es-MX", ["es-MX", "es", "en"], 19.4326, -99.1332),
    "AR": ("America/Argentina/Buenos_Aires", "es-AR", ["es-AR", "es", "en"], -34.6037, -58.3816),
    "JP": ("Asia/Tokyo", "ja-JP", ["ja-JP", "ja", "en"], 35.6762, 139.6503),
    "KR": ("Asia/Seoul", "ko-KR", ["ko-KR", "ko", "en"], 37.5665, 126.9780),
    "CN": ("Asia/Shanghai", "zh-CN", ["zh-CN", "zh", "en"], 31.2304, 121.4737),
    "HK": ("Asia/Hong_Kong", "zh-HK", ["zh-HK", "zh", "en"], 22.3193, 114.1694),
    "SG": ("Asia/Singapore", "en-SG", ["en-SG", "en", "zh"], 1.3521, 103.8198),
    "IN": ("Asia/Kolkata", "en-IN", ["en-IN", "en", "hi"], 28.6139, 77.2090),
    "AU": ("Australia/Sydney", "en-AU", ["en-AU", "en"], -33.8688, 151.2093),
    "AE": ("Asia/Dubai", "ar-AE", ["ar-AE", "ar", "en"], 25.2048, 55.2708),
    "ZA": ("Africa/Johannesburg", "en-ZA", ["en-ZA", "en"], -26.2041, 28.0473),
    "SE": ("Europe/Stockholm", "sv-SE", ["sv-SE", "sv", "en"], 59.3293, 18.0686),
}

# Reverse index: timezone -> country, so we can infer a country when only a
# timezone is known (e.g. an already-configured fingerprint).
_TZ_TO_COUNTRY: Dict[str, str] = {v[0]: k for k, v in _GEO_TABLE.items()}

DEFAULT_COUNTRY = "US"


def supported_countries() -> List[str]:
    """Sorted list of ISO country codes we can align to."""
    return sorted(_GEO_TABLE)


def geo_for_country(country: str) -> GeoProfile:
    """Return a ``GeoProfile`` for an ISO alpha-2 country code.

    Unknown / empty codes fall back to ``DEFAULT_COUNTRY`` (US) so callers
    always get a usable, coherent profile.
    """
    code = (country or "").strip().upper()
    tz, locale, langs, lat, lon = _GEO_TABLE.get(code, _GEO_TABLE[DEFAULT_COUNTRY])
    resolved = code if code in _GEO_TABLE else DEFAULT_COUNTRY
    return GeoProfile(
        country=resolved,
        timezone=tz,
        locale=locale,
        languages=list(langs),
        latitude=lat,
        longitude=lon,
    )


def country_for_timezone(timezone: str) -> Optional[str]:
    """Best-effort reverse lookup: IANA timezone -> ISO country code."""
    return _TZ_TO_COUNTRY.get((timezone or "").strip())


def geo_from_proxy(
    proxy: Optional[Dict],
    *,
    ip_country_lookup: Optional[Callable[[str], Optional[str]]] = None,
    country_override: Optional[str] = None,
) -> Optional[GeoProfile]:
    """Derive a ``GeoProfile`` from a proxy config.

    Resolution order:
      1. ``country_override`` if given.
      2. ``ip_country_lookup(host)`` if a lookup callable is supplied.
      3. ``proxy['country']`` if the proxy dict already carries one.
    Returns ``None`` when no country can be determined (caller keeps the
    fingerprint's existing geo).
    """
    if country_override:
        return geo_for_country(country_override)
    if not proxy:
        return None
    host = proxy.get("proxy_host") or proxy.get("host") or ""
    if ip_country_lookup and host:
        cc = ip_country_lookup(host)
        if cc:
            return geo_for_country(cc)
    cc = proxy.get("country") or proxy.get("proxy_country")
    if cc:
        return geo_for_country(cc)
    return None


def apply_geo_to_fingerprint(fp, geo: GeoProfile):
    """Mutate a ``Fingerprint`` in place so tz/locale/languages/geo all agree.

    Returns the same fingerprint for chaining. Also enables geolocation
    spoofing and sets the coordinates.
    """
    fp.timezone = geo.timezone
    fp.locale = geo.locale
    fp.languages = list(geo.languages)
    primary = geo.languages[0] if geo.languages else geo.locale
    fp.accept_language = (
        f"{primary},{primary.split('-')[0]};q=0.9,en-US;q=0.8,en;q=0.7"
    )
    fp.geo_latitude = geo.latitude
    fp.geo_longitude = geo.longitude
    fp.geo_accuracy = geo.accuracy
    fp.spoof_geolocation = True
    return fp
