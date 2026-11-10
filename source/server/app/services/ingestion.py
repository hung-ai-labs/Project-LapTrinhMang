from datetime import UTC

from sqlalchemy.exc import IntegrityError

from app.db import Observation
from app.db.session import Session
from app.network.hub import hub
from app.schemas.weather import ObservationInput
from app.services.events import event_from_record
from app.services.geography import active_ward


class InvalidWardError(ValueError):
    pass


class EventConflictError(ValueError):
    pass


async def ingest(value: ObservationInput) -> bool:
    async with Session() as session:
        if await active_ward(session, value.ward_id) is None:
            raise InvalidWardError("Unknown or inactive ward")
        record = Observation(
            id=str(value.event_id),
            **value.model_dump(exclude={"event_id", "observed_at"}),
            observed_at=value.observed_at.astimezone(UTC),
        )
        session.add(record)
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            existing = await session.get(Observation, str(value.event_id))
            if existing is not None:
                incoming = value.model_dump(exclude={"event_id", "observed_at"})
                observed = existing.observed_at
                if observed.tzinfo is None:
                    observed = observed.replace(tzinfo=UTC)
                matches = observed.astimezone(UTC) == value.observed_at.astimezone(UTC)
                same_values = all(getattr(existing, key) == item for key, item in incoming.items())
                if not matches or not same_values:
                    raise EventConflictError("Event ID already exists with different values")
                return False
            raise
    event = event_from_record(record)
    hub.publish(f"ward:{value.ward_id}", event.model_dump(mode="json"))
    return True
