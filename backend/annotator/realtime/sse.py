"""Server-Sent Events wire format for one subscription."""
import asyncio
import json
from collections.abc import AsyncIterator

from annotator.realtime.broadcaster import Subscription

RECONNECT_MS = 3000
HEARTBEAT_SECONDS = 15.0


async def event_stream(sub: Subscription, heartbeat_seconds: float = HEARTBEAT_SECONDS) -> AsyncIterator[str]:
    """`retry:` first (how long EventSource waits before reconnecting), then one `data:` line per message.
    A `: ping` comment goes out when idle so proxies keep the connection open; EventSource ignores it."""
    try:
        yield f"retry: {RECONNECT_MS}\n\n"
        while True:
            try:
                message = await asyncio.wait_for(sub.get(), heartbeat_seconds)
            except TimeoutError:
                yield ": ping\n\n"
                continue
            if message is None:
                return
            yield f"data: {json.dumps(message, separators=(',', ':'), ensure_ascii=False)}\n\n"
    finally:
        sub.close()
