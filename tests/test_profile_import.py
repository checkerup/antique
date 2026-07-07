"""Tests for full-profile .adb import (LocalStorage + IndexedDB)."""
import os
import sqlite3
import tarfile
import zipfile
from pathlib import Path

import pytest

from src.core.cookie import (
    apply_initial_state_to_user_data,
    extract_adspower_bundle,
    find_indexeddb_dir,
    find_local_storage_dir,
    find_profile_default_dir,
    prepare_adspower_import,
)


# ---------------------------------------------------------------------------
# Fixtures — synthetic Chrome profile bundle
# ---------------------------------------------------------------------------


def _make_minimal_cookies_db(path: Path) -> Path:
    """Create a minimal Chrome Cookies sqlite file with one cookie."""
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
    WIN_DELTA = 11644473600
    expires_us = int((1700000000 + WIN_DELTA) * 1_000_000)
    conn.execute(
        "INSERT INTO cookies(creation_utc, host_key, name, value, path, expires_utc, is_secure, is_httponly, samesite, last_access_utc) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (0, ".example.com", "k", "v", "/", expires_us, 1, 1, 0, 0),
    )
    conn.commit()
    conn.close()
    return path


def _make_synthetic_leveldb(leveldb_dir: Path, *, files: int = 3) -> Path:
    """Create a fake ``Local Storage/leveldb`` directory with placeholder files.

    Real LevelDB files are binary; for the *copy* test we just need files to
    exist so ``shutil.copytree`` has something to walk.
    """
    leveldb_dir.mkdir(parents=True, exist_ok=True)
    leveldb_dir.joinpath("CURRENT").write_bytes(b"MANIFEST-000002\n")
    leveldb_dir.joinpath("MANIFEST-000002").write_bytes(b"fake")
    for i in range(files):
        leveldb_dir.joinpath(f"{i:06d}.ldb").write_bytes(b"\x00" * 32)
    leveldb_dir.joinpath("LOG").write_bytes(b"")
    return leveldb_dir


def _make_synthetic_indexeddb(idb_dir: Path) -> Path:
    """Create a fake ``IndexedDB/<origin>.indexeddb.leveldb`` directory tree."""
    idb_dir.mkdir(parents=True, exist_ok=True)
    origin_dir = idb_dir / "https_example.com_0.indexeddb.leveldb"
    origin_dir.mkdir(parents=True, exist_ok=True)
    origin_dir.joinpath("CURRENT").write_bytes(b"MANIFEST-000001\n")
    origin_dir.joinpath("000001.ldb").write_bytes(b"\x00" * 16)
    origin_dir.joinpath("LOG").write_bytes(b"")
    return idb_dir


def _make_synthetic_profile(bundle_root: Path, *, with_ls: bool = True, with_idb: bool = True) -> Path:
    """Build a fake AdsPower-style bundle with Default/Cookies + optional
    Local Storage/leveldb and IndexedDB directories."""
    default_dir = bundle_root / "Default"
    default_dir.mkdir(parents=True, exist_ok=True)
    _make_minimal_cookies_db(default_dir / "Cookies")
    if with_ls:
        _make_synthetic_leveldb(default_dir / "Local Storage" / "leveldb")
    if with_idb:
        _make_synthetic_indexeddb(default_dir / "IndexedDB")
    return bundle_root


# ---------------------------------------------------------------------------
# find_profile_default_dir
# ---------------------------------------------------------------------------


def test_find_profile_default_dir_at_root(tmp_path):
    bundle = _make_synthetic_profile(tmp_path)
    d = find_profile_default_dir(bundle)
    assert d == bundle / "Default"


def test_find_profile_default_dir_in_wrapper(tmp_path):
    # AdsPower sometimes wraps with an extra folder
    wrapper = tmp_path / "user_abc123"
    bundle = wrapper / "profile"
    _make_synthetic_profile(bundle)
    d = find_profile_default_dir(wrapper)
    assert d == bundle / "Default"


def test_find_profile_default_dir_missing(tmp_path):
    # Empty bundle — no Default/ anywhere
    assert find_profile_default_dir(tmp_path) is None


# ---------------------------------------------------------------------------
# find_local_storage_dir / find_indexeddb_dir
# ---------------------------------------------------------------------------


def test_find_local_storage_dir_present(tmp_path):
    default = tmp_path / "Default"
    ls = default / "Local Storage" / "leveldb"
    _make_synthetic_leveldb(ls)
    assert find_local_storage_dir(default) == ls


def test_find_local_storage_dir_missing(tmp_path):
    default = tmp_path / "Default"
    default.mkdir()
    assert find_local_storage_dir(default) is None


