from datetime import UTC

from sqlalchemy.exc import IntegrityError

from app.db.models import Observation
from app.db.session import Session
from app.network.hub import hub
from app.schemas.weather import ObservationInput, ObservationOut, WeatherEvent
from app.services.alerts import evaluate_alerts


async def ingest(value: ObservationInput) -> bool:
    async with Session() as session:
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
            if await session.get(Observation, str(value.event_id)) is not None:
                return False
            raise
        observation = ObservationOut.model_validate(record)
    event = WeatherEvent(observation=observation, alerts=evaluate_alerts(observation))
    hub.publish(value.city, event.model_dump(mode="json"))
    return True
