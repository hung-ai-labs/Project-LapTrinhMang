import { useEffect, useState } from "react";
import {
  api,
  type City,
  type Forecast,
  type Observation,
  type WeatherEvent,
} from "../lib/api";

function mergeHistory(records: Observation[], incoming: Observation[]) {
  const unique = new Map(
    [...records, ...incoming].map((item) => [item.id, item]),
  );
  return [...unique.values()]
    .sort((a, b) => Date.parse(b.observed_at) - Date.parse(a.observed_at))
    .slice(0, 60);
}

export function useWeather(city: City) {
  const [event, setEvent] = useState<WeatherEvent | null>(null);
  const [history, setHistory] = useState<Observation[]>([]);
  const [forecast, setForecast] = useState<Forecast | null>(null);
  const [status, setStatus] = useState("Đang kết nối");
  const [error, setError] = useState("");

  useEffect(() => {
    let disposed = false;
    let socket: WebSocket | undefined;
    let timer: ReturnType<typeof setTimeout>;
    let attempts = 0;
    const abort = new AbortController();
    setEvent(null);
    setHistory([]);
    setForecast(null);
    setError("");
    setStatus("Đang kết nối");

    const applyEvent = (next: WeatherEvent) => {
      setEvent((previous) =>
        !previous ||
        Date.parse(next.observation.observed_at) >=
          Date.parse(previous.observation.observed_at)
          ? next
          : previous,
      );
    };
    const refresh = async () => {
      try {
        const [snapshot, records, prediction] = await Promise.all([
          api<WeatherEvent>(`/weather/${city}/current`, abort.signal),
          api<Observation[]>(`/weather/${city}/history`, abort.signal),
          api<Forecast>(`/weather/${city}/forecast`, abort.signal),
        ]);
        if (!disposed) {
          applyEvent(snapshot);
          setHistory((previous) => mergeHistory(previous, records));
          setForecast(prediction);
          setError("");
        }
      } catch (err) {
        if (!disposed)
          setError(
            err instanceof Error ? err.message : "Không tải được dữ liệu.",
          );
      }
    };
    const connect = () => {
      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      socket = new WebSocket(
        `${protocol}//${window.location.host}/api/v1/ws/weather/${city}`,
      );
      socket.onopen = () => {
        if (disposed) return;
        attempts = 0;
        setStatus("Đang trực tuyến");
        void refresh(); // Recover persisted events missed while disconnected.
      };
      socket.onmessage = (message) => {
        if (disposed) return;
        try {
          const next = JSON.parse(message.data);
          if (next.type !== "weather.update" || next.observation.city !== city)
            return;
          applyEvent(next as WeatherEvent);
          setHistory((previous) => mergeHistory(previous, [next.observation]));
          setError("");
          void api<Forecast>(`/weather/${city}/forecast`, abort.signal)
            .then((prediction) => {
              if (!disposed) setForecast(prediction);
            })
            .catch(() => {
              if (!disposed) setForecast(null);
            });
        } catch {
          setError("Không đọc được bản tin từ server.");
        }
      };
      socket.onclose = () => {
        if (disposed) return;
        setStatus("Mất kết nối · đang thử lại");
        timer = setTimeout(connect, Math.min(1000 * 2 ** attempts++, 15000));
      };
      socket.onerror = () => socket?.close();
    };
    connect();
    return () => {
      disposed = true;
      abort.abort();
      clearTimeout(timer);
      socket?.close();
    };
  }, [city]);
  return { event, history, forecast, status, error };
}
