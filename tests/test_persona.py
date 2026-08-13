"""Tests for persona-driven fingerprint generation."""
from src.core.fingerprint import Fingerprint, generate_fingerprint
from src.core.persona import (
    Persona,
    apply_persona,
    generate_persona,
    generate_with_persona,
    persona_to_dict,
)


def test_generate_persona_returns_valid():
    p = generate_persona(seed="p1")
    assert p.age >= 16
    assert p.gender in ("M", "F")
    assert p.occupation in ("developer", "student", "retiree", "designer", "office_worker")
    assert p.income_bracket in ("low", "medium", "high")
    assert p.country
    assert p.device_type in ("desktop", "laptop")


def test_persona_retiree_age_range():
    p = generate_persona(occupation="retiree", seed="r1")
    assert p.age >= 60


def test_persona_student_age_range():
    p = generate_persona(occupation="student", seed="s1")
    assert 18 <= p.age <= 26


def test_persona_developer_high_hardware():
    p = generate_persona(occupation="developer", income_bracket="high", seed="d1")
    fp, _ = generate_with_persona(p, seed="d1")
    assert fp.hardware_concurrency >= 12
    assert fp.device_memory >= 16


def test_persona_country_drives_locale():
    p = generate_persona(country="DE", seed="de1")
    fp, _ = generate_with_persona(p, seed="de1")
    assert fp.locale == "de-DE"
    assert fp.timezone == "Europe/Berlin"
    assert "de-DE" in fp.languages or "de" in fp.languages


def test_persona_ua_version_varies_with_age():
    """Younger personas get newer Chrome UA versions than retirees."""
    young = generate_persona(age=22, occupation="student", seed="y1")
    old = generate_persona(age=70, occupation="retiree", seed="o1")
    fp_y, _ = generate_with_persona(young, seed="y1")
    fp_o, _ = generate_with_persona(old, seed="o1")
    # Extract Chrome version from UA
    import re
    vy = int(re.search(r"Chrome/(\d+)", fp_y.user_agent).group(1))
    vo = int(re.search(r"Chrome/(\d+)", fp_o.user_agent).group(1))
    assert vy >= vo  # younger gets >= version


def test_persona_deterministic_with_seed():
    a, _ = generate_with_persona(seed="det1")
    b, _ = generate_with_persona(seed="det1")
    assert a.user_agent == b.user_agent
    assert a.timezone == b.timezone
    assert a.hardware_concurrency == b.hardware_concurrency


def test_persona_fingerprint_is_coherent():
    """Persona-driven fingerprint should pass basic coherence checks."""
    fp, _ = generate_with_persona(seed="coh1")
    assert fp.user_agent.startswith("Mozilla/5.0")
    assert fp.platform in ("Win32", "MacIntel", "Linux x86_64")
    assert fp.hardware_concurrency > 0
    assert fp.screen_width > 0
    assert fp.fonts
    assert fp.timezone
    assert fp.locale


def test_apply_persona_to_existing_fingerprint():
    """apply_persona mutates an existing fingerprint in place."""
    fp = generate_fingerprint(seed="base", os_family="windows")
    original_ua = fp.user_agent
    p = Persona(age=30, gender="M", occupation="developer", income_bracket="high", country="US", device_type="desktop")
    fp2 = apply_persona(fp, p, seed="apply1")
    assert fp2.user_agent != original_ua or fp2.hardware_concurrency >= 12
    assert fp2.locale == "en-US"
    assert fp2.timezone == "America/New_York"


def test_persona_to_dict():
    p = generate_persona(seed="d1")
    d = persona_to_dict(p)
    for key in ("age", "gender", "occupation", "income_bracket", "country", "device_type"):
        assert key in d
