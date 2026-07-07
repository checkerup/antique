"""Tests for proxy parsing."""
import pytest

from src.core.proxy import ProxyConfig, adspower_shape, parse_proxy


def test_parse_proxy_none_returns_direct():
    cfg = parse_proxy(None)
    assert cfg.type == "direct"
    assert cfg.to_playwright() is None


def test_parse_proxy_empty_dict():
    cfg = parse_proxy({})
    assert cfg.type == "direct"


def test_parse_adspower_http():
    cfg = parse_proxy({
        "proxy_type": "http",
        "proxy_host": "1.2.3.4",
        "proxy_port": 8080,
        "proxy_user": "u",
        "proxy_password": "p",
    })
    assert cfg.type == "http"
    assert cfg.host == "1.2.3.4"
    assert cfg.port == 8080
    pw = cfg.to_playwright()
    assert pw == {
        "server": "http://1.2.3.4:8080",
        "username": "u",
        "password": "p",
    }


def test_parse_socks5():
    cfg = parse_proxy({
        "proxy_type": "socks5",
        "proxy_host": "5.6.7.8",
        "proxy_port": 1080,
    })
    pw = cfg.to_playwright()
    assert pw == {"server": "socks5://5.6.7.8:1080"}


def test_parse_invalid_type():
    with pytest.raises(ValueError):
        parse_proxy({"proxy_type": "weird", "proxy_host": "x", "proxy_port": 1})


def test_non_direct_without_host_raises():
    cfg = parse_proxy({"proxy_type": "http", "proxy_host": "", "proxy_port": 8080})
    with pytest.raises(ValueError):
        cfg.to_playwright()


def test_adspower_shape_roundtrip():
    cfg = ProxyConfig(type="http", host="1.2.3.4", port=8080, username="u", password="p")
    d = adspower_shape(cfg)
    cfg2 = parse_proxy(d)
    assert cfg == cfg2


def test_alternative_keys_supported():
    """Accepts both AdsPower keys and generic ones."""
    cfg = parse_proxy({"type": "socks5", "host": "1.1.1.1", "port": 1080})
    assert cfg.type == "socks5"
    assert cfg.host == "1.1.1.1"
    assert cfg.port == 1080