"""Tests for synchronized multi-profile automation (src/core/sync.py).

No browser: pages are fakes, sleep is stubbed.
"""
import pytest

from src.core.automation import parse_flow
from src.core.sync import SyncReport, SyncResult, run_sync


class FakePage:
    def __init__(self, fail_on=None):
        self.calls = []
        self.fail_on = set(fail_on or [])

    async def goto(self, url, **kw):
        self.calls.append(("goto", url))
        if "goto" in self.fail_on:
            raise RuntimeError("nav failed")

    async def evaluate(self, script, *a):
        self.calls.append(("evaluate", script))


@pytest.fixture
def nosleep():
    async def _s(_):
        return None
    return _s


@pytest.fixture
def flow():
    return parse_flow([
        {"action": "goto", "url": "https://example.com"},
        {"action": "wait", "ms": 5},
    ])


@pytest.mark.asyncio
async def test_sync_all_succeed(flow, nosleep):
    pages = {u: FakePage() for u in ("a", "b", "c")}
    async def provider(uid):
        return pages[uid]
    report = await run_sync(["a", "b", "c"], flow, provider, sleep=nosleep)
    assert isinstance(report, SyncReport)
    assert report.ok
    assert report.succeeded == 3
    assert [r.user_id for r in report.results] == ["a", "b", "c"]  # input order preserved
    assert all(r.total == 2 and r.completed == 2 for r in report.results)


@pytest.mark.asyncio
async def test_sync_page_unavailable_is_isolated(flow, nosleep):
    async def provider(uid):
        if uid == "b":
            raise RuntimeError("not running")
        return FakePage()
    report = await run_sync(["a", "b", "c"], flow, provider, sleep=nosleep)
    assert not report.ok
    assert report.succeeded == 2
    b = next(r for r in report.results if r.user_id == "b")
    assert b.ok is False and "page unavailable" in b.error


@pytest.mark.asyncio
async def test_sync_flow_error_per_profile(flow, nosleep):
    async def provider(uid):
        return FakePage(fail_on={"goto"} if uid == "b" else None)
    report = await run_sync(["a", "b"], flow, provider, sleep=nosleep)
    a = next(r for r in report.results if r.user_id == "a")
    b = next(r for r in report.results if r.user_id == "b")
    assert a.ok is True
    # goto failed for b but the wait step still ran -> not ok, 1 completed
    assert b.ok is False and b.completed == 1


@pytest.mark.asyncio
async def test_sync_respects_max_concurrency(flow, nosleep):
    async def provider(uid):
        return FakePage()
    report = await run_sync(["a", "b", "c", "d"], flow, provider, max_concurrency=2, sleep=nosleep)
    assert report.succeeded == 4


def test_report_to_dict():
    rep = SyncReport(results=[SyncResult("a", True, 2, 2), SyncResult("b", False, 1, 2, "boom")])
    d = rep.to_dict()
    assert d["total"] == 2 and d["succeeded"] == 1 and d["ok"] is False
    assert d["results"][1]["error"] == "boom"