def test_find_indexeddb_dir_present(tmp_path):
    default = tmp_path / "Default"
    idb = default / "IndexedDB"
    _make_synthetic_indexeddb(idb)
    assert find_indexeddb_dir(default) == idb


def test_find_indexeddb_dir_missing(tmp_path):
    default = tmp_path / "Default"
    default.mkdir()
    assert find_indexeddb_dir(default) is None


# ---------------------------------------------------------------------------
# extract_adspower_bundle
# ---------------------------------------------------------------------------


def test_extract_bundle_from_folder(tmp_path):
    src = tmp_path / "src"
    _make_synthetic_profile(src)
    dest = tmp_path / "dest"
    out = extract_adspower_bundle(src, dest)
    assert out == dest
    assert (dest / "Default" / "Cookies").exists()


def test_extract_bundle_from_zip(tmp_path):
    src = tmp_path / "src"
    _make_synthetic_profile(src)
    zip_path = tmp_path / "bundle.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        for f in src.rglob("*"):
            if f.is_file():
                zf.write(f, arcname=str(f.relative_to(src)))
    dest = tmp_path / "dest"
    extract_adspower_bundle(zip_path, dest)
    assert (dest / "Default" / "Cookies").exists()


def test_extract_bundle_from_tar_gz(tmp_path):
    src = tmp_path / "src"
    _make_synthetic_profile(src)
    tar_path = tmp_path / "bundle.tar.gz"
    with tarfile.open(tar_path, "w:gz") as tf:
        tf.add(src, arcname="src")
    dest = tmp_path / "dest"
    extract_adspower_bundle(tar_path, dest)
    assert (dest / "src" / "Default" / "Cookies").exists() or (dest / "Default" / "Cookies").exists()


def test_extract_bundle_unknown_format_raises(tmp_path):
    bogus = tmp_path / "foo.txt"
    bogus.write_text("not a bundle")
    with pytest.raises(ValueError):
        extract_adspower_bundle(bogus, tmp_path / "dest")


def test_extract_bundle_overwrites_existing_dest(tmp_path):
    src = tmp_path / "src"
    _make_synthetic_profile(src)
    dest = tmp_path / "dest"
    # Pre-fill dest with junk
    dest.mkdir()
    (dest / "stale.txt").write_text("old")
    extract_adspower_bundle(src, dest)
    assert not (dest / "stale.txt").exists()
    assert (dest / "Default" / "Cookies").exists()


# ---------------------------------------------------------------------------
# apply_initial_state_to_user_data
# ---------------------------------------------------------------------------


def test_apply_copies_local_storage_and_indexeddb(tmp_path):
    bundle = _make_synthetic_profile(tmp_path, with_ls=True, with_idb=True)
    default = find_profile_default_dir(bundle)
    user_data = tmp_path / "user_data"
    copied = apply_initial_state_to_user_data(default, user_data)
    assert "local_storage" in copied
    assert "indexeddb" in copied
    assert (user_data / "Default" / "Local Storage" / "leveldb" / "CURRENT").exists()
    assert (user_data / "Default" / "IndexedDB").exists()


def test_apply_skips_missing_dirs(tmp_path):
    bundle = _make_synthetic_profile(tmp_path, with_ls=False, with_idb=False)
    default = find_profile_default_dir(bundle)
    user_data = tmp_path / "user_data"
    copied = apply_initial_state_to_user_data(default, user_data)
    assert copied == {}
    # Target Default/ should still exist (created), but no leveldb/IDB
    assert (user_data / "Default").exists()
    assert not (user_data / "Default" / "Local Storage" / "leveldb").exists()
    assert not (user_data / "Default" / "IndexedDB").exists()


def test_apply_skips_if_already_present(tmp_path):
    bundle = _make_synthetic_profile(tmp_path, with_ls=True, with_idb=True)
    default = find_profile_default_dir(bundle)
    user_data = tmp_path / "user_data"
    # Pre-populate target with sentinel files
    pre_ls = user_data / "Default" / "Local Storage" / "leveldb"
    pre_ls.mkdir(parents=True)
    pre_ls.joinpath("SENTINEL").write_text("user-state")
    pre_idb = user_data / "Default" / "IndexedDB"
    pre_idb.mkdir(parents=True)
    pre_idb.joinpath("SENTINEL").write_text("user-state")

    copied = apply_initial_state_to_user_data(default, user_data)
    # Nothing was copied — user's existing state preserved
    assert copied == {}
    # Sentinels still there
    assert pre_ls.joinpath("SENTINEL").read_text() == "user-state"
    assert pre_idb.joinpath("SENTINEL").read_text() == "user-state"


