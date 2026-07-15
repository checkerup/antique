"""Tests for bulk AdsPower-backup import."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from src.core.backup_import import import_adspower_backup_root, prepare_backup_profile_payload
from src.core.cookie import apply_initial_state_to_user_data, import_adspower_profile
from src.core.profile import ProfileStore


def _make_network_cookies_db(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE cookies(
          creation_utc INTEGER NOT NULL DEFAULT 0,
          host_key TEXT NOT NULL,
          top_frame_site_key TEXT NOT NULL DEFAULT '',
          name TEXT NOT NULL,
          value TEXT NOT NULL,
          encrypted_value BLOB DEFAULT '',
          path TEXT NOT NULL,
          expires_utc INTEGER NOT NULL,
          is_secure INTEGER NOT NULL,
          is_httponly INTEGER NOT NULL,
          samesite INTEGER NOT NULL DEFAULT 0,
          last_access_utc INTEGER NOT NULL DEFAULT 0,
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
        """
    )
    win_delta = 11644473600
    expires_us = int((1700000000 + win_delta) * 1_000_000)
    conn.execute(
        "INSERT INTO cookies(host_key, name, value, path, expires_utc, is_secure, is_httponly) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (".example.com", "sid", "cookie-db", "/", expires_us, 1, 1),
    )
    conn.commit()
    conn.close()
    return path


def _make_backup_profile(root: Path, user_id: str) -> Path:
    profile_dir = root / user_id / "Default"
    (profile_dir / "Local Storage" / "leveldb").mkdir(parents=True, exist_ok=True)
    (profile_dir / "Local Storage" / "leveldb" / "CURRENT").write_text("MANIFEST-000001\n")
    (profile_dir / "Local Storage" / "leveldb" / "MANIFEST-000001").write_text("fake")
    (profile_dir / "WebStorage" / "99" / "IndexedDB" / "indexeddb.leveldb").mkdir(parents=True, exist_ok=True)
    (profile_dir / "WebStorage" / "99" / "IndexedDB" / "indexeddb.leveldb" / "CURRENT").write_text("MANIFEST-000001\n")
    _make_network_cookies_db(profile_dir / "Network" / "Cookies")
    return profile_dir.parent


def test_import_adspower_profile_supports_network_cookies(tmp_path: Path):
    profile_root = _make_backup_profile(tmp_path, "abc12345")
    cookies = import_adspower_profile(profile_root)
    assert len(cookies) == 1
    assert cookies[0].name == "sid"
    assert cookies[0].value == "cookie-db"


def test_apply_initial_state_copies_webstorage(tmp_path: Path):
    profile_root = _make_backup_profile(tmp_path, "abc12345")
    source_default = profile_root / "Default"
    user_data = tmp_path / "user_data"
    copied = apply_initial_state_to_user_data(source_default, user_data)
    assert "local_storage" in copied
    assert "webstorage" in copied
    assert (user_data / "Default" / "WebStorage" / "99" / "IndexedDB" / "indexeddb.leveldb" / "CURRENT").exists()


def test_prepare_backup_profile_payload_prefers_json_cookies(tmp_path: Path):
    root = tmp_path / "backup"
    root.mkdir()
    _make_backup_profile(root, "abc12345")
    (root / "json_cookies").mkdir(parents=True, exist_ok=True)
    (root / "json_cookies" / "abc12345_cookies.json").write_text(
        json.dumps([
            {
                "name": "sid",
                "value": "cookie-json",
                "domain": ".example.com",
                "path": "/",
                "secure": True,
                "httpOnly": True,
            }
        ]),
        encoding="utf-8",
    )
    payload = prepare_backup_profile_payload(
        root,
        {
            "user_id": "abc12345",
            "name": "Imported profile",
            "group_id": "10",
            "user_proxy_config": {"proxy_soft": "other", "proxy_type": "socks5", "proxy_host": "127.0.0.1", "proxy_port": "9000"},
            "fbcc_user_tag": ["warm"],
        },
    )
    assert payload["cookie_source"] == "json"
    assert payload["cookies"][0]["value"] == "cookie-json"
    assert payload["proxy"]["proxy_type"] == "socks5"
    assert payload["proxy"]["proxy_port"] == 9000
    assert payload["import_source_path"].endswith("abc12345")


