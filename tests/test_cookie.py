"""Tests for cookie import/export across formats."""
import json
import sqlite3
import tempfile
import zipfile
from pathlib import Path

import pytest

from src.core.cookie import (
    Cookie,
    export_cookies_json,
    export_cookies_netscape,
    import_adspower_profile,
    import_cookies,
    import_cookies_json,
    import_cookies_netscape,
)


# ---------------------------------------------------------------------------
# Netscape
# ---------------------------------------------------------------------------


NETSCAPE_SAMPLE = """# Netscape HTTP Cookie File
# https://curl.haxx.se/rfc/cookie_spec.html

.example.com\tTRUE\t/\tFALSE\t9999999999\tfoo\tbar
.session.example\tFALSE\t/\tFALSE\t0\tsess\tabc123
"""


def test_netscape_import_basic():
    cookies = import_cookies_netscape(NETSCAPE_SAMPLE)
    assert len(cookies) == 2
    foo = next(c for c in cookies if c.name == "foo")
    assert foo.value == "bar"
    assert foo.domain == ".example.com"
    assert foo.path == "/"
    assert foo.secure is False
    assert foo.expires == 9999999999
    sess = next(c for c in cookies if c.name == "sess")
    assert sess.expires == 0  # session cookie
    assert sess.domain == ".session.example"


def test_netscape_handles_comments():
    cookies = import_cookies_netscape("# this is a comment\n\n")
    assert cookies == []


def test_netscape_roundtrip():
    cookies = [
        Cookie(name="k1", value="v1", domain=".x.com", path="/", expires=9999999999, secure=False),
        Cookie(name="k2", value="v2", domain=".y.com", path="/api", expires=0, secure=True),
    ]
    text = export_cookies_netscape(cookies)
    parsed = import_cookies_netscape(text)
    assert len(parsed) == 2
    # Re-export should be identical
    text2 = export_cookies_netscape(parsed)
    assert text.strip() == text2.strip()


# ---------------------------------------------------------------------------
# JSON (Playwright / CDP)
# ---------------------------------------------------------------------------


PLAYWRIGHT_JSON = [
    {
        "name": "auth",
        "value": "token123",
        "domain": ".example.com",
        "path": "/",
        "expires": 1700000000.0,
        "httpOnly": True,
        "secure": True,
        "sameSite": "Strict",
    },
    {
        "name": "pref",
        "value": "dark",
        "domain": "app.example.com",
        "path": "/",
        "expires": -1,
        "httpOnly": False,
        "secure": False,
        "sameSite": "Lax",
    },
]


def test_json_import_list():
    cookies = import_cookies_json(PLAYWRIGHT_JSON)
    assert len(cookies) == 2
    auth = next(c for c in cookies if c.name == "auth")
    assert auth.value == "token123"
    assert auth.http_only is True
    assert auth.secure is True
    assert auth.same_site == "Strict"


def test_json_import_from_string():
    cookies = import_cookies_json(json.dumps(PLAYWRIGHT_JSON))
    assert len(cookies) == 2


def test_json_export_roundtrip():
    cookies = import_cookies_json(PLAYWRIGHT_JSON)
    text = export_cookies_json(cookies)
    parsed = import_cookies_json(text)
    assert len(parsed) == 2
    # Names/values match
    assert {c.name for c in parsed} == {c.name for c in cookies}


# ---------------------------------------------------------------------------
# SameSite normalisation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("raw,expected", [
    ("Strict", "Strict"),
    ("strict", "Strict"),
    ("Lax", "Lax"),
    ("lax", "Lax"),
    ("None", "None"),
    ("no_same_site", "None"),
    ("", "Lax"),
    (None, "Lax"),
])
def test_samesite_normalisation(raw, expected):
    cookies = import_cookies_json([
        {"name": "x", "value": "y", "sameSite": raw}
    ])
    assert cookies[0].same_site == expected


# ---------------------------------------------------------------------------
# AdsPower .adb import
# ---------------------------------------------------------------------------


