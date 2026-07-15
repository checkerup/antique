"""Synchronized multi-profile automation ("sync groups").

Run the SAME automation flow across many profiles at once — the classic
multi-account power feature (Hidemium/AdsPower call it "synchronizer"). You
pick a set of running profiles and one flow (see ``core.automation``); every
profile executes it concurrently and you get a per-profile result report.

Design mirrors the rest of the codebase: the network/browser side is behind an
injectable ``page_provider`` callable so the orchestration logic is unit-tested
with fake pages, no live browser.

- ``SyncResult`` / ``SyncReport`` — pure result dataclasses.
- ``run_sync(...)`` — async orchestrator: for each user_id, get a page and run
  the flow with a ``FlowRunner``, gathering results concurrently.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, List, Optional

from .automation import FlowRunner, Step


@dataclass
class SyncResult:
    user_id: str
    ok: bool
    completed: int = 0
    total: int = 0
    error: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id, "ok": self.ok,
            "completed": self.completed, "total": self.total, "error": self.error,
        }


@dataclass
class SyncReport:
    results: List[SyncResult] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(r.ok for r in self.results)

    @property
    def succeeded(self) -> int:
        return sum(1 for r in self.results if r.ok)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "succeeded": self.succeeded,
            "total": len(self.results),
            "results": [r.to_dict() for r in self.results],
        }


# A page_provider takes a user_id and returns (page, cleanup) where cleanup is
# an optional awaitable/callable run after the flow (e.g. close the page).
PageProvider = Callable[[str], Awaitable[Any]]


async def run_sync(
    user_ids: List[str],
    steps: List[Step],
    page_provider: PageProvider,
    *,
    stop_on_error: bool = False,
    max_concurrency: int = 0,
    sleep: Optional[Callable[[float], Awaitable[None]]] = None,
) -> SyncReport:
    """Run ``steps`` on every profile in ``user_ids`` concurrently.

    Args:
        user_ids: profiles to drive (should already be running).
        steps: a parsed flow (list of ``Step``) — see ``core.automation``.
        page_provider: async ``(user_id) -> page`` returning a Playwright-like
            page (or a fake in tests). Raise to signal the profile can't run.
        stop_on_error: passed through to each profile's ``FlowRunner``.
        max_concurrency: 0 = unlimited; otherwise cap simultaneous profiles.
        sleep: injected into ``FlowRunner`` so tests don't actually wait.
    """
    report = SyncReport()
    sem = asyncio.Semaphore(max_concurrency) if max_concurrency and max_concurrency > 0 else None

    async def _one(uid: str) -> SyncResult:
        try:
            page = await page_provider(uid)
        except Exception as exc:
            return SyncResult(user_id=uid, ok=False, error=f"page unavailable: {exc}")
        runner = FlowRunner(page, stop_on_error=stop_on_error, sleep=sleep)
        try:
            res = await runner.run(steps)
        except Exception as exc:  # pragma: no cover - defensive
            return SyncResult(user_id=uid, ok=False, error=str(exc))
        return SyncResult(
            user_id=uid, ok=res.ok, completed=res.completed, total=len(res.results)
        )

    async def _guarded(uid: str) -> SyncResult:
        if sem is None:
            return await _one(uid)
        async with sem:
            return await _one(uid)

    tasks = [asyncio.create_task(_guarded(uid)) for uid in user_ids]
    report.results = list(await asyncio.gather(*tasks))
    # Preserve input order (gather preserves order, but be explicit).
    order = {uid: i for i, uid in enumerate(user_ids)}
    report.results.sort(key=lambda r: order.get(r.user_id, 0))
    return report
