"""The SSE wire format: what the browser's EventSource receives."""
import asyncio

from annotator.realtime.broadcaster import Broadcaster
from annotator.realtime.sse import event_stream


async def take(gen, n):
    return [await gen.__anext__() for _ in range(n)]


def test_stream_starts_with_the_reconnect_delay_then_sends_each_message_as_one_data_line():
    async def go():
        b = Broadcaster()
        sub = b.subscribe(1)
        gen = event_stream(sub, heartbeat_seconds=5)
        b.publish(1, {"type": "images", "op": "update", "data": {"id": 3, "fileName": "a b.jpg"}})
        chunks = await take(gen, 2)
        await gen.aclose()
        return chunks

    assert asyncio.run(go()) == [
        "retry: 3000\n\n",
        'data: {"type":"images","op":"update","data":{"id":3,"fileName":"a b.jpg"}}\n\n',
    ]


def test_an_idle_stream_sends_a_heartbeat_comment():
    """Keeps proxies from closing a quiet connection; EventSource ignores comment lines."""
    async def go():
        sub = Broadcaster().subscribe(1)
        gen = event_stream(sub, heartbeat_seconds=0.01)
        chunks = await take(gen, 2)
        await gen.aclose()
        return chunks

    assert asyncio.run(go())[1] == ": ping\n\n"


def test_the_stream_ends_when_the_server_shuts_down():
    async def go():
        b = Broadcaster()
        gen = event_stream(b.subscribe(1), heartbeat_seconds=5)
        await gen.__anext__()
        b.shutdown()
        return [chunk async for chunk in gen]

    assert asyncio.run(go()) == []


def test_closing_the_stream_unsubscribes():
    """Starlette stops the generator when the browser goes away; the subscription must not leak."""
    async def go():
        b = Broadcaster()
        gen = event_stream(b.subscribe(1), heartbeat_seconds=5)
        await gen.__anext__()
        before = b.subscriber_count()
        await gen.aclose()
        return before, b.subscriber_count()

    assert asyncio.run(go()) == (1, 0)
