"""Hands live messages to the SSE streams of a project. Lives in the API's event loop.

Each open browser tab has one Subscription (an asyncio queue). The NOTIFY listener runs in its own thread, so
it uses the *_from_thread methods, which pass the work to the event loop (asyncio queues aren't thread-safe).
"""
import asyncio
from collections import defaultdict

RESYNC = {"type": "resync"}
DEFAULT_MAX_QUEUE = 1000


class Subscription:
    def __init__(self, broadcaster: "Broadcaster", project_id: int, max_queue: int):
        self.broadcaster = broadcaster
        self.project_id = project_id
        self.queue: asyncio.Queue = asyncio.Queue(maxsize=max_queue)

    async def get(self) -> dict | None:
        """The next message, or None when the server is shutting down."""
        return await self.queue.get()

    def put(self, message: dict | None) -> None:
        if self.queue.full():
            # This tab has fallen far behind (asleep, very slow link). Drop what's queued and tell it to
            # refetch everything instead, so memory stays bounded.
            while not self.queue.empty():
                self.queue.get_nowait()
            self.queue.put_nowait(RESYNC if message is not None else None)
            return
        self.queue.put_nowait(message)

    def close(self) -> None:
        self.broadcaster.unsubscribe(self)


class Broadcaster:
    def __init__(self, max_queue: int = DEFAULT_MAX_QUEUE):
        self.max_queue = max_queue
        self._subs: dict[int, set[Subscription]] = defaultdict(set)
        self._loop: asyncio.AbstractEventLoop | None = None

    def attach(self, loop: asyncio.AbstractEventLoop) -> None:
        """The event loop that owns the queues (set at app start-up)."""
        self._loop = loop

    def subscribe(self, project_id: int) -> Subscription:
        sub = Subscription(self, project_id, self.max_queue)
        self._subs[project_id].add(sub)
        return sub

    def unsubscribe(self, sub: Subscription) -> None:
        subs = self._subs.get(sub.project_id)
        if subs is not None:
            subs.discard(sub)
            if not subs:
                del self._subs[sub.project_id]

    def subscriber_count(self) -> int:
        return sum(len(s) for s in self._subs.values())

    def publish(self, project_id: int, message: dict) -> None:
        for sub in list(self._subs.get(project_id, ())):
            sub.put(message)

    def publish_all(self, message: dict) -> None:
        for project_id in list(self._subs):
            self.publish(project_id, message)

    def publish_from_thread(self, project_id: int, message: dict) -> None:
        self._loop.call_soon_threadsafe(self.publish, project_id, message)

    def publish_all_from_thread(self, message: dict) -> None:
        self._loop.call_soon_threadsafe(self.publish_all, message)

    def shutdown(self) -> None:
        """End every stream (server stopping), so open SSE responses finish instead of holding shutdown up."""
        for subs in list(self._subs.values()):
            for sub in list(subs):
                sub.put(None)
        self._subs.clear()
