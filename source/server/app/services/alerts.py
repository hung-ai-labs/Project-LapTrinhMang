from app.schemas.weather import Alert, ObservationOut


def evaluate_alerts(value: ObservationOut) -> list[Alert]:
    alerts = []
    if value.temperature >= 35:
        alerts.append(Alert(code="heat", message="Nhiệt độ cao từ 35°C."))
    if value.rainfall >= 20:
        alerts.append(Alert(code="rain", message="Mưa lớn từ 20 mm/giờ."))
    if value.wind_speed >= 50:
        alerts.append(Alert(code="wind", message="Gió mạnh từ 50 km/giờ."))
    return alerts
