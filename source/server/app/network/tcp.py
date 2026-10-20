import asyncio
import json
import logging

from pydantic import ValidationError

from app.schemas.weather import ObservationInput
from app.services.ingestion import ingest

logger = logging.getLogger(__name__)
MAX_FRAME_BYTES = 8192


async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    """NDJSON frames: TCP is a byte stream, not a message transport."""
    try:
        while True:
            try:
                frame = await asyncio.wait_for(reader.readline(), timeout=60)
            except (ValueError, TimeoutError):
                writer.write(b'{"status":"error","code":"frame_limit_or_timeout"}\n')
                await writer.drain()
                break
            if not frame:
                break
            try:
                value = ObservationInput.model_validate_json(frame)
                created = await ingest(value)
                response = {
                    "status": "accepted" if created else "duplicate",
                    "event_id": str(value.event_id),
                }
            except ValidationError:
                response = {"status": "error", "code": "invalid_observation"}
            except Exception:
                logger.exception("Ingestion failed")
                response = {"status": "error", "code": "storage_unavailable"}
            writer.write((json.dumps(response) + "\n").encode())
            await asyncio.wait_for(writer.drain(), timeout=10)
    except (ConnectionError, TimeoutError):
        pass
    finally:
        writer.close()
        await writer.wait_closed()
