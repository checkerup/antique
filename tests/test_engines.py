"""Tests for the browser engine registry (src/core/engines.py) and its wiring
into the launcher's engine resolution.
"""
import pytest

from src.core.engines import (
    DEFAULT_ENGINE,
    EngineSpec,
    engine_keys,
    is_valid_engine,
    list_engines,
    resolve_engine,
    resolve_engine_for_profile,
)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


def test_registry_has_core_engines():
    keys = engine_keys()
    for k in ("chromium", "chrome", "edge", "firefox", "camoufox", "webkit"):
        assert k in keys


def test_default_engine_is_chromium():
    assert DEFAULT_ENGINE == "chromium"
    assert resolve_engine(DEFAULT_ENGINE).key == "chromium"


def test_list_engines_returns_specs():
    specs = list_engines()
    assert all(isinstance(e, EngineSpec) for e in specs)
    assert len(specs) == len(engine_keys())


def test_engine_bases_are_sane():
    by = {e.key: e for e in list_engines()}
    assert by["chromium"].base == "chromium"
    assert by["chrome"].base == "chromium" and by["chrome"].channel == "chrome"
    assert by["edge"].base == "chromium" and by["edge"].channel == "msedge"
    assert by["firefox"].base == "firefox"
    assert by["camoufox"].base == "firefox" and by["camoufox"].stealth == "deep"
    assert by["webkit"].base == "webkit"


def test_capabilities():
    by = {e.key: e for e in list_engines()}
    # Chromium engines support extensions + real CDP; others don't.
    assert by["chromium"].supports_extensions and by["chromium"].supports_cdp
    assert by["chrome"].supports_extensions
    assert not by["firefox"].supports_extensions
    assert not by["camoufox"].supports_cdp
    assert not by["webkit"].supports_extensions


def test_camoufox_needs_install():
    by = {e.key: e for e in list_engines()}
    assert by["camoufox"].needs_install
    assert "camoufox" in by["camoufox"].install_hint
    assert not by["chromium"].needs_install


def test_to_dict_shape():
    d = resolve_engine("camoufox").to_dict()
    assert set(d) >= {"key", "label", "base", "stealth", "needs_install", "supports_extensions", "supports_cdp"}


# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------


def test_is_valid_engine():
    assert is_valid_engine("chromium")
    assert is_valid_engine("CamouFox")   # case-insensitive
    assert not is_valid_engine("nonsense")
    assert not is_valid_engine("")


def test_resolve_aliases():
    assert resolve_engine("google-chrome").key == "chrome"
    assert resolve_engine("msedge").key == "edge"
    assert resolve_engine("safari").key == "webkit"
    assert resolve_engine("camo").key == "camoufox"


def test_resolve_unknown_falls_back():
    assert resolve_engine("totally-fake").key == "chromium"
    assert resolve_engine(None).key == "chromium"


def test_resolve_for_profile_priority():
    # explicit profile engine wins
    assert resolve_engine_for_profile("firefox", env={}).key == "firefox"
    # env used when no profile engine
    assert resolve_engine_for_profile(None, env={"ANTIDETECT_ENGINE": "camoufox"}).key == "camoufox"
    # profile engine beats env
    assert resolve_engine_for_profile("webkit", env={"ANTIDETECT_ENGINE": "camoufox"}).key == "webkit"
    # nothing set -> default
    assert resolve_engine_for_profile(None, env={}).key == "chromium"
    # invalid profile engine ignored -> env, then default
    assert resolve_engine_for_profile("bogus", env={"ANTIDETECT_ENGINE": "edge"}).key == "edge"
    assert resolve_engine_for_profile("bogus", env={}).key == "chromium"


# ---------------------------------------------------------------------------
# Launcher wiring
# ---------------------------------------------------------------------------


def test_launcher_get_engine_uses_registry(tmp_path):
    from src.core.profile import Profile, ProfileStore
    from src.core.browser import BrowserLauncher
    store = ProfileStore(db_path=tmp_path / "t.db")
    launcher = BrowserLauncher(store, data_root=tmp_path)

    assert launcher._get_engine(Profile(user_id="a", name="A")) == "chromium"
    p_ff = Profile(user_id="b", name="B", fingerprint={"browser_engine": "firefox"})
    assert launcher._get_engine(p_ff) == "firefox"
    p_bad = Profile(user_id="c", name="C", fingerprint={"browser_engine": "nope"})
    assert launcher._get_engine(p_bad) == "chromium"
    spec = launcher._resolve_engine_spec(Profile(user_id="d", name="D", fingerprint={"browser_engine": "camoufox"}))
    assert spec.key == "camoufox" and spec.base == "firefox"


def test_browser_engine_persists_on_fingerprint(tmp_path):
    from src.core.fingerprint import generate_fingerprint
    from src.core.profile import ProfileStore
    store = ProfileStore(db_path=tmp_path / "t.db")
    fp = generate_fingerprint(seed="x")
    fp.browser_engine = "camoufox"
    p = store.create(name="eng", fingerprint=fp)
    fetched = store.get(p.user_id)
    assert fetched.fingerprint["browser_engine"] == "camoufox"
