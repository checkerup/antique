"""Tests for safe_archive integration and path validation in cookie/backup imports.

Covers P0 security defects:
1. ZIP slip / tar path traversal in cookie import and bundle extraction
2. user_id path traversal in backup import helpers
3. Terminal batch_repair safety (site_verified → failed must not crash)
4. Orphan migration records when profile creation fails
"""
from __future__ import annotations

import json
import sqlite3
import tarfile
import zipfile
from pathlib import Path

import pytest

from src.core.cookie import (
    extract_adspower_bundle,
    import_adspower_profile,
)
from src.core.backup_import import (
    _cookie_json_path,
    _profile_dir,
    prepare_backup_profile_payload,
    import_adspower_backup_root,
)
from src.core.migration import MigrationManager, MigrationStatus
from src.core.profile import ProfileStore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_synthetic_cookies_db(path: Path) -> Path:
    """Create a minimal Chrome Cookies sqlite file with one cookie."""
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.executescript("""
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
    """)
    WIN_DELTA = 11644473600
    expires_us = int((1700000000 + WIN_DELTA) * 1_000_000)
    conn.execute(
        "INSERT INTO cookies(host_key, name, value, path, expires_utc, is_secure, is_httponly) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (".example.com", "sid", "val", "/", expires_us, 1, 1),
    )
    conn.commit()
    conn.close()
    return path


# ---------------------------------------------------------------------------
# 1. ZIP slip / tar path traversal in import_adspower_profile
# ---------------------------------------------------------------------------

class TestZipSlipInCookieImport:
    def test_zip_slip_rejected_in_import_adspower_profile(self, tmp_path):
        """A ZIP with ../ in entry names must be rejected, not extracted."""
        from src.core.safe_archive import UnsafeArchiveError

        zip_path = tmp_path / "evil.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("../../evil.txt", "pwned")

        with pytest.raises(UnsafeArchiveError):
            import_adspower_profile(zip_path)

    def test_zip_slip_absolute_path_rejected(self, tmp_path):
        """ZIP entries with absolute paths must be rejected."""
        from src.core.safe_archive import UnsafeArchiveError

        zip_path = tmp_path / "evil_abs.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("/etc/evil.txt", "pwned")

        with pytest.raises(UnsafeArchiveError):
            import_adspower_profile(zip_path)

    def test_tar_path_traversal_rejected(self, tmp_path):
        """A TAR with ../ paths must be rejected."""
        from src.core.safe_archive import UnsafeArchiveError

        tar_path = tmp_path / "evil.tar.gz"
        # Build a tar with a path traversal entry
        with tarfile.open(tar_path, "w:gz") as tf:
            info = tarfile.TarInfo(name="../../../evil.txt")
            data = b"pwned"
            info.size = len(data)
            tf.addfile(info, io_bytes(data))

        with pytest.raises(UnsafeArchiveError):
            import_adspower_profile(tar_path)

    def test_zip_symlink_rejected(self, tmp_path):
        """ZIP entries that are symlinks must be rejected."""
        from src.core.safe_archive import UnsafeArchiveError

        zip_path = tmp_path / "evil_symlink.zip"
        # Create a symlink entry in the zip
        with zipfile.ZipFile(zip_path, "w") as zf:
            info = zipfile.ZipInfo("link")
            info.external_attr = (0o120000 << 16)  # S_IFLNK
            zf.writestr(info, "/etc/passwd")

        with pytest.raises(UnsafeArchiveError):
            import_adspower_profile(zip_path)

    def test_safe_zip_still_imports_cookies(self, tmp_path):
        """A legitimate ZIP with Default/Cookies should still work."""
        # Build a valid zip
        default_dir = tmp_path / "src" / "Default"
        default_dir.mkdir(parents=True)
        cookies_db = _make_synthetic_cookies_db(default_dir / "Cookies")

        zip_path = tmp_path / "valid.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.write(cookies_db, arcname="Default/Cookies")

        cookies = import_adspower_profile(zip_path)
        assert len(cookies) == 1
        assert cookies[0].name == "sid"


# ---------------------------------------------------------------------------
# 2. ZIP slip in extract_adspower_bundle
# ---------------------------------------------------------------------------