def _make_synthetic_chrome_cookies_db(path: Path) -> Path:
    """Create a minimal Chrome Cookies sqlite file with two cookies."""
    conn = sqlite3.connect(path)
    conn.executescript("""
        CREATE TABLE meta(key LONGVARCHAR NOT NULL UNIQUE PRIMARY KEY, value LONGVARCHAR);
        INSERT INTO meta VALUES('version', '24');
        INSERT INTO meta VALUES('last_compatible_version', '24');

        CREATE TABLE cookies(
          creation_utc INTEGER NOT NULL,
          host_key TEXT NOT NULL,
          top_frame_site_key TEXT NOT NULL DEFAULT '',
          name TEXT NOT NULL,
          value TEXT NOT NULL,
          encrypted_value BLOB DEFAULT '',
          path TEXT NOT NULL,
          expires_utc INTEGER NOT NULL,
          is_secure INTEGER NOT NULL,
          is_httponly INTEGER NOT NULL,
          samesite INTEGER NOT NULL,
          last_access_utc INTEGER NOT NULL,
          has_expires INTEGER NOT NULL DEFAULT 1,
          is_persistent INTEGER NOT NULL DEFAULT 1,
          priority INTEGER NOT NULL DEFAULT 1,
          source_scheme INTEGER NOT NULL DEFAULT 1,
          source_port INTEGER NOT NULL DEFAULT -1,
          last_update_utc INTEGER NOT NULL DEFAULT 0,
          source_type INTEGER NOT NULL DEFAULT 0,
          has_cross_site_ancestor INTEGER NOT NULL DEFAULT 0,
          PRIMARY KEY (host_key, top_frame_site_key, name, path, source_scheme, source_port)
        );
    """)
    # Chrome epoch offset: microseconds since 1601-01-01
    # expires_utc = (unix_ts + 11644473600) * 1_000_000
    # For expires = 1700000000 (Unix): micro = (1700000000 + 11644473600) * 1e6
    WIN_DELTA = 11644473600
    expires_us_persistent = int((1700000000 + WIN_DELTA) * 1_000_000)
    expires_us_session = 0
    conn.execute(
        "INSERT INTO cookies(creation_utc, host_key, name, value, path, expires_utc, is_secure, is_httponly, samesite, last_access_utc) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (0, ".example.com", "persistent", "yes-value", "/", expires_us_persistent, 1, 1, 0, 0),
    )
    conn.execute(
        "INSERT INTO cookies(creation_utc, host_key, name, value, path, expires_utc, is_secure, is_httponly, samesite, last_access_utc) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (0, ".example.com", "session", "sess-value", "/", expires_us_session, 0, 0, 1, 0),
    )
    conn.commit()
    conn.close()
    return path


def test_adspower_import_from_directory(tmp_path):
    # Mimic an AdsPower bundle: <root>/Default/Cookies
    profile_dir = tmp_path / "user_x1234"
    default_dir = profile_dir / "Default"
    default_dir.mkdir(parents=True)
    _make_synthetic_chrome_cookies_db(default_dir / "Cookies")
    cookies = import_adspower_profile(profile_dir)
    assert len(cookies) == 2
    names = {c.name for c in cookies}
    assert names == {"persistent", "session"}
    persistent = next(c for c in cookies if c.name == "persistent")
    assert persistent.value == "yes-value"
    assert persistent.secure is True
    assert persistent.http_only is True
    # Persistent cookies get a real expires; session cookies get -1
    assert persistent.expires > 0
    session = next(c for c in cookies if c.name == "session")
    assert session.expires == -1


def test_adspower_import_from_zip(tmp_path):
    profile_dir = tmp_path / "extract"
    default_dir = profile_dir / "Default"
    default_dir.mkdir(parents=True)
    cookies_db = _make_synthetic_chrome_cookies_db(default_dir / "Cookies")
    # Zip it
    zip_path = tmp_path / "profile.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.write(cookies_db, arcname="Default/Cookies")
    cookies = import_adspower_profile(zip_path)
    assert len(cookies) == 2


def test_import_cookies_auto_detect(tmp_path):
    # JSON
    p_json = tmp_path / "cookies.json"
    p_json.write_text(json.dumps(PLAYWRIGHT_JSON))
    cookies = import_cookies(p_json)
    assert len(cookies) == 2

    # Netscape
    p_txt = tmp_path / "cookies.txt"
    p_txt.write_text(NETSCAPE_SAMPLE)
    cookies = import_cookies(p_txt)
    assert len(cookies) == 2


def test_import_cookies_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        import_cookies(tmp_path / "nonexistent.json")


# ---------------------------------------------------------------------------
# Cookie.to_playwright
# ---------------------------------------------------------------------------


def test_cookie_to_playwright_shape():
    c = Cookie(
        name="k", value="v", domain=".x.com", path="/", expires=9999999999,
        http_only=True, secure=True, same_site="Lax",
    )
    out = c.to_playwright()
    assert out["name"] == "k"
    assert out["value"] == "v"
    assert out["domain"] == ".x.com"
    assert out["httpOnly"] is True
    assert out["secure"] is True
    assert out["sameSite"] == "Lax"