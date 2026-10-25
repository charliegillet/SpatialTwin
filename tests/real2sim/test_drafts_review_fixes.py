"""Regression test for a review finding on the draft event stream: a browser reconnecting after a server restart
(its Last-Event-ID beyond the rebuilt log) still receives the stored status and the terminal event."""
from backend.app.ai.real2sim.drafts import EventLog


async def collect(log, last_event_id):
    return [frame async for frame in log.stream(last_event_id=last_event_id, ping_seconds=0.01)]


async def test_a_cursor_beyond_a_rebuilt_log_replays_it_and_ends():
    log = EventLog()
    log.append("status", {"status": "ready", "phase": "replay"})
    log.append("done", {"status": "ready"}, terminal=True)
    frames = await collect(log, 17)
    assert [frame.split("\n")[1] for frame in frames] == ["event: status", "event: done"]


async def test_a_cursor_inside_the_log_still_resumes_after_it():
    log = EventLog()
    log.append("status", {"status": "extracting"})
    log.append("thought", {"text": "reading walls"})
    log.append("done", {"status": "ready"}, terminal=True)
    frames = await collect(log, 1)
    assert [frame.split("\n")[1] for frame in frames] == ["event: thought", "event: done"]
