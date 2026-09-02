"""Tests for the per-profile migration state machine.

Covers:
- MigrationStatus enum and valid transitions
- SQLite persistence of status/detail/timestamps
- Backward-compatible schema migration (adding columns to existing DB)
- Idempotent import (re-importing same backup doesn't duplicate states)
- Restart-safe (state survives process restart = new ProfileStore instance)
- Source/cookie/storage/extension validation
- Batch validation/status/retry/repair API endpoints
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict

import pytest
from fastapi.testclient import TestClient

from src.core.migration import (
    MigrationManager,
    MigrationStatus,
    VALID_TRANSITIONS,
)
from src.core.profile import ProfileStore
from src.core.storage import MigrationRecord, make_engine, init_db


# ---------------------------------------------------------------------------
# Helpers — reuse backup scaffold from test_backup_import
# ---------------------------------------------------------------------------

def _make_network_cookies_db(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS cookies(
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
        "INSERT INTO cookies(host_key, name, value, path, expires_utc, is_secure, is_httponly) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
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
    (profile_dir / "WebStorage").mkdir(parents=True, exist_ok=True)
    _make_network_cookies_db(profile_dir / "Network" / "Cookies")
    return profile_dir.parent


def _make_fake_backup(root: Path) -> Path:
    """Create a minimal AdsPower-shaped backup root with 2 profiles."""
    root.mkdir(parents=True, exist_ok=True)
    _make_backup_profile(root, "aaa11111")
    _make_backup_profile(root, "bbb22222")
    jc = root / "json_cookies"
    jc.mkdir(exist_ok=True)
    (jc / "aaa11111_cookies.json").write_text(
        json.dumps([{"name": "sid", "value": "x", "domain": ".example.com", "path": "/"}]),
        encoding="utf-8",
    )
    (root / "all_profiles_list.json").write_text(
        json.dumps([
            {"user_id": "aaa11111", "name": "Acc One", "group_id": "5",
             "user_proxy_config": {"proxy_soft": "no_proxy"},
             "fbcc_user_tag": ["warm"]},
            {"user_id": "bbb22222", "name": "Acc Two", "group_id": "5",
             "user_proxy_config": {"proxy_soft": "no_proxy"}},
        ]),
        encoding="utf-8",
    )
    return root


# ---------------------------------------------------------------------------
# MigrationStatus enum & valid transitions
# ---------------------------------------------------------------------------

class TestMigrationStatusEnum:
    def test_all_required_statuses_exist(self):
        assert MigrationStatus.DISCOVERED.value == "discovered"
        assert MigrationStatus.METADATA_IMPORTED.value == "metadata_imported"
        assert MigrationStatus.STORAGE_COPIED.value == "storage_copied"
        assert MigrationStatus.EXTENSIONS_REMAPPED.value == "extensions_remapped"
        assert MigrationStatus.LAUNCH_VERIFIED.value == "launch_verified"
        assert MigrationStatus.SITE_VERIFIED.value == "site_verified"
        assert MigrationStatus.FAILED.value == "failed"

    def test_valid_transitions_from_discovered(self):
        assert "metadata_imported" in VALID_TRANSITIONS["discovered"]
        assert "failed" in VALID_TRANSITIONS["discovered"]

    def test_valid_transitions_from_metadata_imported(self):
        assert "storage_copied" in VALID_TRANSITIONS["metadata_imported"]
        assert "failed" in VALID_TRANSITIONS["metadata_imported"]
        # Can go back to discovered on retry
        assert "discovered" in VALID_TRANSITIONS["metadata_imported"]

    def test_valid_transitions_from_storage_copied(self):
        assert "extensions_remapped" in VALID_TRANSITIONS["storage_copied"]
        assert "failed" in VALID_TRANSITIONS["storage_copied"]

    def test_valid_transitions_from_extensions_remapped(self):
        assert "launch_verified" in VALID_TRANSITIONS["extensions_remapped"]
        assert "failed" in VALID_TRANSITIONS["extensions_remapped"]

    def test_valid_transitions_from_launch_verified(self):
        assert "site_verified" in VALID_TRANSITIONS["launch_verified"]
        assert "failed" in VALID_TRANSITIONS["launch_verified"]

    def test_failed_is_terminal_for_retry(self):
        # From failed you can retry back to any prior state
        assert "discovered" in VALID_TRANSITIONS["failed"]
        assert "metadata_imported" in VALID_TRANSITIONS["failed"]

    def test_site_verified_is_terminal(self):
        # site_verified is the success terminal — no transitions out
        assert VALID_TRANSITIONS.get("site_verified", set()) == set()

    def test_invalid_transition_raises(self):
        from src.core.migration import MigrationError
        store = ProfileStore()
        mgr = MigrationManager(store)
        mgr.create_or_reset("test123", source_path="/tmp/fake")
        with pytest.raises(MigrationError):
            mgr.transition("test123", MigrationStatus.SITE_VERIFIED)


# ---------------------------------------------------------------------------
# SQLite persistence of migration state
# ---------------------------------------------------------------------------

class TestMigrationPersistence:
    def test_create_migration_record(self, tmp_path):
        store = ProfileStore(tmp_path / "test.db")
        mgr = MigrationManager(store)
        rec = mgr.create_or_reset("uid1", source_path="/backup/uid1")
        assert rec.user_id == "uid1"
        assert rec.status == "discovered"
        assert rec.source_path == "/backup/uid1"
        assert rec.created_at is not None
        assert rec.updated_at is not None

    def test_get_migration_record(self, tmp_path):
        store = ProfileStore(tmp_path / "test.db")
        mgr = MigrationManager(store)
        mgr.create_or_reset("uid1", source_path="/backup/uid1")
        rec = mgr.get("uid1")
        assert rec is not None
        assert rec.status == "discovered"

    def test_get_nonexistent_returns_none(self, tmp_path):
        store = ProfileStore(tmp_path / "test.db")
        mgr = MigrationManager(store)
        assert mgr.get("nonexistent") is None

    def test_transition_updates_status_and_timestamp(self, tmp_path):
        store = ProfileStore(tmp_path / "test.db")
        mgr = MigrationManager(store)
        mgr.create_or_reset("uid1", source_path="/backup/uid1")
        rec = mgr.transition("uid1", MigrationStatus.METADATA_IMPORTED)
        assert rec.status == "metadata_imported"
        assert rec.updated_at is not None

    def test_restart_safe_persists_across_store_instances(self, tmp_path):
        """State must survive a process restart = new ProfileStore instance."""
        db_path = tmp_path / "test.db"
        store1 = ProfileStore(db_path)
        mgr1 = MigrationManager(store1)
        mgr1.create_or_reset("uid1", source_path="/backup/uid1")
        mgr1.transition("uid1", MigrationStatus.METADATA_IMPORTED)

        # Simulate restart — new store pointing at same DB
        store2 = ProfileStore(db_path)
        mgr2 = MigrationManager(store2)
        rec = mgr2.get("uid1")
        assert rec is not None
        assert rec.status == "metadata_imported"

    def test_detail_field_persisted(self, tmp_path):
        store = ProfileStore(tmp_path / "test.db")
        mgr = MigrationManager(store)
        mgr.create_or_reset("uid1", source_path="/backup/uid1")
        mgr.transition(
            "uid1", MigrationStatus.METADATA_IMPORTED,
            detail={"cookie_source": "json", "cookie_count": 5},
        )
        rec = mgr.get("uid1")
        assert rec.detail is not None
        detail = json.loads(rec.detail)
        assert detail["cookie_source"] == "json"
        assert detail["cookie_count"] == 5

    def test_error_field_persisted_on_failure(self, tmp_path):
        store = ProfileStore(tmp_path / "test.db")
        mgr = MigrationManager(store)
        mgr.create_or_reset("uid1", source_path="/backup/uid1")
        mgr.transition(
            "uid1", MigrationStatus.FAILED,
            detail={"error": "cookie DB corrupted", "step": "metadata_imported"},
        )
        rec = mgr.get("uid1")
        assert rec.status == "failed"
        detail = json.loads(rec.detail)
        assert detail["error"] == "cookie DB corrupted"

    def test_backward_compatible_schema_migration(self, tmp_path):
        """An existing DB without migration_state table must get it added."""
        db_path = tmp_path / "test.db"
        # Create a DB with just the profiles table, no migration_state
        engine = make_engine(db_path)
        # Only create profiles table
        from sqlmodel import SQLModel
        from src.core.storage import ProfileRecord
        SQLModel.metadata.create_all(engine, tables=[ProfileRecord.__table__])
        # Verify migration_state doesn't exist yet
        with engine.connect() as conn:
            from sqlalchemy import text
            tables = [r[0] for r in conn.execute(text(
                "SELECT name FROM sqlite_master WHERE type='table'"))]
            assert "migration_state" not in tables
        # Now run init_db — should add the migration_state table
        init_db(engine)
        with engine.connect() as conn:
            tables = [r[0] for r in conn.execute(text(
                "SELECT name FROM sqlite_master WHERE type='table'"))]
            assert "migration_state" in tables

    def test_idempotent_create_or_reset(self, tmp_path):
        """Calling create_or_reset twice on same user_id resets, doesn't error."""
        store = ProfileStore(tmp_path / "test.db")
        mgr = MigrationManager(store)
        mgr.create_or_reset("uid1", source_path="/backup/uid1")
        mgr.transition("uid1", MigrationStatus.METADATA_IMPORTED)
        # Reset
        mgr.create_or_reset("uid1", source_path="/backup/uid1")
        rec = mgr.get("uid1")
        assert rec.status == "discovered"

    def test_list_migrations(self, tmp_path):
        store = ProfileStore(tmp_path / "test.db")
        mgr = MigrationManager(store)
        mgr.create_or_reset("uid1", source_path="/b/uid1")
        mgr.create_or_reset("uid2", source_path="/b/uid2")
        mgr.create_or_reset("uid3", source_path="/b/uid3")
        mgr.transition("uid2", MigrationStatus.METADATA_IMPORTED)
        all_recs = mgr.list_all()
        assert len(all_recs) == 3

    def test_list_by_status(self, tmp_path):
        store = ProfileStore(tmp_path / "test.db")
        mgr = MigrationManager(store)
        mgr.create_or_reset("uid1", source_path="/b/uid1")
        mgr.create_or_reset("uid2", source_path="/b/uid2")
        mgr.transition("uid2", MigrationStatus.METADATA_IMPORTED)
        discovered = mgr.list_by_status(MigrationStatus.DISCOVERED)
        assert len(discovered) == 1
        assert discovered[0].user_id == "uid1"
        imported = mgr.list_by_status(MigrationStatus.METADATA_IMPORTED)
        assert len(imported) == 1
        assert imported[0].user_id == "uid2"


