"""Build API weather events from stored observations."""

from app.db import Observation
from app.schemas.weather import ObservationOut, WeatherEvent
from app.services.alerts import evaluate_alerts


def event_from_record(record: Observation) -> WeatherEvent:
    observation = ObservationOut.model_validate(record)
    return WeatherEvent(observation=observation, alerts=evaluate_alerts(observation))
