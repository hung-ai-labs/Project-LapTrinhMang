import { useEffect, useState } from "react";
import {
  api, ApiError, type Forecast, type WeatherEvent,
} from "../lib/api";

interface CurrentState {
  wardId: string | null;
  event: WeatherEvent | null;
  status: string;
  error: string;
}
interface ForecastState {
  wardId: string | null;
  value: Forecast | null;
  loading: boolean;
  error: string;
}
function emptyCurrent(wardId: string | null): CurrentState {
  return { wardId, event: null, status: wardId ? "Đang kết nối" : "Chưa chọn địa điểm", error: "" };
}
const errorMessage = (error: unknown, fallback: string) => error instanceof Error ? error.message : fallback;

export function useWeather(wardId: string | null) {
  const [current, setCurrent] = useState<CurrentState>(() => emptyCurrent(wardId));
  const [forecast, setForecast] = useState<ForecastState>({ wardId: null, value: null, loading: false, error: "" });
  const [forecastRequest, setForecastRequest] = useState(0);

  useEffect(() => {
    setCurrent(emptyCurrent(wardId));
    if (!wardId) return;
    let disposed = false;
    let socket: WebSocket | undefined;
    let reconnectTimer: ReturnType<typeof setTimeout> | undefined;
    let attempts = 0;
    let connectedBefore = false;
    let refreshing = false;
    const controller = new AbortController();
    const base = `/wards/${encodeURIComponent(wardId)}/weather`;
    const update = (change: (previous: CurrentState) => CurrentState) => {
      if (!disposed) setCurrent((previous) => change(previous.wardId === wardId ? previous : emptyCurrent(wardId)));
    };
    const applyEvent = (next: WeatherEvent) => {
      if (next.observation.ward_id !== wardId) return;
      update((previous) => ({
        ...previous,
        event: !previous.event || Date.parse(next.observation.observed_at) >=
          Date.parse(previous.event.observation.observed_at) ? next : previous.event,
        error: "",
      }));

    };
    const refreshCurrent = async () => {
      if (disposed || refreshing) return;
      refreshing = true;
      try {
        const snapshot = await api<WeatherEvent>(`${base}/current`, controller.signal);
        if (!disposed) applyEvent(snapshot);
      } catch (error) {
        if (!disposed) update((previous) => ({
          ...previous,
          error: error instanceof ApiError && error.status === 404 ? "" : errorMessage(error, "Không tải được thời tiết."),
        }));
      } finally { refreshing = false; }
    };
    const connect = () => {
      if (disposed) return;
      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      socket = new WebSocket(`${protocol}//${window.location.host}/api/v1/ws/wards/${encodeURIComponent(wardId)}/weather`);
      socket.onopen = () => {
        if (disposed) return;
        attempts = 0;
        update((previous) => ({ ...previous, status: "Đang trực tuyến" }));
        if (connectedBefore) {
          void refreshCurrent();
        }
        connectedBefore = true;
      };
      socket.onmessage = (message) => {
        if (disposed) return;
        try {
          const next = JSON.parse(message.data);
          if (next.type === "weather.update" && next.observation?.ward_id === wardId) applyEvent(next);
        } catch {
          update((previous) => ({ ...previous, error: "Không đọc được bản tin từ server." }));
        }
      };
      socket.onclose = () => {
        if (disposed) return;
        update((previous) => ({ ...previous, status: "Mất kết nối · đang thử lại" }));
        reconnectTimer = setTimeout(connect, Math.min(1000 * 2 ** attempts++, 15000));
      };
      socket.onerror = () => socket?.close();
    };
    void refreshCurrent();
    connect();
    const timer = setInterval(() => { void refreshCurrent(); }, 60000);
    return () => {
      disposed = true;
      controller.abort();
      clearTimeout(reconnectTimer);
      clearInterval(timer);
      socket?.close();
    };
  }, [wardId]);

  useEffect(() => {
    setForecast({ wardId, value: null, loading: Boolean(wardId), error: "" });
    if (!wardId) return;
    let disposed = false;
    const controller = new AbortController();
    void api<Forecast>(`/wards/${encodeURIComponent(wardId)}/weather/forecast`, controller.signal, "no-store")
      .then((value) => {
        if (disposed) return;
        if (value.ward_id !== wardId) throw new Error("Dự báo không khớp phường/xã đang xem.");
        setForecast({ wardId, value, loading: false, error: "" });
      }).catch((error) => {
        if (!disposed) setForecast({ wardId, value: null, loading: false,
          error: errorMessage(error, "Không tải được dự báo.") });
      });
    return () => { disposed = true; controller.abort(); };
  }, [wardId, forecastRequest]);

  const visibleCurrent = current.wardId === wardId ? current : emptyCurrent(wardId);
  const visibleForecast = forecast.wardId === wardId ? forecast : null;
  return {
    ...visibleCurrent,
    forecast: visibleForecast?.value ?? null,
    forecastError: visibleForecast?.error ?? "",
    forecastLoading: Boolean(wardId) && (!visibleForecast || visibleForecast.loading),
    requestForecast: () => { if (wardId) setForecastRequest((previous) => previous + 1); },
  };
}
