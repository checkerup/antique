"""No-code automation flows (a.k.a. "Cookie Robot" / RPA).

A *flow* is an ordered list of steps that drive a profile's browser page:
navigate, wait, scroll, click, type, and so on. This is the local, no-cloud
equivalent of AdsPower's RPA and Hidemium's no-code automation — useful for
"warming" a profile (accumulating cookies + localStorage by browsing real
sites before exporting) and for simple scripted tasks.

Design:

- ``Step`` — a validated dataclass for one action.
- ``parse_flow(data)`` — turn a JSON/dict list into ``[Step, ...]`` with
  full validation (raises ``FlowValidationError`` on bad input).
- ``FlowRunner`` — executes a parsed flow against a Playwright ``Page``.
  Execution is fully async and every step is wrapped so a single failure
  doesn't abort the whole run unless ``stop_on_error`` is set.
- ``cookie_robot_flow(urls, ...)`` — convenience builder that turns a list
  of URLs into a warming flow (goto → wait → scroll for each URL).

The parser + builder are pure Python and unit-testable without a browser.
The runner is tested against a fake page object (duck-typed) so we don't
need a live Chromium in CI.
"""
from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


class FlowValidationError(ValueError):
    """Raised when a flow definition is structurally invalid."""


# Supported step actions and their required/optional parameters.
# value = (required_keys, optional_keys)
_ACTIONS: Dict[str, tuple] = {
    "goto":       ({"url"}, {"wait_until", "timeout_ms"}),
    "wait":       (set(), {"ms", "min_ms", "max_ms"}),
    "wait_for":   ({"selector"}, {"timeout_ms", "state"}),
    "scroll":     (set(), {"pixels", "to", "times", "delay_ms"}),
    "click":      ({"selector"}, {"timeout_ms"}),
    "type":       ({"selector", "text"}, {"delay_ms", "clear"}),
    "press":      ({"key"}, {"selector"}),
    "hover":      ({"selector"}, {"timeout_ms"}),
    "screenshot": (set(), {"path", "full_page"}),
    "eval":       ({"script"}, set()),
}

_VALID_SCROLL_TO = {"top", "bottom"}
_VALID_WAIT_STATE = {"attached", "detached", "visible", "hidden"}


@dataclass
class Step:
    """A single validated automation step."""

    action: str
    params: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {"action": self.action, **self.params}


def parse_step(raw: Dict[str, Any]) -> Step:
    """Validate and normalise a single step dict."""
    if not isinstance(raw, dict):
        raise FlowValidationError(f"step must be an object, got {type(raw).__name__}")
    action = raw.get("action")
    if not action or not isinstance(action, str):
        raise FlowValidationError("step is missing a string 'action'")
    action = action.lower()
    if action not in _ACTIONS:
        raise FlowValidationError(
            f"unknown action {action!r}; valid: {', '.join(sorted(_ACTIONS))}"
        )
    required, optional = _ACTIONS[action]
    params = {k: v for k, v in raw.items() if k != "action"}
    allowed = required | optional
    unknown = set(params) - allowed
    if unknown:
        raise FlowValidationError(
            f"action {action!r} got unknown params: {', '.join(sorted(unknown))}"
        )
    missing = required - set(params)
    if missing:
        raise FlowValidationError(
            f"action {action!r} is missing required params: {', '.join(sorted(missing))}"
        )

    # Per-action semantic validation
    if action == "goto":
        url = params["url"]
        if not isinstance(url, str) or not url.strip():
            raise FlowValidationError("goto.url must be a non-empty string")
        if not (url.startswith("http://") or url.startswith("https://")):
            raise FlowValidationError(f"goto.url must be http(s): {url!r}")
    if action == "scroll":
        to = params.get("to")
        if to is not None and to not in _VALID_SCROLL_TO:
            raise FlowValidationError(
                f"scroll.to must be one of {_VALID_SCROLL_TO}, got {to!r}"
            )
        for k in ("pixels", "times", "delay_ms"):
            if k in params and (not isinstance(params[k], int) or params[k] < 0):
                raise FlowValidationError(f"scroll.{k} must be a non-negative int")
    if action == "wait":
        for k in ("ms", "min_ms", "max_ms"):
            if k in params and (not isinstance(params[k], int) or params[k] < 0):
                raise FlowValidationError(f"wait.{k} must be a non-negative int")
        if ("min_ms" in params) != ("max_ms" in params):
            raise FlowValidationError("wait.min_ms and wait.max_ms must be used together")
        if "min_ms" in params and params["min_ms"] > params["max_ms"]:
            raise FlowValidationError("wait.min_ms must be <= wait.max_ms")
    if action == "wait_for":
        state = params.get("state")
        if state is not None and state not in _VALID_WAIT_STATE:
            raise FlowValidationError(
                f"wait_for.state must be one of {_VALID_WAIT_STATE}, got {state!r}"
            )
    return Step(action=action, params=params)


def parse_flow(data: Any) -> List[Step]:
    """Parse a full flow (a list of step dicts, or an object with 'steps')."""
    if isinstance(data, dict) and "steps" in data:
        data = data["steps"]
    if not isinstance(data, list):
        raise FlowValidationError("flow must be a list of steps (or {'steps': [...]})")
    if not data:
        raise FlowValidationError("flow is empty")
    return [parse_step(s) for s in data]


