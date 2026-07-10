"""Tests for the no-code automation flow runner (Cookie Robot / RPA)."""
import random

import pytest

from src.core.automation import (
    FlowResult,
    FlowRunner,
    FlowValidationError,
    Step,
    cookie_robot_flow,
    parse_flow,
    parse_step,
)


# ---------------------------------------------------------------------------
# Parsing / validation
# ---------------------------------------------------------------------------


def test_parse_valid_goto_step():
    s = parse_step({"action": "goto", "url": "https://example.com"})
    assert isinstance(s, Step)
    assert s.action == "goto"
    assert s.params["url"] == "https://example.com"


def test_parse_unknown_action_raises():
    with pytest.raises(FlowValidationError, match="unknown action"):
        parse_step({"action": "teleport", "url": "https://x.com"})


def test_parse_missing_required_param_raises():
    with pytest.raises(FlowValidationError, match="missing required"):
        parse_step({"action": "goto"})


def test_parse_unknown_param_raises():
    with pytest.raises(FlowValidationError, match="unknown params"):
        parse_step({"action": "goto", "url": "https://x.com", "bogus": 1})


def test_parse_goto_rejects_non_http():
    with pytest.raises(FlowValidationError, match="http"):
        parse_step({"action": "goto", "url": "ftp://x.com"})


def test_parse_scroll_to_validation():
    parse_step({"action": "scroll", "to": "bottom"})  # ok
    with pytest.raises(FlowValidationError, match="scroll.to"):
        parse_step({"action": "scroll", "to": "sideways"})


def test_parse_wait_min_max_pairing():
    with pytest.raises(FlowValidationError, match="used together"):
        parse_step({"action": "wait", "min_ms": 100})
    with pytest.raises(FlowValidationError, match="<="):
        parse_step({"action": "wait", "min_ms": 500, "max_ms": 100})


def test_parse_flow_accepts_list_and_wrapped():
    steps = [{"action": "goto", "url": "https://a.com"}, {"action": "wait", "ms": 100}]
    a = parse_flow(steps)
    b = parse_flow({"steps": steps})
    assert len(a) == len(b) == 2


def test_parse_flow_empty_raises():
    with pytest.raises(FlowValidationError, match="empty"):
        parse_flow([])


# ---------------------------------------------------------------------------
# Cookie robot builder
# ---------------------------------------------------------------------------


def test_cookie_robot_flow_structure():
    flow = cookie_robot_flow(["https://a.com", "https://b.com"], scrolls=2)
    actions = [s.action for s in flow]
    # goto, wait, scroll, wait  ->  x2
    assert actions == ["goto", "wait", "scroll", "wait"] * 2
    assert flow[0].params["url"] == "https://a.com"
    assert flow[2].params["times"] == 2


def test_cookie_robot_flow_requires_urls():
    with pytest.raises(FlowValidationError):
        cookie_robot_flow([])


def test_cookie_robot_flow_no_scroll():
    flow = cookie_robot_flow(["https://a.com"], scrolls=0)
    actions = [s.action for s in flow]
    assert "scroll" not in actions


# ---------------------------------------------------------------------------
# Runner (against a fake page — no live browser)
# ---------------------------------------------------------------------------


class FakePage:
    """Records calls; each async method appends to ``calls``."""

    def __init__(self, fail_on=None):
        self.calls = []
        self.fail_on = set(fail_on or [])

    async def goto(self, url, **kw):
        self.calls.append(("goto", url, kw))
        if "goto" in self.fail_on:
            raise RuntimeError("nav failed")
        return {"status": 200}

    async def wait_for_selector(self, selector, **kw):
        self.calls.append(("wait_for_selector", selector, kw))
        return object()

    async def click(self, selector, **kw):
        self.calls.append(("click", selector, kw))

    async def fill(self, selector, text, **kw):
        self.calls.append(("fill", selector, text))

    async def type(self, selector, text, **kw):
        self.calls.append(("type", selector, text, kw))

    async def hover(self, selector, **kw):
        self.calls.append(("hover", selector, kw))

    async def evaluate(self, script, *a):
        self.calls.append(("evaluate", script))
        return None

    async def screenshot(self, **kw):
        self.calls.append(("screenshot", kw))
        return b"png"


@pytest.fixture
def nosleep():
    async def _sleep(_seconds):
        return None
    return _sleep


@pytest.mark.asyncio
async def test_runner_executes_all_steps(nosleep):
    page = FakePage()
    flow = parse_flow([
        {"action": "goto", "url": "https://a.com"},
        {"action": "wait", "ms": 10},
        {"action": "scroll", "to": "bottom", "times": 2, "delay_ms": 0},
        {"action": "click", "selector": "#go"},
        {"action": "type", "selector": "#in", "text": "hi", "clear": True},
        {"action": "screenshot"},
    ])
    runner = FlowRunner(page, rng=random.Random(1), sleep=nosleep)
    res = await runner.run(flow)
    assert res.ok
    assert res.completed == 6
    # goto happened with url
    assert page.calls[0][0] == "goto"
    # two scrollTo bottom calls
    scfg = [c for c in page.calls if c[0] == "evaluate"]
    assert len(scfg) == 2
    # type with clear triggers a fill("") first
    assert ("fill", "#in", "") in page.calls


@pytest.mark.asyncio
async def test_runner_wait_random_uses_rng(nosleep):
    page = FakePage()
    flow = parse_flow([{"action": "wait", "min_ms": 100, "max_ms": 200}])
    runner = FlowRunner(page, rng=random.Random(42), sleep=nosleep)
    res = await runner.run(flow)
    assert res.ok
    # detail is the chosen ms, within range
    assert 100 <= res.results[0].detail <= 200


@pytest.mark.asyncio
async def test_runner_continues_after_error_by_default(nosleep):
    page = FakePage(fail_on={"goto"})
    flow = parse_flow([
        {"action": "goto", "url": "https://a.com"},
        {"action": "wait", "ms": 1},
    ])
    runner = FlowRunner(page, sleep=nosleep)
    res = await runner.run(flow)
    assert not res.ok
    assert res.completed == 1  # the wait still ran
    assert res.results[0].ok is False
    assert "nav failed" in res.results[0].error


@pytest.mark.asyncio
async def test_runner_stop_on_error(nosleep):
    page = FakePage(fail_on={"goto"})
    flow = parse_flow([
        {"action": "goto", "url": "https://a.com"},
        {"action": "wait", "ms": 1},
    ])
    runner = FlowRunner(page, stop_on_error=True, sleep=nosleep)
    res = await runner.run(flow)
    assert not res.ok
    assert len(res.results) == 1  # stopped after the failure


def test_flow_result_to_dict():
    fr = FlowResult()
    fr.results.append(type("R", (), {"index": 0, "action": "goto", "ok": True, "error": ""})())
    d = fr.to_dict()
    assert d["total"] == 1
    assert d["steps"][0]["action"] == "goto"