class TestZipSlipInExtractBundle:
    def test_zip_slip_rejected_in_extract_adspower_bundle(self, tmp_path):
        """extract_adspower_bundle must reject path traversal."""
        from src.core.safe_archive import UnsafeArchiveError

        zip_path = tmp_path / "evil_bundle.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("../../evil.txt", "pwned")

        dest = tmp_path / "dest"
        with pytest.raises(UnsafeArchiveError):
            extract_adspower_bundle(zip_path, dest)

    def test_tar_traversal_rejected_in_extract_adspower_bundle(self, tmp_path):
        """extract_adspower_bundle must reject tar path traversal."""
        from src.core.safe_archive import UnsafeArchiveError

        tar_path = tmp_path / "evil_bundle.tar.gz"
        with tarfile.open(tar_path, "w:gz") as tf:
            info = tarfile.TarInfo(name="../../../evil.txt")
            data = b"pwned"
            info.size = len(data)
            tf.addfile(info, io_bytes(data))

        dest = tmp_path / "dest"
        with pytest.raises(UnsafeArchiveError):
            extract_adspower_bundle(tar_path, dest)


# ---------------------------------------------------------------------------
# 3. user_id path traversal validation
# ---------------------------------------------------------------------------

class TestUserIdPathTraversal:
    @pytest.mark.parametrize("malicious_id", [
        "../secret",
        "..\\..\\secret",
        "../../etc/passwd",
        "/absolute/path",
        "foo/../../bar",
        "foo/../bar",
    ])
    def test_profile_dir_rejects_traversal(self, malicious_id):
        """_profile_dir must reject user_ids that escape the backup root."""
        with pytest.raises((ValueError, AssertionError)):
            _profile_dir(Path("/backup"), malicious_id)

    @pytest.mark.parametrize("malicious_id", [
        "../secret",
        "..\\..\\secret",
        "foo/../bar",
    ])
    def test_cookie_json_path_rejects_traversal(self, malicious_id):
        """_cookie_json_path must reject user_ids that escape json_cookies/."""
        with pytest.raises((ValueError, AssertionError)):
            _cookie_json_path(Path("/backup"), malicious_id)

    def test_prepare_backup_profile_payload_rejects_traversal(self, tmp_path):
        """prepare_backup_profile_payload must reject malicious user_id."""
        root = tmp_path / "backup"
        root.mkdir()
        with pytest.raises((ValueError, AssertionError)):
            prepare_backup_profile_payload(root, {
                "user_id": "../../etc/passwd",
                "name": "Evil",
                "user_proxy_config": {"proxy_soft": "no_proxy"},
            })

    def test_valid_user_id_accepted(self, tmp_path):
        """Normal alphanumeric user_ids should work fine."""
        root = tmp_path / "backup"
        p = _profile_dir(root, "abc12345")
        assert p == root / "abc12345"


# ---------------------------------------------------------------------------
# 4. Terminal batch_repair safety
# ---------------------------------------------------------------------------

class TestBatchRepairTerminalSafety:
    def _make_backup_profile(self, root: Path, user_id: str) -> Path:
        profile_dir = root / user_id / "Default"
        (profile_dir / "Local Storage" / "leveldb").mkdir(parents=True, exist_ok=True)
        (profile_dir / "Local Storage" / "leveldb" / "CURRENT").write_text("MANIFEST\n")
        _make_synthetic_cookies_db(profile_dir / "Network" / "Cookies")
        return profile_dir.parent

    def _make_backup(self, root: Path) -> Path:
        root.mkdir(parents=True, exist_ok=True)
        self._make_backup_profile(root, "aaa11111")
        (root / "all_profiles_list.json").write_text(
            json.dumps([
                {"user_id": "aaa11111", "name": "Acc", "group_id": "0",
                 "user_proxy_config": {"proxy_soft": "no_proxy"}},
            ]),
            encoding="utf-8",
        )
        return root

    def test_batch_repair_does_not_crash_on_site_verified(self, tmp_path):
        """batch_repair must not raise when a profile is in terminal
        site_verified state and source is still valid."""
        backup_root = self._make_backup(tmp_path / "backup")
        store = ProfileStore(tmp_path / "test.db")
        import_adspower_backup_root(backup_root, store)
        mgr = MigrationManager(store)
        # Advance through the full pipeline to site_verified
        mgr.transition("aaa11111", MigrationStatus.STORAGE_COPIED)
        mgr.transition("aaa11111", MigrationStatus.EXTENSIONS_REMAPPED)
        mgr.transition("aaa11111", MigrationStatus.LAUNCH_VERIFIED)
        mgr.transition("aaa11111", MigrationStatus.SITE_VERIFIED)

        # Now repair — source is still valid, must not crash
        results = mgr.batch_repair(backup_root, ["aaa11111"])
        assert results["aaa11111"]["repaired"] is True

    def test_batch_repair_handles_source_gone_on_site_verified(self, tmp_path):
        """If source is gone and profile is site_verified, batch_repair
        must handle gracefully (mark failed or skip, not crash)."""
        backup_root = self._make_backup(tmp_path / "backup")
        store = ProfileStore(tmp_path / "test.db")
        import_adspower_backup_root(backup_root, store)
        mgr = MigrationManager(store)
        # Advance to terminal
        mgr.transition("aaa11111", MigrationStatus.STORAGE_COPIED)
        mgr.transition("aaa11111", MigrationStatus.EXTENSIONS_REMAPPED)
        mgr.transition("aaa11111", MigrationStatus.LAUNCH_VERIFIED)
        mgr.transition("aaa11111", MigrationStatus.SITE_VERIFIED)

        # Point to a non-existent backup root
        results = mgr.batch_repair(tmp_path / "nonexistent", ["aaa11111"])
        # Must not crash — either failed or skipped with a reason
        assert "aaa11111" in results
        assert results["aaa11111"]["repaired"] is False