# ---------------------------------------------------------------------------
# Validation checks (source/cookie/storage/extension)
# ---------------------------------------------------------------------------

class TestMigrationValidation:
    def test_validate_source_path_exists(self, tmp_path):
        store = ProfileStore(tmp_path / "test.db")
        mgr = MigrationManager(store)
        backup_root = tmp_path / "backup"
        _make_fake_backup(backup_root)
        result = mgr.validate_source("aaa11111", backup_root)
        assert result["source_valid"] is True
        assert result["source_path_exists"] is True

    def test_validate_source_path_missing(self, tmp_path):
        store = ProfileStore(tmp_path / "test.db")
        mgr = MigrationManager(store)
        result = mgr.validate_source("nonexistent", tmp_path / "backup")
        assert result["source_valid"] is False
        assert result["source_path_exists"] is False

    def test_validate_cookies_from_json(self, tmp_path):
        store = ProfileStore(tmp_path / "test.db")
        mgr = MigrationManager(store)
        backup_root = tmp_path / "backup"
        _make_fake_backup(backup_root)
        result = mgr.validate_cookies("aaa11111", backup_root)
        assert result["cookies_valid"] is True
        assert result["cookie_source"] == "json"
        assert result["cookie_count"] >= 1

    def test_validate_cookies_from_profile_dir(self, tmp_path):
        store = ProfileStore(tmp_path / "test.db")
        mgr = MigrationManager(store)
        backup_root = tmp_path / "backup"
        _make_fake_backup(backup_root)
        # bbb22222 has no JSON cookies, falls back to profile dir
        result = mgr.validate_cookies("bbb22222", backup_root)
        assert result["cookies_valid"] is True
        assert result["cookie_source"] == "profile_dir"
        assert result["cookie_count"] >= 1

    def test_validate_storage_present(self, tmp_path):
        store = ProfileStore(tmp_path / "test.db")
        mgr = MigrationManager(store)
        backup_root = tmp_path / "backup"
        _make_fake_backup(backup_root)
        result = mgr.validate_storage("aaa11111", backup_root)
        assert result["storage_valid"] is True
        assert result["has_local_storage"] is True

    def test_validate_storage_absent(self, tmp_path):
        store = ProfileStore(tmp_path / "test.db")
        mgr = MigrationManager(store)
        # No backup dir at all
        result = mgr.validate_storage("nonexistent", tmp_path / "no_backup")
        assert result["storage_valid"] is False
        assert result["has_local_storage"] is False

    def test_validate_extensions_no_extensions(self, tmp_path):
        store = ProfileStore(tmp_path / "test.db")
        mgr = MigrationManager(store)
        backup_root = tmp_path / "backup"
        _make_fake_backup(backup_root)
        result = mgr.validate_extensions("aaa11111", backup_root)
        # No extensions installed in our test backup
        assert result["extensions_valid"] is True
        assert result["extension_count"] == 0

    def test_validate_all_runs_all_checks(self, tmp_path):
        store = ProfileStore(tmp_path / "test.db")
        mgr = MigrationManager(store)
        backup_root = tmp_path / "backup"
        _make_fake_backup(backup_root)
        result = mgr.validate_all("aaa11111", backup_root)
        assert "source" in result
        assert "cookies" in result
        assert "storage" in result
        assert "extensions" in result
        assert result["source"]["source_valid"] is True
        assert result["cookies"]["cookies_valid"] is True
        assert result["storage"]["storage_valid"] is True
        assert result["extensions"]["extensions_valid"] is True


