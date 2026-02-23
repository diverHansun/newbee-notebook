import asyncio

from newbee_notebook.api.routers.chat import SSEEvent, heartbeat_generator


def test_heartbeat_generator_emits_heartbeat_while_waiting_for_first_event():
    async def delayed_stream():
        await asyncio.sleep(0.12)
        yield SSEEvent.content("hello")

    async def _collect():
        events = []
        async for event in heartbeat_generator(delayed_stream(), heartbeat_interval=0.05):
            events.append(event)
            if event == SSEEvent.content("hello"):
                break
        return events

    events = asyncio.run(_collect())

    assert events[0] == SSEEvent.heartbeat()
    assert SSEEvent.content("hello") in events
