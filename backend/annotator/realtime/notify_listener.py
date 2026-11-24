"""The one database connection that LISTENs for changes (like backend_web's notification listener).

It runs in its own thread with a plain blocking psycopg connection: that works the same on every OS, while
psycopg's async mode doesn't run on Windows' default event loop. Payloads are handed to `on_payload` in this
thread; the caller passes them to the event loop.
"""
import logging
import threading
from collections.abc import Callable

import psycopg

log = logging.getLogger(__name__)

# Must match the channel in db/migration/V4__change_notify.sql.
CHANNEL = "annotator_changes"


class NotifyListener:
    def __init__(self, dsn: str, *, on_payload: Callable[[str], None], on_connect: Callable[[], None] = lambda: None,
                 retry_seconds: float = 2.0, poll_seconds: float = 1.0,
                 connect: Callable[[], psycopg.Connection] | None = None):
        self.on_payload = on_payload
        self.on_connect = on_connect
        self.retry_seconds = retry_seconds
        self.poll_seconds = poll_seconds
        self._connect = connect or (lambda: psycopg.connect(dsn, autocommit=True, connect_timeout=5))
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="notify-listener", daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        self._stop.set()
        if self._thread.is_alive():
            self._thread.join(timeout)

    def is_alive(self) -> bool:
        return self._thread.is_alive()

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                with self._connect() as conn:
                    conn.execute(f"LISTEN {CHANNEL}")
                    log.info("Live updates: listening on %s", CHANNEL)
                    self._call(self.on_connect)
                    while not self._stop.is_set():
                        # Returns after poll_seconds even when quiet, so stop() is noticed.
                        for note in conn.notifies(timeout=self.poll_seconds):
                            self._call(self.on_payload, note.payload)
            except psycopg.Error as e:
                log.warning("Live updates: no database connection (%s); retrying in %ss", e, self.retry_seconds)
                self._stop.wait(self.retry_seconds)

    @staticmethod
    def _call(fn, *args) -> None:
        try:
            fn(*args)
        except Exception:
            log.exception("Live updates: a handler failed; carrying on")
