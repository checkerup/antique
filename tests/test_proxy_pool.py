"""Tests for the proxy pool: rotation strategies + failover."""
import random

import pytest

from src.core.proxy import ProxyConfig
from src.core.proxy_pool import ProxyPool


def _cfgs(n):
    return [ProxyConfig(type="http", host=f"10.0.0.{i}", port=8000 + i) for i in range(1, n + 1)]


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


def test_empty_pool_rejected():
    with pytest.raises(ValueError):
        ProxyPool(proxies=[])


def test_bad_strategy_rejected():
    with pytest.raises(ValueError):
        ProxyPool(proxies=_cfgs(2), strategy="nope")


def test_from_list_text():
    pool = ProxyPool.from_list_text(
        "http://1.1.1.1:8080\nsocks5://user:pass@2.2.2.2:1080\n", strategy="round_robin"
    )
    assert len(pool.proxies) == 2
    assert pool.strategy == "round_robin"


def test_from_list_text_empty_rejected():
    with pytest.raises(ValueError):
        ProxyPool.from_list_text("# only a comment\n\n")


# ---------------------------------------------------------------------------
# Sticky
# ---------------------------------------------------------------------------


def test_sticky_keeps_same_until_dead():
    pool = ProxyPool(proxies=_cfgs(3), strategy="sticky")
    first = pool.next_proxy()
    # Repeated calls return the same proxy while it's alive.
    assert pool.next_proxy().host == first.host
    assert pool.next_proxy().host == first.host
    # After failover (marks current dead), it moves to a different one.
    nxt = pool.failover()
    assert nxt.host != first.host


# ---------------------------------------------------------------------------
# Round-robin
# ---------------------------------------------------------------------------


def test_round_robin_cycles():
    pool = ProxyPool(proxies=_cfgs(3), strategy="round_robin")
    seq = [pool.next_proxy().host for _ in range(6)]
    # 3 distinct hosts, each appearing twice, in a repeating cycle
    assert len(set(seq)) == 3
    assert seq[:3] == seq[3:]


def test_round_robin_skips_dead():
    pool = ProxyPool(proxies=_cfgs(3), strategy="round_robin")
    dead = pool.proxies[1]
    pool.mark_dead(dead)
    seq = [pool.next_proxy().host for _ in range(4)]
    assert dead.host not in seq


# ---------------------------------------------------------------------------
# Random
# ---------------------------------------------------------------------------


def test_random_is_seedable_and_live_only():
    pool = ProxyPool(proxies=_cfgs(4), strategy="random")
    pool.mark_dead(pool.proxies[0])
    rng = random.Random(123)
    picks = {pool.next_proxy(rng=rng).host for _ in range(20)}
    assert pool.proxies[0].host not in picks
    assert picks.issubset({p.host for p in pool.proxies[1:]})


# ---------------------------------------------------------------------------
# Failover / liveness
# ---------------------------------------------------------------------------


def test_failover_retires_current_and_returns_next():
    pool = ProxyPool(proxies=_cfgs(2), strategy="sticky")
    a = pool.next_proxy()
    b = pool.failover()
    assert b is not None
    assert b.host != a.host
    assert pool.is_dead(a)


def test_all_dead_returns_none():
    pool = ProxyPool(proxies=_cfgs(2), strategy="round_robin")
    for p in pool.proxies:
        pool.mark_dead(p)
    assert pool.next_proxy() is None
    assert pool.failover() is None


def test_reset_liveness_revives_all():
    pool = ProxyPool(proxies=_cfgs(2), strategy="round_robin")
    for p in pool.proxies:
        pool.mark_dead(p)
    assert pool.next_proxy() is None
    pool.reset_liveness()
    assert pool.next_proxy() is not None


def test_live_proxies_reflects_deaths():
    pool = ProxyPool(proxies=_cfgs(3), strategy="sticky")
    assert len(pool.live_proxies()) == 3
    pool.mark_dead(pool.proxies[0])
    assert len(pool.live_proxies()) == 2
    pool.mark_alive(pool.proxies[0])
    assert len(pool.live_proxies()) == 3