# ---------------------------------------------------------------------------
# 5. Orphan migration records
# ---------------------------------------------------------------------------

class TestOrphanMigrationRecords:
    def test_deleting_profile_removes_migration_record(self, tmp_path):
        store = ProfileStore(tmp_path / "test.db")
        store.create(name="Profile", user_id="aaa11111")
        mgr = MigrationManager(store)
        mgr.create_or_reset("aaa11111", source_path=str(tmp_path))
        assert mgr.get("aaa11111") is not None

        assert store.delete("aaa11111") is True
        assert mgr.get("aaa11111") is None

    def _make_backup_profile(self, root: Path, user_id: str) -> Path:
        profile_dir = root / user_id / "Default"
        (profile_dir / "Local Storage" / "leveldb").mkdir(parents=True, exist_ok=True)
        (profile_dir / "Local Storage" / "leveldb" / "CURRENT").write_text("M\n")
        _make_synthetic_cookies_db(profile_dir / "Network" / "Cookies")
        return profile_dir.parent

    def _make_backup(self, root: Path, user_ids: list[str]) -> Path:
        root.mkdir(parents=True, exist_ok=True)
        for uid in user_ids:
            self._make_backup_profile(root, uid)
        (root / "all_profiles_list.json").write_text(
            json.dumps([
                {"user_id": uid, "name": f"Acc {uid}", "group_id": "0",
                 "user_proxy_config": {"proxy_soft": "no_proxy"}}
                for uid in user_ids
            ]),
            encoding="utf-8",
        )
        return root

    def test_failed_profile_creation_does_not_orphan_migration(self, tmp_path,
                                                                monkeypatch):
        """If store.create raises, no orphan migration record should be left
        in 'discovered' state without a corresponding profile."""
        backup_root = self._make_backup(tmp_path / "backup", ["aaa11111"])
        store = ProfileStore(tmp_path / "test.db")

        # Pre-create the profile so store.create will raise ValueError
        # (user_id collision). This simulates a failure during import.
        store.create(name="Pre-existing", user_id="aaa11111")

        # Now import with overwrite=False — will skip, no orphan
        summary = import_adspower_backup_root(backup_root, store, overwrite=False)
        assert summary["skipped_count"] == 1

        # No migration record should exist for skipped profiles
        mgr = MigrationManager(store)
        rec = mgr.get("aaa11111")
        assert rec is None  # skipped profiles should not get migration records

    def test_orphan_record_cleaned_on_profile_creation_failure(self, tmp_path,
                                                                monkeypatch):
        """If store.create raises mid-import, the migration record must be
        marked failed (not left in discovered)."""
        backup_root = self._make_backup(tmp_path / "backup", ["bbb22222"])
        store = ProfileStore(tmp_path / "test.db")

        # Monkeypatch store.create to raise
        original_create = store.create

        def failing_create(*args, **kwargs):
            raise RuntimeError("simulated profile creation failure")

        monkeypatch.setattr(store, "create", failing_create)

        summary = import_adspower_backup_root(backup_root, store, overwrite=True)
        assert summary["error_count"] == 1

        mgr = MigrationManager(store)
        rec = mgr.get("bbb22222")
        # Record should be either failed or not exist — never 'discovered'
        if rec is not None:
            assert rec.status == MigrationStatus.FAILED.value


# ---------------------------------------------------------------------------
# Helper for tarfile TarInfo data
# ---------------------------------------------------------------------------

def io_bytes(data: bytes):
    import io
    return io.BytesIO(data)
