from datetime import timedelta
from typing import Protocol

from app.schemas.weather import ForecastOut, ObservationOut


class ForecastService(Protocol):
    """Replace this interface with a trained model after defining its data pipeline."""

    def predict(self, observation: ObservationOut) -> ForecastOut: ...


class PersistenceForecast:
    """Reference baseline; deliberately reported as non-AI in the API contract."""

    def predict(self, observation: ObservationOut) -> ForecastOut:
        return ForecastOut(
            city=observation.city,
            predicted_temperature=observation.temperature,
            target_at=observation.observed_at + timedelta(hours=1),
            based_on=observation.id,
        )


forecaster: ForecastService = PersistenceForecast()