def test_import_adspower_backup_root_creates_profiles(tmp_path: Path):
    root = tmp_path / "backup"
    root.mkdir()
    _make_backup_profile(root, "abc12345")
    _make_backup_profile(root, "def67890")
    (root / "json_cookies").mkdir(parents=True, exist_ok=True)
    (root / "json_cookies" / "abc12345_cookies.json").write_text(
        json.dumps([
            {"name": "a", "value": "1", "domain": ".example.com", "path": "/"}
        ]),
        encoding="utf-8",
    )
    (root / "all_profiles_list.json").write_text(
        json.dumps(
            [
                {
                    "user_id": "abc12345",
                    "name": "Alpha",
                    "group_id": "1",
                    "remark": "first",
                    "user_proxy_config": {"proxy_soft": "other", "proxy_type": "http", "proxy_host": "10.0.0.1", "proxy_port": "8080"},
                    "fbcc_user_tag": ["team-a"],
                },
                {
                    "user_id": "def67890",
                    "name": "",
                    "group_id": "2",
                    "remark": "",
                    "user_proxy_config": {"proxy_soft": "no_proxy"},
                    "fbcc_user_tag": [],
                },
            ]
        ),
        encoding="utf-8",
    )

    store = ProfileStore(tmp_path / "profiles.db")
    summary = import_adspower_backup_root(root, store)
    assert summary["processed"] == 2
    assert summary["imported_count"] == 2
    assert summary["error_count"] == 0
    assert summary["cookie_sources"]["json"] == 1
    assert summary["full_state_profiles"] == 2

    alpha = store.get("abc12345")
    beta = store.get("def67890")
    assert alpha is not None and beta is not None
    assert alpha.name == "Alpha"
    assert alpha.proxy["proxy_type"] == "http"
    assert alpha.cookies[0]["value"] == "1"
    assert alpha.import_source_path.endswith("abc12345")
    assert beta.name == "Imported def67890"
    assert beta.proxy["proxy_type"] == "direct"


def test_prepare_payload_falls_back_when_json_cookies_are_broken(tmp_path: Path):
    root = tmp_path / "backup"
    root.mkdir()
    _make_backup_profile(root, "abc12345")
    (root / "json_cookies").mkdir()
    (root / "json_cookies" / "abc12345_cookies.json").write_text("{broken", encoding="utf-8")
    payload = prepare_backup_profile_payload(root, {
        "user_id": "abc12345",
        "user_proxy_config": {"proxy_soft": "no_proxy"},
    })
    assert payload["cookie_source"] == "profile_dir"
    assert payload["cookies"][0]["value"] == "cookie-db"


def test_prepare_payload_invalid_proxy_port_becomes_direct(tmp_path: Path):
    root = tmp_path / "backup"
    root.mkdir()
    payload = prepare_backup_profile_payload(root, {
        "user_id": "abc12345",
        "user_proxy_config": {"proxy_type": "socks5", "proxy_host": "x", "proxy_port": "bad"},
    })
    assert payload["proxy"]["proxy_type"] == "direct"


def test_import_adspower_backup_root_skips_existing_without_overwrite(tmp_path: Path):
    root = tmp_path / "backup"
    root.mkdir()
    _make_backup_profile(root, "abc12345")
    (root / "all_profiles_list.json").write_text(
        json.dumps([
            {"user_id": "abc12345", "name": "Alpha", "group_id": "1", "user_proxy_config": {"proxy_soft": "no_proxy"}}
        ]),
        encoding="utf-8",
    )

    store = ProfileStore(tmp_path / "profiles.db")
    store.create(name="Existing", user_id="abc12345")
    summary = import_adspower_backup_root(root, store, overwrite=False)
    assert summary["imported_count"] == 0
    assert summary["skipped_count"] == 1
    assert store.get("abc12345").name == "Existing"
