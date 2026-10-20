import asyncio
from contextlib import asynccontextmanager


class WeatherHub:
    """One bounded queue per subscriber; slow consumers keep the newest events."""

    def __init__(self):
        self.subscribers: dict[asyncio.Queue, str] = {}

    @asynccontextmanager
    async def subscribe(self, city: str):
        queue = asyncio.Queue(maxsize=32)
        self.subscribers[queue] = city
        try:
            yield queue
        finally:
            self.subscribers.pop(queue, None)

    def publish(self, city: str, event: dict):
        for queue, selected in tuple(self.subscribers.items()):
            if selected != city:
                continue
            if queue.full():
                queue.get_nowait()
            queue.put_nowait(event)


hub = WeatherHub()