def cookie_robot_flow(
    urls: List[str],
    *,
    dwell_min_ms: int = 2000,
    dwell_max_ms: int = 6000,
    scrolls: int = 3,
) -> List[Step]:
    """Build a "cookie robot" warming flow from a list of URLs.

    For each URL: goto → random dwell → scroll a few times → dwell again.
    This mimics light human browsing so sites set their cookies + localStorage.
    """
    if not urls:
        raise FlowValidationError("cookie_robot_flow needs at least one URL")
    steps: List[Dict[str, Any]] = []
    for url in urls:
        steps.append({"action": "goto", "url": url, "wait_until": "domcontentloaded"})
        steps.append({"action": "wait", "min_ms": dwell_min_ms, "max_ms": dwell_max_ms})
        if scrolls > 0:
            steps.append({"action": "scroll", "to": "bottom", "times": scrolls, "delay_ms": 800})
        steps.append({"action": "wait", "min_ms": dwell_min_ms, "max_ms": dwell_max_ms})
    return parse_flow(steps)


@dataclass
class StepResult:
    index: int
    action: str
    ok: bool
    error: str = ""
    detail: Any = None


@dataclass
class FlowResult:
    results: List[StepResult] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(r.ok for r in self.results)

    @property
    def completed(self) -> int:
        return sum(1 for r in self.results if r.ok)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "completed": self.completed,
            "total": len(self.results),
            "steps": [
                {"index": r.index, "action": r.action, "ok": r.ok, "error": r.error}
                for r in self.results
            ],
        }


class FlowRunner:
    """Execute a parsed flow against a Playwright Page (or a duck-typed fake).

    The runner only depends on the async subset of Playwright's Page API:
    ``goto``, ``wait_for_timeout``, ``wait_for_selector``, ``click``,
    ``fill`` / ``type``, ``press``, ``hover``, ``evaluate``, ``screenshot``,
    and ``mouse.wheel`` (via ``evaluate`` fallback). This keeps it testable
    with a lightweight fake page in unit tests.
    """

    def __init__(
        self,
        page: Any,
        *,
        stop_on_error: bool = False,
        rng: Optional[random.Random] = None,
        sleep: Optional[Callable[[float], Any]] = None,
    ):
        self.page = page
        self.stop_on_error = stop_on_error
        self.rng = rng or random.Random()
        # Injectable sleep so tests don't actually wait.
        self._sleep = sleep or asyncio.sleep

    async def run(self, steps: List[Step]) -> FlowResult:
        result = FlowResult()
        for i, step in enumerate(steps):
            try:
                detail = await self._run_step(step)
                result.results.append(
                    StepResult(index=i, action=step.action, ok=True, detail=detail)
                )
            except Exception as exc:  # noqa: BLE001 — we record and optionally continue
                result.results.append(
                    StepResult(index=i, action=step.action, ok=False, error=str(exc))
                )
                if self.stop_on_error:
                    break
        return result

    async def _run_step(self, step: Step) -> Any:
        p = step.params
        action = step.action
        page = self.page

        if action == "goto":
            kwargs = {}
            if "wait_until" in p:
                kwargs["wait_until"] = p["wait_until"]
            if "timeout_ms" in p:
                kwargs["timeout"] = p["timeout_ms"]
            return await page.goto(p["url"], **kwargs)

        if action == "wait":
            if "min_ms" in p:
                ms = self.rng.randint(p["min_ms"], p["max_ms"])
            else:
                ms = p.get("ms", 1000)
            await self._sleep(ms / 1000.0)
            return ms

        if action == "wait_for":
            kwargs = {}
            if "timeout_ms" in p:
                kwargs["timeout"] = p["timeout_ms"]
            if "state" in p:
                kwargs["state"] = p["state"]
            return await page.wait_for_selector(p["selector"], **kwargs)

        if action == "scroll":
            times = p.get("times", 1)
            delay_ms = p.get("delay_ms", 500)
            to = p.get("to")
            pixels = p.get("pixels", 800)
            for _ in range(max(1, times)):
                if to == "bottom":
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                elif to == "top":
                    await page.evaluate("window.scrollTo(0, 0)")
                else:
                    await page.evaluate(f"window.scrollBy(0, {int(pixels)})")
                if delay_ms:
                    await self._sleep(delay_ms / 1000.0)
            return times

        if action == "click":
            kwargs = {}
            if "timeout_ms" in p:
                kwargs["timeout"] = p["timeout_ms"]
            return await page.click(p["selector"], **kwargs)

        if action == "type":
            selector = p["selector"]
            text = p["text"]
            if p.get("clear"):
                await page.fill(selector, "")
            kwargs = {}
            if "delay_ms" in p:
                kwargs["delay"] = p["delay_ms"]
            return await page.type(selector, text, **kwargs)

        if action == "press":
            if "selector" in p:
                return await page.press(p["selector"], p["key"])
            return await page.keyboard.press(p["key"])

        if action == "hover":
            kwargs = {}
            if "timeout_ms" in p:
                kwargs["timeout"] = p["timeout_ms"]
            return await page.hover(p["selector"], **kwargs)

        if action == "screenshot":
            kwargs = {}
            if "path" in p:
                kwargs["path"] = p["path"]
            if "full_page" in p:
                kwargs["full_page"] = p["full_page"]
            return await page.screenshot(**kwargs)

        if action == "eval":
            return await page.evaluate(p["script"])

        raise FlowValidationError(f"unhandled action {action!r}")  # pragma: no cover