# ---------------------------------------------------------------------------
# Idempotent import with migration tracking
# ---------------------------------------------------------------------------

class TestIdempotentImport:
    def test_import_creates_migration_records(self, tmp_path):
        from src.core.backup_import import import_adspower_backup_root
        backup_root = tmp_path / "backup"
        _make_fake_backup(backup_root)
        store = ProfileStore(tmp_path / "test.db")
        summary = import_adspower_backup_root(backup_root, store)
        assert summary["imported_count"] == 2
        mgr = MigrationManager(store)
        rec1 = mgr.get("aaa11111")
        rec2 = mgr.get("bbb22222")
        assert rec1 is not None
        assert rec2 is not None
        assert rec1.status == "metadata_imported"
        assert rec2.status == "metadata_imported"

    def test_reimport_is_idempotent(self, tmp_path):
        from src.core.backup_import import import_adspower_backup_root
        backup_root = tmp_path / "backup"
        _make_fake_backup(backup_root)
        store = ProfileStore(tmp_path / "test.db")
        # First import
        import_adspower_backup_root(backup_root, store)
        mgr1 = MigrationManager(store)
        rec1_before = mgr1.get("aaa11111")
        assert rec1_before is not None
        # Second import (should skip, not error, not duplicate)
        summary = import_adspower_backup_root(backup_root, store, overwrite=False)
        assert summary["imported_count"] == 0
        assert summary["skipped_count"] == 2
        # Migration record still exists, not duplicated
        mgr2 = MigrationManager(store)
        rec1_after = mgr2.get("aaa11111")
        assert rec1_after is not None
        all_recs = mgr2.list_all()
        assert len(all_recs) == 2  # No duplication

    def test_reimport_with_overwrite_resets_migration(self, tmp_path):
        from src.core.backup_import import import_adspower_backup_root
        backup_root = tmp_path / "backup"
        _make_fake_backup(backup_root)
        store = ProfileStore(tmp_path / "test.db")
        import_adspower_backup_root(backup_root, store)
        mgr = MigrationManager(store)
        # Simulate advanced state
        mgr.transition("aaa11111", MigrationStatus.STORAGE_COPIED)
        # Re-import with overwrite
        import_adspower_backup_root(backup_root, store, overwrite=True)
        rec = mgr.get("aaa11111")
        assert rec.status == "metadata_imported"  # Reset to post-import state


