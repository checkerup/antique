"""Tests for bulk operations, proxy health-check, groups, and fingerprint editing.

Run with:  pytest tests/test_bulk_and_proxy.py -v
"""
import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from src.core.proxy import (
    ProxyConfig,
    check_proxy,
    parse_proxy,
    parse_proxy_list,
    adspower_shape,
)
from src.core.fingerprint import Fingerprint, generate_fingerprint


# ---------------------------------------------------------------------------
# proxy.py tests
# ---------------------------------------------------------------------------


class TestParseProxyList:
    def test_url_format_http(self):
        text = "http://1.2.3.4:8080\nhttps://5.6.7.8:3128"
        configs = parse_proxy_list(text)
        assert len(configs) == 2
        assert configs[0].type == "http"
        assert configs[0].host == "1.2.3.4"
        assert configs[0].port == 8080
        assert configs[1].type == "https"
        assert configs[1].host == "5.6.7.8"
        assert configs[1].port == 3128

    def test_url_format_with_auth(self):
        text = "socks5://user:pass123@proxy.example.com:1080"
        configs = parse_proxy_list(text)
        assert len(configs) == 1
        assert configs[0].type == "socks5"
        assert configs[0].host == "proxy.example.com"
        assert configs[0].port == 1080
        assert configs[0].username == "user"
        assert configs[0].password == "pass123"

    def test_host_port_format(self):
        text = "1.2.3.4:8080"
        configs = parse_proxy_list(text)
        assert len(configs) == 1
        assert configs[0].type == "http"
        assert configs[0].host == "1.2.3.4"
        assert configs[0].port == 8080

    def test_host_port_user_pass_format(self):
        text = "1.2.3.4:8080:myuser:mypass"
        configs = parse_proxy_list(text)
        assert len(configs) == 1
        assert configs[0].username == "myuser"
        assert configs[0].password == "mypass"

    def test_five_part_format(self):
        text = "socks5:1.2.3.4:1080:user:pass"
        configs = parse_proxy_list(text)
        assert len(configs) == 1
        assert configs[0].type == "socks5"
        assert configs[0].port == 1080

    def test_skips_comments_and_empty(self):
        text = "# This is a comment\n\n  \nhttp://good.proxy:8080\n# another comment"
        configs = parse_proxy_list(text)
        assert len(configs) == 1
        assert configs[0].host == "good.proxy"

    def test_mixed_formats(self):
        text = """http://fast.proxy:3128
socks5://user:p@ss@slow.proxy:1080
10.0.0.1:8080
10.0.0.2:8080:admin:secret
"""
        configs = parse_proxy_list(text)
        assert len(configs) == 4


class TestCheckProxyDirect:
    @pytest.mark.asyncio
    async def test_skip_for_direct(self):
        cfg = ProxyConfig(type="direct")
        result = await check_proxy(cfg)
        assert result["status"] == "skip"
        assert "direct" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_skip_for_no_host(self):
        cfg = ProxyConfig(type="http", host="", port=0)
        result = await check_proxy(cfg)
        assert result["status"] == "skip"


class TestParseProxy:
    def test_parse_http(self):
        cfg = parse_proxy({"proxy_type": "http", "proxy_host": "1.2.3.4", "proxy_port": 8080})
        assert cfg.type == "http"
        assert cfg.host == "1.2.3.4"
        assert cfg.port == 8080

    def test_parse_empty(self):
        cfg = parse_proxy(None)
        assert cfg.type == "direct"

    def test_parse_with_auth(self):
        cfg = parse_proxy({
            "proxy_type": "socks5",
            "proxy_host": "proxy.com",
            "proxy_port": 1080,
            "proxy_user": "u",
            "proxy_password": "p",
        })
        assert cfg.username == "u"
        assert cfg.password == "p"


class TestAdspowerShape:
    def test_roundtrip(self):
        cfg = ProxyConfig(type="http", host="x.y", port=80, username="a", password="b")
        shape = adspower_shape(cfg)
        cfg2 = parse_proxy(shape)
        assert cfg2.type == cfg.type
        assert cfg2.host == cfg.host
        assert cfg2.port == cfg.port
        assert cfg2.username == cfg.username


