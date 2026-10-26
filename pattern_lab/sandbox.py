"""Run a function in a separate process with a time limit.

A regex can take exponential time on some texts, and Python cannot interrupt a running match.
So drafts run in a child process that is terminated when it takes too long. The limit counts
from the moment the child is ready (its imports done), so a slow process start never counts
against the patterns.
"""

import multiprocessing
import time
from collections.abc import Callable
from multiprocessing.connection import Connection
from typing import Any

START_SECONDS = 30.0


class TooSlowError(Exception):
    """The work did not finish within its time limit; `where` is its last progress report."""

    def __init__(self, where: str | None = None) -> None:
        super().__init__(where or "too slow")
        self.where = where


class LabError(Exception):
    """The work failed in the child process."""


_progress: Connection | None = None


def report(where: str) -> None:
    """Tell the parent what the child is working on (named in a TooSlowError)."""
    if _progress is not None:
        _progress.send(("progress", where))


def _child(conn: Connection, target: Callable[..., Any], args: tuple[Any, ...]) -> None:
    global _progress
    _progress = conn
    conn.send(("ready", None))
    try:
        conn.send(("ok", target(*args)))
    except Exception as exc:  # reported to the parent, which raises it
        conn.send(("error", f"{type(exc).__name__}: {exc}"))
    finally:
        conn.close()


def run_limited[T](target: Callable[..., T], args: tuple[Any, ...], seconds: float) -> T:
    context = multiprocessing.get_context("spawn")
    receiver, sender = context.Pipe(duplex=False)
    process = context.Process(target=_child, args=(sender, target, args), daemon=True)
    process.start()
    sender.close()
    try:
        if not receiver.poll(START_SECONDS):
            raise TooSlowError("the test process did not start")
        receiver.recv()  # "ready"
        deadline, where = time.monotonic() + seconds, None
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not receiver.poll(remaining):
                raise TooSlowError(where)
            kind, value = receiver.recv()
            if kind == "progress":
                where = value
            elif kind == "error":
                raise LabError(value)
            else:
                return value  # type: ignore[no-any-return]
    finally:
        if process.is_alive():
            process.terminate()
        process.join(timeout=5)
        receiver.close()