# ---------------------------------------------------------------------------
# Batch validation / status / retry / repair
# ---------------------------------------------------------------------------

class TestBatchOperations:
    def test_batch_validate_all_profiles(self, tmp_path):
        from src.core.backup_import import import_adspower_backup_root
        backup_root = tmp_path / "backup"
        _make_fake_backup(backup_root)
        store = ProfileStore(tmp_path / "test.db")
        import_adspower_backup_root(backup_root, store)
        mgr = MigrationManager(store)
        results = mgr.batch_validate(backup_root)
        assert len(results) == 2
        assert results["aaa11111"]["source"]["source_valid"] is True
        assert results["bbb22222"]["source"]["source_valid"] is True

    def test_batch_status(self, tmp_path):
        from src.core.backup_import import import_adspower_backup_root
        backup_root = tmp_path / "backup"
        _make_fake_backup(backup_root)
        store = ProfileStore(tmp_path / "test.db")
        import_adspower_backup_root(backup_root, store)
        mgr = MigrationManager(store)
        statuses = mgr.batch_status()
        assert len(statuses) == 2
        assert all(s["status"] == "metadata_imported" for s in statuses)

    def test_batch_retry_resets_failed_to_discovered(self, tmp_path):
        from src.core.backup_import import import_adspower_backup_root
        backup_root = tmp_path / "backup"
        _make_fake_backup(backup_root)
        store = ProfileStore(tmp_path / "test.db")
        import_adspower_backup_root(backup_root, store)
        mgr = MigrationManager(store)
        # Mark one as failed
        mgr.transition("aaa11111", MigrationStatus.FAILED)
        # Retry
        results = mgr.batch_retry(["aaa11111", "bbb22222"])
        assert results["aaa11111"]["retried"] is True
        assert results["bbb22222"]["retried"] is False  # wasn't failed
        rec = mgr.get("aaa11111")
        assert rec.status == "discovered"

    def test_batch_repair_re_validates_and_updates(self, tmp_path):
        from src.core.backup_import import import_adspower_backup_root
        backup_root = tmp_path / "backup"
        _make_fake_backup(backup_root)
        store = ProfileStore(tmp_path / "test.db")
        import_adspower_backup_root(backup_root, store)
        mgr = MigrationManager(store)
        results = mgr.batch_repair(backup_root, ["aaa11111"])
        assert results["aaa11111"]["repaired"] is True
        assert "validation" in results["aaa11111"]


