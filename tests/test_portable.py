"""Tests for portable .antq profile export / import."""
import json

import pytest

from src.core.fingerprint import generate_fingerprint
from src.core.portable import (
    BUNDLE_FORMAT,
    BUNDLE_VERSION,
    PortableBundleError,
    build_bundle,
    dumps_bundle,
    export_profile,
    import_profile,
    load_bundle_file,
    parse_bundle,
)
from src.core.profile import ProfileStore


@pytest.fixture
def store(tmp_path):
    return ProfileStore(db_path=tmp_path / "test.db")


@pytest.fixture
def sample_profile(store):
    fp = generate_fingerprint(seed="portable")
    return store.create(
        name="Portable One",
        group_id="7",
        proxy={"proxy_type": "http", "proxy_host": "1.2.3.4", "proxy_port": 8080},
        fingerprint=fp,
        cookies=[{"name": "sid", "value": "abc", "domain": ".example.com", "path": "/"}],
        tags=["warm", "us"],
        remark="my note",
    )


# ---------------------------------------------------------------------------
# Build / serialise
# ---------------------------------------------------------------------------


def test_build_bundle_shape(sample_profile):
    b = build_bundle(sample_profile)
    assert b["format"] == BUNDLE_FORMAT
    assert b["version"] == BUNDLE_VERSION
    assert b["source_user_id"] == sample_profile.user_id
    prof = b["profile"]
    assert prof["name"] == "Portable One"
    assert prof["group_id"] == "7"
    assert prof["tags"] == ["warm", "us"]
    assert prof["proxy"]["proxy_host"] == "1.2.3.4"
    assert prof["fingerprint"]["id"] == sample_profile.fingerprint["id"]
    assert prof["cookies"][0]["name"] == "sid"


def test_build_bundle_drops_runtime_fields(sample_profile):
    b = build_bundle(sample_profile)
    prof = b["profile"]
    # These machine-local / runtime fields must NOT be in the portable bundle.
    for forbidden in ("running_pid", "running_ws", "import_source_path", "launch_count"):
        assert forbidden not in prof


def test_dumps_bundle_is_valid_json(sample_profile):
    s = dumps_bundle(sample_profile)
    data = json.loads(s)
    assert data["format"] == BUNDLE_FORMAT


def test_export_writes_file_with_suffix(sample_profile, tmp_path):
    out = export_profile(sample_profile, tmp_path / "noext")
    assert out.suffix == ".antq"
    assert out.exists()
    loaded = load_bundle_file(out)
    assert loaded["profile"]["name"] == "Portable One"


# ---------------------------------------------------------------------------
# Parse / validate
# ---------------------------------------------------------------------------


def test_parse_bundle_rejects_bad_format():
    with pytest.raises(PortableBundleError, match="format"):
        parse_bundle({"format": "nope", "version": 1, "profile": {"name": "x"}})


def test_parse_bundle_rejects_bad_version():
    with pytest.raises(PortableBundleError, match="version"):
        parse_bundle({"format": BUNDLE_FORMAT, "version": 999, "profile": {"name": "x"}})


def test_parse_bundle_requires_name():
    with pytest.raises(PortableBundleError, match="name"):
        parse_bundle({"format": BUNDLE_FORMAT, "version": BUNDLE_VERSION, "profile": {}})


def test_parse_bundle_rejects_bad_json():
    with pytest.raises(PortableBundleError, match="JSON"):
        parse_bundle("{not json")


# ---------------------------------------------------------------------------
# Round-trip import
# ---------------------------------------------------------------------------


def test_round_trip_export_import(store, sample_profile):
    bundle = build_bundle(sample_profile)
    imported = import_profile(store, bundle, name="Copied")
    assert imported.user_id != sample_profile.user_id  # new id assigned
    assert imported.name == "Copied"
    assert imported.group_id == "7"
    assert imported.tags == ["warm", "us"]
    assert imported.proxy["proxy_host"] == "1.2.3.4"
    assert imported.cookies[0]["name"] == "sid"
    # Fingerprint preserved (same id as the source)
    assert imported.fingerprint["id"] == sample_profile.fingerprint["id"]


def test_import_from_file_path(store, sample_profile, tmp_path):
    out = export_profile(sample_profile, tmp_path / "p.antq")
    imported = import_profile(store, out)
    assert imported.name == "Portable One"
    assert imported.fingerprint["webgpu_vendor"] == sample_profile.fingerprint["webgpu_vendor"]


def test_import_from_json_string(store, sample_profile):
    s = dumps_bundle(sample_profile)
    imported = import_profile(store, s)
    assert imported.name == "Portable One"


def test_import_explicit_user_id(store, sample_profile):
    imported = import_profile(store, build_bundle(sample_profile), user_id="transfer1")
    assert imported.user_id == "transfer1"


def test_imported_profile_persists_in_store(store, sample_profile):
    imported = import_profile(store, build_bundle(sample_profile))
    fetched = store.get(imported.user_id)
    assert fetched is not None
    assert fetched.name == "Portable One"