def test_apply_force_overwrites_existing(tmp_path):
    bundle = _make_synthetic_profile(tmp_path, with_ls=True, with_idb=True)
    default = find_profile_default_dir(bundle)
    user_data = tmp_path / "user_data"
    # Pre-populate target with sentinel files
    pre_ls = user_data / "Default" / "Local Storage" / "leveldb"
    pre_ls.mkdir(parents=True)
    pre_ls.joinpath("SENTINEL").write_text("user-state")

    copied = apply_initial_state_to_user_data(default, user_data, force=True)
    # Now the source leveldb is copied — sentinel is gone
    assert "local_storage" in copied
    assert not pre_ls.joinpath("SENTINEL").exists()
    assert pre_ls.joinpath("CURRENT").exists()


def test_apply_missing_default_returns_empty(tmp_path):
    user_data = tmp_path / "user_data"
    copied = apply_initial_state_to_user_data(tmp_path / "does_not_exist", user_data)
    assert copied == {}


# ---------------------------------------------------------------------------
# prepare_adspower_import (one-shot helper)
# ---------------------------------------------------------------------------


def test_prepare_import_from_folder(tmp_path):
    bundle = _make_synthetic_profile(tmp_path, with_ls=True, with_idb=True)
    dest_root = tmp_path / "imports"
    profile_id = "test01"
    result = prepare_adspower_import(bundle, dest_root, profile_id)
    assert result["extracted_path"] == str(dest_root / profile_id)
    assert result["default_dir"] == str(dest_root / profile_id / "Default")
    assert len(result["cookies"]) == 1
    assert result["cookies"][0].name == "k"


def test_prepare_import_from_zip(tmp_path):
    src = tmp_path / "src"
    _make_synthetic_profile(src, with_ls=True, with_idb=False)
    zip_path = tmp_path / "bundle.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        for f in src.rglob("*"):
            if f.is_file():
                zf.write(f, arcname=str(f.relative_to(src)))
    dest_root = tmp_path / "imports"
    result = prepare_adspower_import(zip_path, dest_root, "abc01")
    assert len(result["cookies"]) == 1
    assert result["default_dir"] is not None
    # And the extracted bundle has the leveldb
    extracted = Path(result["extracted_path"])
    assert (Path(result["default_dir"]) / "Local Storage" / "leveldb" / "CURRENT").exists()


def test_prepare_import_no_local_storage(tmp_path):
    # Profile with no Local Storage — should still extract and parse cookies
    bundle = _make_synthetic_profile(tmp_path, with_ls=False, with_idb=False)
    dest_root = tmp_path / "imports"
    result = prepare_adspower_import(bundle, dest_root, "id01")
    assert len(result["cookies"]) == 1


# ---------------------------------------------------------------------------
# Profile store — set_import_source + mark_initial_state_applied
# ---------------------------------------------------------------------------


def test_profile_store_import_bookkeeping(tmp_path):
    from src.core.profile import ProfileStore

    db = tmp_path / "profiles.db"
    store = ProfileStore(db)
    p = store.create(name="test-profile")
    assert p.import_source_path == ""
    assert p.initial_state_applied is False

    # Set source — by default resets applied
    store.set_import_source(p.user_id, "/some/path")
    p2 = store.get(p.user_id)
    assert p2.import_source_path == "/some/path"
    assert p2.initial_state_applied is False

    # Mark applied
    store.mark_initial_state_applied(p.user_id)
    p3 = store.get(p.user_id)
    assert p3.initial_state_applied is True

    # Re-import with reset_applied=True (default)
    store.set_import_source(p.user_id, "/another/path")
    p4 = store.get(p.user_id)
    assert p4.import_source_path == "/another/path"
    assert p4.initial_state_applied is False

    # Mark applied again
    store.mark_initial_state_applied(p.user_id)
    p5 = store.get(p.user_id)
    assert p5.initial_state_applied is True

    # Set source with reset_applied=False — keeps flag as-is
    store.set_import_source(p.user_id, "/same/path", reset_applied=False)
    p6 = store.get(p.user_id)
    assert p6.import_source_path == "/same/path"
    assert p6.initial_state_applied is True  # preserved


def test_profile_store_set_import_source_unknown_user(tmp_path):
    from src.core.profile import ProfileStore

    db = tmp_path / "profiles.db"
    store = ProfileStore(db)
    with pytest.raises(KeyError):
        store.set_import_source("nonexistent", "/foo")
    with pytest.raises(KeyError):
        store.mark_initial_state_applied("nonexistent")