# ---------------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------------

class TestMigrationAPI:
    @pytest.fixture
    def client(self, tmp_path):
        from src.api.server import create_app
        app = create_app(data_root=tmp_path)
        return TestClient(app)

    @pytest.fixture
    def backup_root(self, tmp_path):
        root = tmp_path / "backup"
        _make_fake_backup(root)
        return root

    def test_api_migration_status_empty(self, client):
        r = client.get("/migration/status")
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["total"] == 0
        assert data["list"] == []

    def test_api_migration_status_after_import(self, client, backup_root):
        client.post("/user/import/backup", json={"source_path": str(backup_root)})
        r = client.get("/migration/status")
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["total"] == 2
        statuses = {item["user_id"]: item["status"] for item in data["list"]}
        assert statuses["aaa11111"] == "metadata_imported"
        assert statuses["bbb22222"] == "metadata_imported"

    def test_api_migration_validate(self, client, backup_root):
        client.post("/user/import/backup", json={"source_path": str(backup_root)})
        r = client.post("/migration/validate", json={
            "source_path": str(backup_root),
        })
        assert r.status_code == 200
        data = r.json()["data"]
        assert len(data["results"]) == 2
        assert data["results"]["aaa11111"]["source"]["source_valid"] is True

    def test_api_migration_retry(self, client, backup_root):
        client.post("/user/import/backup", json={"source_path": str(backup_root)})
        # Retry is deliberately restricted to failed records; healthy
        # in-progress migrations must not be reset accidentally.
        from src.api import routes as routes_module
        mgr = routes_module._migration_mgr()
        mgr.transition("aaa11111", MigrationStatus.FAILED)
        r = client.post("/migration/retry", json={
            "user_ids": ["aaa11111"],
        })
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["results"]["aaa11111"]["retried"] is True

    def test_api_migration_retry_does_not_reset_in_progress(self, client, backup_root):
        client.post("/user/import/backup", json={"source_path": str(backup_root)})
        r = client.post("/migration/retry", json={"user_ids": ["aaa11111"]})
        assert r.status_code == 200
        result = r.json()["data"]["results"]["aaa11111"]
        assert result["retried"] is False
        assert "not failed" in result["reason"]

    def test_api_migration_repair(self, client, backup_root):
        client.post("/user/import/backup", json={"source_path": str(backup_root)})
        r = client.post("/migration/repair", json={
            "source_path": str(backup_root),
            "user_ids": ["aaa11111"],
        })
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["results"]["aaa11111"]["repaired"] is True

    def test_api_migration_status_filter_by_status(self, client, backup_root):
        client.post("/user/import/backup", json={"source_path": str(backup_root)})
        r = client.get("/migration/status?status=metadata_imported")
        assert r.status_code == 200
        assert r.json()["data"]["total"] == 2
        r2 = client.get("/migration/status?status=failed")
        assert r2.json()["data"]["total"] == 0

    def test_api_migration_does_not_launch_sites(self, client, backup_root):
        """Batch validation/repair must NOT launch external sites by default."""
        client.post("/user/import/backup", json={"source_path": str(backup_root)})
        r = client.post("/migration/validate", json={
            "source_path": str(backup_root),
            "launch_sites": True,
        })
        # Should reject launch_sites=True or ignore it safely
        assert r.status_code == 200
        data = r.json()["data"]
        # No site verification should have been attempted
        for uid_result in data["results"].values():
            assert "site_verified" not in uid_result or uid_result.get("site_verified") is False
