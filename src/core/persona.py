"""Persona-based fingerprint generation.

A persona is a coherent digital portrait (age, gender, occupation, income
bracket, country) that DRIVES the fingerprint fields. Instead of generating
a fingerprint and hoping the fields are plausible together, we generate the
persona first, then derive every fingerprint field from it — the way a real
user's device would reflect who they are and where they live.

Examples:
  - developer, 28M, US, high income → high hardware_concurrency (16+),
    developer fonts (Consolas, Cascadia Code), en-US, fast connection,
    recent Chrome UA, large screen (2 monitors).
  - retiree, 68F, UK, medium income → older UA version, larger default fonts
    (accessibility), en-GB, moderate hardware (4 cores), home wifi.
  - student, 21F, DE, low income → laptop-class hardware (8 cores, 8GB),
    de-DE locale, university wifi, mid-range GPU.

This module is rule-based (no LLM call) — it's a lookup table of persona
traits → fingerprint field constraints, applied on top of the base
generation (template or corpus).
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from .fingerprint import Fingerprint, generate_fingerprint


@dataclass
class Persona:
    """A coherent digital portrait."""
    age: int
    gender: str                    # "M" | "F"
    occupation: str                # e.g. "developer", "student", "retiree", "designer"
    income_bracket: str            # "low" | "medium" | "high"
    country: str                   # ISO 3166-1 alpha-2, e.g. "US", "GB", "DE"
    device_type: str = "desktop"   # "desktop" | "laptop"
    name: str = ""                 # optional label


# Occupation → trait constraints
_OCCUPATION_TRAITS: Dict[str, Dict[str, Any]] = {
    "developer": {
        "hardware_concurrency": (12, 32),
        "device_memory": (16, 64),
        "screen_width": (1920, 3840),
        "screen_height": (1080, 2160),
        "fonts_extra": ["Consolas", "Cascadia Code", "JetBrains Mono", "Fira Code", "Source Code Pro"],
        "connection_downlink": (50.0, 300.0),
        "ua_recency": "high",  # latest Chrome
    },
    "student": {
        "hardware_concurrency": (4, 12),
        "device_memory": (8, 16),
        "screen_width": (1366, 1920),
        "screen_height": (768, 1080),
        "fonts_extra": ["Calibri", "Segoe UI"],
        "connection_downlink": (10.0, 100.0),
        "ua_recency": "medium",
    },
    "retiree": {
        "hardware_concurrency": (2, 8),
        "device_memory": (4, 8),
        "screen_width": (1366, 1920),
        "screen_height": (768, 1080),
        "fonts_extra": ["Arial", "Times New Roman", "Georgia"],
        "connection_downlink": (5.0, 50.0),
        "ua_recency": "low",  # older Chrome
    },
    "designer": {
        "hardware_concurrency": (8, 16),
        "device_memory": (16, 32),
        "screen_width": (1920, 2560),
        "screen_height": (1080, 1600),
        "fonts_extra": ["Helvetica Neue", "Avenir", "Futura", "Gill Sans"],
        "connection_downlink": (50.0, 200.0),
        "ua_recency": "medium",
    },
    "office_worker": {
        "hardware_concurrency": (4, 12),
        "device_memory": (8, 16),
        "screen_width": (1920, 2560),
        "screen_height": (1080, 1440),
        "fonts_extra": ["Calibri", "Segoe UI", "Arial"],
        "connection_downlink": (20.0, 100.0),
        "ua_recency": "medium",
    },
}

# Country → (timezone, locale, languages, accept_language)
_COUNTRY_LOCALE: Dict[str, Tuple[str, str, List[str], str]] = {
    "US": ("America/New_York", "en-US", ["en-US", "en"], "en-US,en;q=0.9"),
    "GB": ("Europe/London", "en-GB", ["en-GB", "en"], "en-GB,en;q=0.9"),
    "DE": ("Europe/Berlin", "de-DE", ["de-DE", "de", "en-US", "en"], "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7"),
    "FR": ("Europe/Paris", "fr-FR", ["fr-FR", "fr", "en-US", "en"], "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7"),
    "ES": ("Europe/Madrid", "es-ES", ["es-ES", "es", "en-US", "en"], "es-ES,es;q=0.9,en-US;q=0.8,en;q=0.7"),
    "IT": ("Europe/Rome", "it-IT", ["it-IT", "it", "en-US", "en"], "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7"),
    "BR": ("America/Sao_Paulo", "pt-BR", ["pt-BR", "pt", "en-US", "en"], "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7"),
    "RU": ("Europe/Moscow", "ru-RU", ["ru-RU", "ru", "en-US", "en"], "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7"),
    "JP": ("Asia/Tokyo", "ja-JP", ["ja-JP", "ja", "en-US", "en"], "ja-JP,ja;q=0.9,en-US;q=0.8,en;q=0.7"),
    "KR": ("Asia/Seoul", "ko-KR", ["ko-KR", "ko", "en-US", "en"], "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7"),
    "CN": ("Asia/Shanghai", "zh-CN", ["zh-CN", "zh", "en-US", "en"], "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7"),
    "AU": ("Australia/Sydney", "en-AU", ["en-AU", "en"], "en-AU,en;q=0.9"),
    "CA": ("America/Toronto", "en-CA", ["en-CA", "en", "fr-CA"], "en-CA,en;q=0.9,fr-CA;q=0.8"),
}

# Age → UA recency preference (younger → newer, older → slightly older)
def _ua_recency_for_age(age: int, occupation_recency: str) -> str:
    if age < 25:
        return "high"
    if age < 45:
        return occupation_recency
    return "low" if occupation_recency != "high" else "medium"


# Device type → screen constraints
_DEVICE_SCREEN: Dict[str, Tuple[Tuple[int, int], Tuple[int, int]]] = {
    "desktop": ((1920, 3840), (1080, 2160)),
    "laptop": ((1366, 2560), (768, 1600)),
}


def generate_persona(
    *,
    age: Optional[int] = None,
    gender: Optional[str] = None,
    occupation: Optional[str] = None,
    income_bracket: Optional[str] = None,
    country: Optional[str] = None,
    device_type: Optional[str] = None,
    seed: Optional[str] = None,
) -> Persona:
    """Generate a coherent persona. Any unspecified field is randomized."""
    rng = random.Random(seed)

    if occupation is None:
        occupation = rng.choice(list(_OCCUPATION_TRAITS.keys()))
    if country is None:
        country = rng.choice(list(_COUNTRY_LOCALE.keys()))
    if age is None:
        # Age distribution skewed by occupation
        if occupation == "retiree":
            age = rng.randint(60, 78)
        elif occupation == "student":
            age = rng.randint(18, 26)
        elif occupation == "developer":
            age = rng.randint(22, 42)
        else:
            age = rng.randint(22, 55)
    if gender is None:
        gender = rng.choice(["M", "F"])
    if income_bracket is None:
        # Income correlated with occupation and age
        if occupation == "retiree":
            income_bracket = rng.choice(["medium", "medium", "high"])
        elif occupation == "student":
            income_bracket = "low"
        elif occupation == "developer":
            income_bracket = rng.choice(["medium", "high", "high"])
        else:
            income_bracket = rng.choice(["low", "medium", "high"])
    if device_type is None:
        # Occupation/age hints: students and retirees more often laptop
        if occupation in ("student", "retiree") and age > 55:
            device_type = "laptop"
        elif occupation == "student":
            device_type = "laptop"
        else:
            device_type = "desktop" if rng.random() < 0.6 else "laptop"

    return Persona(
        age=age,
        gender=gender,
        occupation=occupation,
        income_bracket=income_bracket,
        country=country,
        device_type=device_type,
    )


def apply_persona(fp: Fingerprint, persona: Persona, seed: Optional[str] = None) -> Fingerprint:
    """Derive fingerprint fields from a persona, mutating the fingerprint in place.

    The persona drives: locale, timezone, languages, UA recency, hardware,
    screen, fonts, connection speed. Fields NOT driven by persona (canvas/
    audio noise, webgl vendor, plugins) are left as-is.
    """
    rng = random.Random(seed)
    traits = _OCCUPATION_TRAITS.get(persona.occupation, _OCCUPATION_TRAITS["office_worker"])

    # Locale/timezone/languages from country
    tz, locale, langs, accept = _COUNTRY_LOCALE.get(persona.country, _COUNTRY_LOCALE["US"])
    fp.timezone = tz
    fp.locale = locale
    fp.languages = langs
    fp.accept_language = accept

    # Hardware from occupation
    hc_min, hc_max = traits["hardware_concurrency"]
    dm_min, dm_max = traits["device_memory"]
    fp.hardware_concurrency = rng.randint(hc_min, hc_max)
    fp.device_memory = rng.randint(dm_min, dm_max)

    # Screen from device_type + occupation
    sw_range, sh_range = _DEVICE_SCREEN.get(persona.device_type, _DEVICE_SCREEN["desktop"])
    occ_sw_min, occ_sw_max = traits["screen_width"]
    occ_sh_min, occ_sh_max = traits["screen_height"]
    fp.screen_width = rng.randint(max(sw_range[0], occ_sw_min), min(sw_range[1], occ_sw_max))
    fp.screen_height = rng.randint(max(sh_range[0], occ_sh_min), min(sh_range[1], occ_sh_max))
    fp.inner_width = fp.screen_width
    fp.inner_height = fp.screen_height - 83  # Chrome chrome height
    fp.avail_screen_width = fp.screen_width
    fp.avail_screen_height = fp.screen_height - 40
    fp.pixel_ratio = 2.0 if persona.device_type == "laptop" and fp.screen_width > 2000 else 1.0

    # Fonts: base OS pool + occupation extras
    from .fingerprint import _FONTS_BY_OS
    os_family = "windows" if fp.platform == "Win32" else "macos" if fp.platform == "MacIntel" else "linux"
    base_fonts = list(_FONTS_BY_OS.get(os_family, _FONTS_BY_OS["windows"]))
    extras = [f for f in traits.get("fonts_extra", []) if f not in base_fonts]
    # Keep a subset of base + all extras (occupation signature)
    keep = rng.sample(base_fonts, min(len(base_fonts), rng.randint(10, 20)))
    fp.fonts = sorted(set(keep + extras))

    # Connection speed from occupation
    dl_min, dl_max = traits["connection_downlink"]
    fp.connection_downlink = round(rng.uniform(dl_min, dl_max), 1)
    fp.connection_rtt = rng.randint(10, 80)
    fp.connection_type = "ethernet" if persona.device_type == "desktop" else "wifi"

    # UA recency: regenerate UA with age-appropriate Chrome version
    recency = _ua_recency_for_age(persona.age, traits.get("ua_recency", "medium"))
    # Map recency to Chrome version range (approximate, 2026)
    if recency == "high":
        chrome_version = f"13{rng.randint(0, 1)}.0.0.0"
    elif recency == "medium":
        chrome_version = f"12{rng.randint(5, 9)}.0.0.0"
    else:
        chrome_version = f"12{rng.randint(0, 4)}.0.0.0"
    # Rebuild UA with the version (keep platform/OS coherent)
    if fp.platform == "Win32":
        fp.user_agent = f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{chrome_version} Safari/537.36"
    elif fp.platform == "MacIntel":
        fp.user_agent = f"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{chrome_version} Safari/537.36"
    else:
        fp.user_agent = f"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{chrome_version} Safari/537.36"

    # Geo: align geolocation with country (if spoofing enabled)
    if fp.spoof_geolocation:
        from .geo import country_to_coords
        coords = country_to_coords(persona.country)
        if coords:
            fp.geo_latitude, fp.geo_longitude = coords
            fp.geo_accuracy = rng.randint(20, 100)

    return fp


def generate_with_persona(
    persona: Optional[Persona] = None,
    *,
    os_family: str = "windows",
    seed: Optional[str] = None,
    use_corpus: bool = True,
) -> Tuple[Fingerprint, Persona]:
    """Generate a fingerprint driven by a persona.

    Returns (fingerprint, persona) so the caller can inspect the portrait.
    If persona is None, one is generated randomly.
    """
    if persona is None:
        persona = generate_persona(seed=seed)
    fp = generate_fingerprint(seed=seed, os_family=os_family, use_corpus=use_corpus)
    fp = apply_persona(fp, persona, seed=seed)
    return fp, persona


def persona_to_dict(p: Persona) -> Dict[str, Any]:
    return {
        "age": p.age,
        "gender": p.gender,
        "occupation": p.occupation,
        "income_bracket": p.income_bracket,
        "country": p.country,
        "device_type": p.device_type,
    }
