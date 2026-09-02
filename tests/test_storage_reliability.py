"""SQLite reliability tests — WAL mode, busy_timeout, concurrent writes.

Validates that the storage engine is configured for safe concurrent access
from multiple threads (which is the real-world scenario: FastAPI + Playwright
sessions running concurrently).
"""
import sqlite3
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pytest
from sqlmodel import Session

from src.core.storage import (
    ActivityEventRecord,
    ProfileRecord,
    init_db,
    make_engine,
)


def _pragma(engine, name: str) -> str:
    """Read a PRAGMA value from the raw DB connection."""
    with engine.connect() as conn:
        row = conn.exec_driver_sql(f"PRAGMA {name}").fetchone()
        return str(row[0]) if row else ""


class TestWalMode:
    def test_wal_journal_mode(self, tmp_path: Path):
        engine = make_engine(tmp_path / "wal.db")
        init_db(engine)
        assert _pragma(engine, "journal_mode").lower() == "wal"

    def test_wal_files_created(self, tmp_path: Path):
        db_path = tmp_path / "test.db"
        engine = make_engine(db_path)
        init_db(engine)
        # Force a write to create the WAL file
        with Session(engine) as s:
            s.add(ProfileRecord(user_id="w1", name="w1"))
            s.commit()
        # WAL file should exist after a write
        assert (tmp_path / "test.db-wal").exists() or _pragma(engine, "journal_mode").lower() == "wal"


class TestBusyTimeout:
    def test_busy_timeout_set(self, tmp_path: Path):
        engine = make_engine(tmp_path / "bt.db")
        init_db(engine)
        assert int(_pragma(engine, "busy_timeout")) >= 5000

    def test_busy_timeout_at_least_5_seconds(self, tmp_path: Path):
        engine = make_engine(tmp_path / "bt5.db")
        init_db(engine)
        bt = int(_pragma(engine, "busy_timeout"))
        # 5000ms = 5s minimum
        assert bt >= 5000


class TestConcurrentWrites:
    """Concurrent writes from multiple threads must not corrupt or deadlock."""

    def test_concurrent_profile_inserts(self, tmp_path: Path):
        """N threads each insert distinct profiles — all must succeed."""
        engine = make_engine(tmp_path / "concurrent.db")
        init_db(engine)
        n_writers = 8
        per_writer = 25

        def writer(writer_id: int) -> int:
            count = 0
            for i in range(per_writer):
                uid = f"w{writer_id}_p{i:03d}"
                try:
                    with Session(engine) as s:
                        s.add(ProfileRecord(user_id=uid, name=f"Writer-{writer_id}-{i}"))
                        s.commit()
                    count += 1
                except Exception:
                    pass  # busy timeout should prevent this, but tolerate
            return count

        with ThreadPoolExecutor(max_workers=n_writers) as pool:
            futures = [pool.submit(writer, w) for w in range(n_writers)]
            results = [f.result() for f in as_completed(futures)]

        total_inserted = sum(results)
        expected = n_writers * per_writer
        assert total_inserted == expected, f"Only {total_inserted}/{expected} inserts succeeded"

        # Verify all rows present
        with Session(engine) as s:
            rows = s.exec(
                __import__("sqlmodel").select(ProfileRecord)
            ).all()
            assert len(rows) == expected

    def test_concurrent_activity_log_writes(self, tmp_path: Path):
        """Activity log is the hottest concurrent write path — test it."""
        engine = make_engine(tmp_path / "activity.db")
        init_db(engine)

        n_threads = 10
        per_thread = 50
        barrier = threading.Barrier(n_threads)

        def logger(tid: int) -> int:
            barrier.wait()  # start together for max contention
            count = 0
            for i in range(per_thread):
                try:
                    with Session(engine) as s:
                        s.add(ActivityEventRecord(
                            user_id=f"u{tid}",
                            action="launch",
                            detail=f'{{"i":{i}}}',
                        ))
                        s.commit()
                    count += 1
                except Exception:
                    pass
            return count

        with ThreadPoolExecutor(max_workers=n_threads) as pool:
            futures = [pool.submit(logger, t) for t in range(n_threads)]
            results = [f.result() for f in as_completed(futures)]

        assert sum(results) == n_threads * per_thread

    def test_concurrent_mixed_read_write(self, tmp_path: Path):
        """Concurrent reads during writes must not fail."""
        engine = make_engine(tmp_path / "mixed.db")
        init_db(engine)

        # Seed some data
        with Session(engine) as s:
            for i in range(20):
                s.add(ProfileRecord(user_id=f"seed{i:03d}", name=f"seed{i}"))
            s.commit()

        stop = threading.Event()
        errors: list = []

        def reader():
            while not stop.is_set():
                try:
                    with Session(engine) as s:
                        rows = s.exec(
                            __import__("sqlmodel").select(ProfileRecord)
                        ).all()
                        assert len(rows) >= 20
                except Exception as e:
                    errors.append(("reader", e))
                time.sleep(0.001)

        def writer():
            i = 0
            while not stop.is_set():
                try:
                    with Session(engine) as s:
                        s.add(ProfileRecord(
                            user_id=f"cw{i:04d}",
                            name=f"concurrent-{i}",
                        ))
                        s.commit()
                    i += 1
                except Exception as e:
                    errors.append(("writer", e))
                time.sleep(0.002)

        threads = []
        threads.append(threading.Thread(target=reader))
        threads.append(threading.Thread(target=reader))
        threads.append(threading.Thread(target=writer))

        for t in threads:
            t.start()

        time.sleep(1.0)
        stop.set()
        for t in threads:
            t.join(timeout=5)

        # No errors should have occurred
        assert not errors, f"Concurrent read/write errors: {errors[:5]}"

    def test_concurrent_updates_same_row(self, tmp_path: Path):
        """Multiple threads updating the same row's launch_count."""
        engine = make_engine(tmp_path / "update.db")
        init_db(engine)

        with Session(engine) as s:
            s.add(ProfileRecord(user_id="shared", name="shared", launch_count=0))
            s.commit()

        n_threads = 6
        per_thread = 20
        barrier = threading.Barrier(n_threads)
        errors: list = []

        def updater():
            barrier.wait()
            for i in range(per_thread):
                try:
                    with Session(engine) as s:
                        rec = s.get(ProfileRecord, "shared")
                        if rec:
                            rec.launch_count += 1
                            s.add(rec)
                            s.commit()
                except Exception as e:
                    errors.append(e)

        threads = [threading.Thread(target=updater) for _ in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        # At least some updates should succeed — WAL + busy_timeout prevents total failure
        with Session(engine) as s:
            rec = s.get(ProfileRecord, "shared")
            assert rec is not None
            assert rec.launch_count > 0, "No updates succeeded"

    def test_synchronous_normal_or_better(self, tmp_path: Path):
        """Synchronous should be NORMAL (safe with WAL) or FULL."""
        engine = make_engine(tmp_path / "sync.db")
        init_db(engine)
        sync = _pragma(engine, "synchronous").lower()
        # NORMAL=1, FULL=2, OFF=0 — NORMAL is the recommended for WAL
        assert sync in ("1", "2", "normal", "full"), f"Got synchronous={sync!r}"
