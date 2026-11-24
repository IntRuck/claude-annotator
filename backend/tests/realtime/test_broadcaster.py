"""Broadcaster: hands each live message to the SSE streams of that project (in the API's event loop)."""
import asyncio
import threading

from annotator.realtime.broadcaster import RESYNC, Broadcaster


def run(coro):
    return asyncio.run(coro)


def drain(sub) -> list:
    items = []
    while not sub.queue.empty():
        items.append(sub.queue.get_nowait())
    return items


def test_a_message_reaches_only_the_streams_of_its_project():
    async def go():
        b = Broadcaster()
        one, other = b.subscribe(1), b.subscribe(2)
        b.publish(1, {"type": "images"})
        return drain(one), drain(other)

    assert run(go()) == ([{"type": "images"}], [])


def test_every_stream_of_the_project_gets_the_message():
    async def go():
        b = Broadcaster()
        a, c = b.subscribe(1), b.subscribe(1)
        b.publish(1, {"n": 1})
        return drain(a), drain(c)

    assert run(go()) == ([{"n": 1}], [{"n": 1}])


def test_publish_all_reaches_every_project():
    async def go():
        b = Broadcaster()
        a, c = b.subscribe(1), b.subscribe(2)
        b.publish_all(RESYNC)
        return drain(a), drain(c)

    assert run(go()) == ([RESYNC], [RESYNC])


def test_a_closed_subscription_gets_nothing_more():
    async def go():
        b = Broadcaster()
        sub = b.subscribe(1)
        sub.close()
        b.publish(1, {"n": 1})
        return drain(sub), b.subscriber_count()

    assert run(go()) == ([], 0)


def test_get_waits_for_the_next_message():
    async def go():
        b = Broadcaster()
        sub = b.subscribe(1)
        asyncio.get_running_loop().call_later(0.01, b.publish, 1, {"n": 1})
        return await sub.get()

    assert run(go()) == {"n": 1}


def test_shutting_down_ends_every_stream():
    async def go():
        b = Broadcaster()
        sub = b.subscribe(1)
        b.shutdown()
        return await sub.get(), b.subscriber_count()

    assert run(go()) == (None, 0)


def test_a_stream_that_falls_too_far_behind_is_told_to_resync():
    """A stuck browser mustn't grow memory forever: its queue is emptied and it refetches instead."""
    async def go():
        b = Broadcaster(max_queue=3)
        sub = b.subscribe(1)
        for n in range(5):
            b.publish(1, {"n": n})
        return drain(sub)

    assert run(go()) == [RESYNC, {"n": 4}]


def test_messages_from_another_thread_are_handed_to_the_event_loop():
    """The NOTIFY listener runs in its own thread; asyncio queues may only be touched from the loop."""
    async def go():
        b = Broadcaster()
        b.attach(asyncio.get_running_loop())
        sub = b.subscribe(3)
        threading.Thread(target=b.publish_from_thread, args=(3, {"n": 1})).start()
        first = await asyncio.wait_for(sub.get(), 2)
        threading.Thread(target=b.publish_all_from_thread, args=(RESYNC,)).start()
        second = await asyncio.wait_for(sub.get(), 2)
        return first, second

    assert run(go()) == ({"n": 1}, RESYNC)
