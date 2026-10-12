"""Server-sent events bridged from blocking work running in a worker thread."""
from __future__ import annotations

import asyncio
import json
import threading
from typing import AsyncIterator, Callable

from fastapi.responses import StreamingResponse

from .errors import describe

Emit = Callable[[str, dict], None]
Work = Callable[[Emit, Callable[[], bool]], None]


async def _events(work: Work) -> AsyncIterator[str]:
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()
    stop = threading.Event()

    def emit(event: str, data: dict) -> None:
        loop.call_soon_threadsafe(queue.put_nowait, (event, data))

    def run() -> None:
        try:
            work(emit, stop.is_set)
        except Exception as exc:  # reported to the client as an error event
            status, code, message = describe(exc)
            emit("error", {"status": status, "code": code, "message": message})
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, None)

    loop.run_in_executor(None, run)
    try:
        while True:
            item = await queue.get()
            if item is None:
                break
            event, data = item
            yield f"event: {event}\ndata: {json.dumps(data)}\n\n"
    finally:
        # Runs on normal completion and when the client disconnects; generation stops at the next token.
        stop.set()


def sse_response(work: Work) -> StreamingResponse:
    return StreamingResponse(
        _events(work),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
