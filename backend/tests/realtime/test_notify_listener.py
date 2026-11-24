"""NotifyListener: one dedicated connection that LISTENs and hands each payload on, reconnecting if it drops."""
import queue
import threading
from types import SimpleNamespace

import psycopg

from annotator.realtime.notify_listener import CHANNEL, NotifyListener


class FakeConnection:
    """Just enough of a psycopg connection: LISTEN, then notifications from a script.
    A script item that is an exception is raised (the connection dropped)."""

    def __init__(self, script):
        self.script = queue.Queue()
        for item in script:
            self.script.put(item)
        self.executed = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql):
        self.executed.append(sql)

    def notifies(self, timeout):
        try:
            item = self.script.get(timeout=timeout)
        except queue.Empty:
            return
        if isinstance(item, Exception):
            raise item
        yield SimpleNamespace(payload=item)


def connector(*results):
    """connect() returns (or raises) each result in turn, then idle connections."""
    pending = list(results)

    def connect():
        result = pending.pop(0) if pending else FakeConnection([])
        if isinstance(result, Exception):
            raise result
        return result

    return connect


def run_until(listener, done: threading.Event):
    listener.start()
    try:
        assert done.wait(5), "listener didn't get there in time"
    finally:
        listener.stop()


def test_listens_on_the_channel_and_hands_each_payload_on():
    conn = FakeConnection(["a", "b"])
    got, done = [], threading.Event()

    def on_payload(p):
        got.append(p)
        if len(got) == 2:
            done.set()

    listener = NotifyListener("dsn", on_payload=on_payload, poll_seconds=0.01, connect=connector(conn))
    run_until(listener, done)

    assert conn.executed == [f"LISTEN {CHANNEL}"]
    assert got == ["a", "b"]
    assert not listener.is_alive()


def test_says_when_it_is_connected_so_browsers_can_catch_up():
    connected = threading.Event()
    listener = NotifyListener("dsn", on_payload=lambda p: None, on_connect=connected.set, poll_seconds=0.01,
                              connect=connector(FakeConnection([])))
    run_until(listener, connected)


def test_reconnects_after_the_database_was_unreachable_or_the_connection_dropped():
    got, connects, done = [], [], threading.Event()

    def on_payload(p):
        got.append(p)
        if p == "after":
            done.set()

    listener = NotifyListener(
        "dsn", on_payload=on_payload, on_connect=lambda: connects.append(1), poll_seconds=0.01, retry_seconds=0.01,
        connect=connector(psycopg.OperationalError("refused"),
                          FakeConnection(["before", psycopg.OperationalError("server closed")]),
                          FakeConnection(["after"])),
    )
    run_until(listener, done)

    assert got == ["before", "after"]
    assert len(connects) == 2


def test_a_failing_handler_does_not_stop_the_listener():
    got, done = [], threading.Event()

    def on_payload(p):
        if p == "bad":
            raise ValueError("boom")
        got.append(p)
        done.set()

    listener = NotifyListener("dsn", on_payload=on_payload, poll_seconds=0.01,
                              connect=connector(FakeConnection(["bad", "good"])))
    run_until(listener, done)

    assert got == ["good"]
