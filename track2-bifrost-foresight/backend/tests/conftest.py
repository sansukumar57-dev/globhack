"""Shared test fixtures. Tests must never touch the real foresight.db."""
from __future__ import annotations

import os
import sys

# Prevent OpenMP/BLAS thread contention and deadlocks inside Windows sandboxes
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["VECLIB_MAXIMUM_THREADS"] = "1"
os.environ["NUMEXPR_NUM_THREADS"] = "1"

import uuid
from pathlib import Path
import pytest

# Under Windows sandbox/isolated environments without loopback network permissions,
# asyncio's ProactorEventLoop hangs trying to create a self-pipe via socket.socketpair().
# Replace self-pipe with an os.pipe wrapper so event loops run cleanly in isolation.
if sys.platform == "win32":
    try:
        from asyncio.proactor_events import BaseProactorEventLoop

        class _DummyPipeSocket:
            def __init__(self, fd: int):
                self._fd = fd

            def fileno(self) -> int:
                return self._fd

            def setblocking(self, val: bool) -> None:
                pass

            def send(self, data: bytes) -> int:
                try:
                    return os.write(self._fd, data)
                except OSError:
                    return 0

            def close(self) -> None:
                try:
                    os.close(self._fd)
                except OSError:
                    pass

        def _fake_make_self_pipe(self):
            r, w = os.pipe()
            self._ssock = _DummyPipeSocket(r)
            self._csock = _DummyPipeSocket(w)
            self._self_reading_future = None
            self._internal_fds += 1

        def _fake_close_self_pipe(self):
            if self._ssock:
                self._ssock.close()
                self._ssock = None
            if self._csock:
                self._csock.close()
                self._csock = None
            self._internal_fds -= 1

        def _fake_write_to_self(self):
            if self._csock:
                self._csock.send(b"\0")

        def _fake_loop_self_reading(self, f=None):
            pass

        BaseProactorEventLoop._make_self_pipe = _fake_make_self_pipe
        BaseProactorEventLoop._close_self_pipe = _fake_close_self_pipe
        BaseProactorEventLoop._write_to_self = _fake_write_to_self
        BaseProactorEventLoop._loop_self_reading = _fake_loop_self_reading
    except Exception:
        pass

from foresight import store

_TEST_DIR = Path(__file__).resolve().parent.parent / ".test_tmp"
_TEST_DIR.mkdir(exist_ok=True)


@pytest.fixture()
def tmp_db(monkeypatch):
    """Point the store at a throwaway SQLite file within workspace with schema initialized."""
    import gc
    db_file = _TEST_DIR / f"test_{uuid.uuid4().hex[:8]}.db"
    monkeypatch.setattr(store, "DB_PATH", db_file)
    store.init_db()
    yield store
    # Clean up test database files
    gc.collect()
    for suffix in ("", "-shm", "-wal"):
        f = Path(str(db_file) + suffix)
        if f.exists():
            try:
                f.unlink()
            except Exception:
                pass