# ---------------------------------------------------------------------------
# Fingerprint editing tests
# ---------------------------------------------------------------------------


class TestFingerprintGenerate:
    def test_deterministic_with_seed(self):
        fp1 = generate_fingerprint(seed="test123")
        fp2 = generate_fingerprint(seed="test123")
        assert fp1.user_agent == fp2.user_agent
        assert fp1.canvas_noise_seed == fp2.canvas_noise_seed

    def test_different_without_seed(self):
        fp1 = generate_fingerprint()
        fp2 = generate_fingerprint()
        # Very unlikely to be the same
        assert fp1.noise != fp2.noise

    def test_os_families(self):
        for os_family in ("windows", "macos", "linux"):
            fp = generate_fingerprint(os_family=os_family)
            assert fp.user_agent  # not empty
            assert fp.platform

    def test_fingerprint_has_all_fields(self):
        fp = generate_fingerprint(seed="x")
        assert fp.webgl_vendor
        assert fp.webgl_renderer
        assert fp.audio_noise_seed > 0
        assert fp.canvas_noise_seed > 0
        assert fp.hardware_concurrency > 0
        assert fp.device_memory > 0
        assert fp.screen_width > 0


# ---------------------------------------------------------------------------
# Bulk operations integration tests (using ProfileStore directly)
# ---------------------------------------------------------------------------


class TestBulkOperationsWithStore:
    @pytest.fixture
    def store(self, tmp_path):
        from src.core.profile import ProfileStore
        return ProfileStore(db_path=tmp_path / "test.db")

    def test_bulk_delete(self, store):
        p1 = store.create(name="A")
        p2 = store.create(name="B")
        p3 = store.create(name="C")

        # Delete two
        store.delete(p1.user_id)
        store.delete(p3.user_id)

        remaining = store.list()
        assert len(remaining) == 1
        assert remaining[0].user_id == p2.user_id

    def test_group_filtering(self, store):
        store.create(name="A", group_id="social")
        store.create(name="B", group_id="social")
        store.create(name="C", group_id="crypto")

        social = store.list(group_id="social")
        assert len(social) == 2
        crypto = store.list(group_id="crypto")
        assert len(crypto) == 1

    def test_bulk_proxy_assignment(self, store):
        p1 = store.create(name="A")
        p2 = store.create(name="B")

        proxy_cfg = {"proxy_type": "http", "proxy_host": "1.2.3.4", "proxy_port": 8080}
        store.update(p1.user_id, proxy=proxy_cfg)
        store.update(p2.user_id, proxy=proxy_cfg)

        updated1 = store.get(p1.user_id)
        updated2 = store.get(p2.user_id)
        assert updated1.proxy["proxy_host"] == "1.2.3.4"
        assert updated2.proxy["proxy_host"] == "1.2.3.4"

    def test_fingerprint_update(self, store):
        p = store.create(name="FP test")
        new_fp = generate_fingerprint(seed="custom", os_family="macos")
        store.update(p.user_id, fingerprint=new_fp)

        updated = store.get(p.user_id)
        assert updated.fingerprint["platform"] == "MacIntel"

    def test_group_list(self, store):
        store.create(name="A", group_id="1")
        store.create(name="B", group_id="1")
        store.create(name="C", group_id="2")
        store.create(name="D", group_id="2")
        store.create(name="E", group_id="2")

        profiles = store.list()
        groups = {}
        for p in profiles:
            gid = p.group_id or "0"
            groups[gid] = groups.get(gid, 0) + 1
        assert groups["1"] == 2
        assert groups["2"] == 3

    def test_search_by_name(self, store):
        store.create(name="alpha-profile")
        store.create(name="beta-profile")
        store.create(name="gamma")

        results = store.list(search="alpha")
        assert len(results) == 1
        assert results[0].name == "alpha-profile"

    def test_tag_filter(self, store):
        store.create(name="A", tags=["social", "crypto"])
        store.create(name="B", tags=["social"])
        store.create(name="C", tags=["other"])

        social = store.list(tag="social")
        assert len(social) == 2
        crypto = store.list(tag="crypto")
        assert len(crypto) == 1
