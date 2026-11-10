import { useEffect, useRef, useState } from "react";
import {
  api, ApiError, isConnectionError, type Forecast, type Observation, type PaginatedData,
  type WeatherEvent,
} from "../lib/api";
import { forecastCacheKey, ResourceLoader } from "../lib/catalog";
import {
  backoffDelay, HEARTBEAT_CHECK_MS, heartbeatExpired, nextRetryDelay,
} from "../lib/realtime";
import { useConnection } from "./useConnection";

function mergeHistory(records: Observation[], incoming: Observation[]) {
  const unique = new Map([...records, ...incoming].map((item) => [item.id, item]));
  return [...unique.values()]
    .sort((a, b) => Date.parse(b.observed_at) - Date.parse(a.observed_at) || b.id.localeCompare(a.id))
    .slice(0, 60);
}
interface CurrentState {
  wardId: string | null;
  event: WeatherEvent | null;
  status: string;
  error: string;
}
interface HistoryState {
  wardId: string | null;
  records: Observation[];
  loading: boolean;
  error: string;
}
interface ForecastState {
  wardId: string | null;
  value: Forecast | null;
  loading: boolean;
  error: string;
  fromCache: boolean;
}
function emptyCurrent(wardId: string | null): CurrentState {
  return { wardId, event: null, status: wardId ? "Đang kết nối" : "Chưa chọn địa điểm", error: "" };
}

const forecastCache = {
  parse: (raw: string): Forecast | null => {
    const value = JSON.parse(raw) as Forecast;
    return value && typeof value.ward_id === "string" ? value : null;
  },
  serialize: (value: Forecast) => JSON.stringify(value),
};

export function useWeather(
  wardId: string | null,
  { historyEnabled = false }: { historyEnabled?: boolean } = {},
) {
  const { online, restored } = useConnection();
  const [current, setCurrent] = useState<CurrentState>(() => emptyCurrent(wardId));
  const [history, setHistory] = useState<HistoryState>({ wardId: null, records: [], loading: false, error: "" });
  const [forecast, setForecast] = useState<ForecastState>({
    wardId: null, value: null, loading: false, error: "", fromCache: false,
  });
  const [offlineSources, setOfflineSources] = useState({
    current: false, history: false, forecast: false,
  });
  const markOffline = (source: "current" | "history" | "forecast", offline: boolean) => {
    setOfflineSources((previous) => (
      previous[source] === offline ? previous : { ...previous, [source]: offline }
    ));
  };
  const currentLoader = useRef<ResourceLoader<WeatherEvent> | null>(null);
  const historyLoader = useRef<ResourceLoader<PaginatedData<Observation>> | null>(null);
  const forecastLoader = useRef<ResourceLoader<Forecast> | null>(null);
  const reconnect = useRef<() => void>(() => {});
  const applyEventRef = useRef<(next: WeatherEvent) => void>(() => {});
  const historyKey = historyEnabled ? wardId : null;
  const historyKeyRef = useRef(historyKey);
  useEffect(() => { historyKeyRef.current = historyKey; }, [historyKey]);

  useEffect(() => {
    if (!wardId) {
      currentLoader.current = null;
      markOffline("current", false);
      setCurrent(emptyCurrent(wardId));
      return;
    }
    const applyEvent = (next: WeatherEvent) => {
      if (next.observation.ward_id !== wardId) return;
      setCurrent((previous) => {
        const base = previous.wardId === wardId ? previous : emptyCurrent(wardId);
        return {
          ...base,
          event: !base.event || Date.parse(next.observation.observed_at) >=
            Date.parse(base.event.observation.observed_at) ? next : base.event,
          error: "",
        };
      });
      const key = historyKeyRef.current;
      if (key) setHistory((previous) => ({
        wardId: key,
        records: mergeHistory(previous.wardId === key ? previous.records : [], [next.observation]),
        loading: previous.wardId === key ? previous.loading : false,
        error: "",
      }));
    };
    applyEventRef.current = applyEvent;
    const loader = new ResourceLoader<WeatherEvent>({
      load: (signal) => api<WeatherEvent>(
        `/wards/${encodeURIComponent(wardId)}/weather/current`, signal,
      ),
      onValue: applyEvent,
      onError: (message, error) => {
        if (isConnectionError(error)) {
          markOffline("current", true);
          return;
        }
        markOffline("current", false);
        const missing = error instanceof ApiError && error.status === 404;
        setCurrent((previous) => (
          previous.wardId === wardId ? { ...previous, error: missing ? "" : message } : previous
        ));
      },
      retryDelay: nextRetryDelay,
      pollIntervalMs: 60000,
    });
    currentLoader.current = loader;
    loader.start();
    return () => {
      loader.stop();
      currentLoader.current = null;
      applyEventRef.current = () => {};
    };
  }, [wardId]);

  useEffect(() => {
    if (!historyKey) {
      historyLoader.current = null;
      markOffline("history", false);
      setHistory({ wardId: null, records: [], loading: false, error: "" });
      return;
    }
    const loader = new ResourceLoader<PaginatedData<Observation>>({
      load: (signal) => api<PaginatedData<Observation>>(
        `/wards/${encodeURIComponent(historyKey)}/weather/history?page_size=60`, signal,
      ),
      onValue: (result) => setHistory((previous) => ({
        wardId: historyKey,
        records: mergeHistory(previous.wardId === historyKey ? previous.records : [],
          result.results.filter((row) => row.ward_id === historyKey)),
        loading: false,
        error: "",
      })),
      onError: (message, error) => {
        if (isConnectionError(error)) {
          markOffline("history", true);
          return;
        }
        markOffline("history", false);
        setHistory((previous) => (
          previous.wardId === historyKey ? { ...previous, loading: false, error: message } : previous
        ));
      },
      onLoading: (loading) => setHistory((previous) => (
        previous.wardId === historyKey ? { ...previous, loading } : previous
      )),
      retryDelay: nextRetryDelay,
      pollIntervalMs: 60000,
    });
    historyLoader.current = loader;
    loader.start();
    return () => {
      loader.stop();
      historyLoader.current = null;
    };
  }, [historyKey]);

  useEffect(() => {
    if (!wardId) {
      forecastLoader.current = null;
      markOffline("forecast", false);
      setForecast({ wardId: null, value: null, loading: false, error: "", fromCache: false });
      return;
    }
    setForecast({ wardId, value: null, loading: true, error: "", fromCache: false });
    const loader = new ResourceLoader<Forecast>({
      cache: { ...forecastCache, key: forecastCacheKey(wardId) },
      load: (signal) => api<Forecast>(
        `/wards/${encodeURIComponent(wardId)}/weather/forecast`, signal, "no-store",
      ),
      onValue: (value, fromCache) => {
        if (value.ward_id !== wardId) return;
        setForecast({ wardId, value, loading: false, error: "", fromCache });
      },
      onError: (message, error) => {
        if (isConnectionError(error)) {
          markOffline("forecast", true);
          return;
        }
        markOffline("forecast", false);
        setForecast((previous) => (
          previous.wardId === wardId ? { ...previous, loading: false, error: message } : previous
        ));
      },
      onLoading: (loading) => setForecast((previous) => (
        previous.wardId === wardId ? { ...previous, loading } : previous
      )),
      retryDelay: nextRetryDelay,
    });
    forecastLoader.current = loader;
    loader.start();
    return () => {
      loader.stop();
      forecastLoader.current = null;
    };
  }, [wardId]);

  useEffect(() => {
    if (!wardId) return;
    let disposed = false;
    let socket: WebSocket | undefined;
    let reconnectTimer: ReturnType<typeof setTimeout> | undefined;
    let watchdog: ReturnType<typeof setInterval> | undefined;
    let attempts = 0;
    let connectedBefore = false;
    let immediate = false;
    let lastMessageAt = 0;
    const update = (change: (previous: CurrentState) => CurrentState) => {
      if (!disposed) setCurrent((previous) => change(previous.wardId === wardId ? previous : emptyCurrent(wardId)));
    };
    const resync = () => {
      currentLoader.current?.refresh();
      historyLoader.current?.refresh();
      update((previous) => ({ ...previous, status: "Đang trực tuyến" }));
    };
    const connect = () => {
      if (disposed) return;
      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      socket = new WebSocket(`${protocol}//${window.location.host}/api/v1/ws/wards/${encodeURIComponent(wardId)}/weather`);
      socket.onopen = () => {
        if (disposed) return;
        attempts = 0;
        lastMessageAt = Date.now();
        if (connectedBefore) {
          update((previous) => ({ ...previous, status: "Đang đồng bộ dữ liệu" }));
          resync();
          return;
        }
        connectedBefore = true;
        update((previous) => ({ ...previous, status: "Đang trực tuyến" }));
      };
      socket.onmessage = (message) => {
        if (disposed) return;
        lastMessageAt = Date.now();
        try {
          const next = JSON.parse(message.data);
          if (next.type === "weather.update" && next.observation?.ward_id === wardId) {
            applyEventRef.current(next);
          }
        } catch {
          update((previous) => ({ ...previous, error: "Không đọc được bản tin từ server." }));
        }
      };
      socket.onclose = () => {
        if (disposed) return;
        update((previous) => ({ ...previous, status: "Mất kết nối · đang thử lại" }));
        if (immediate) {
          immediate = false;
          connect();
          return;
        }
        reconnectTimer = setTimeout(connect, backoffDelay(attempts++));
      };
      socket.onerror = () => socket?.close();
    };
    reconnect.current = () => {
      if (disposed) return;
      attempts = 0;
      if (socket && socket.readyState === WebSocket.OPEN) {
        resync();
        return;
      }
      immediate = true;
      if (socket) {
        socket.close();
        return;
      }
      connect();
    };
    const onOffline = () => {
      update((previous) => ({ ...previous, status: "Mất kết nối · đang thử lại" }));
    };
    window.addEventListener("offline", onOffline);
    connect();
    watchdog = setInterval(() => {
      if (disposed || !socket || socket.readyState !== WebSocket.OPEN) return;
      if (heartbeatExpired(lastMessageAt, Date.now())) {
        update((previous) => ({ ...previous, status: "Mất kết nối · đang thử lại" }));
        socket.close();
      }
    }, HEARTBEAT_CHECK_MS);
    return () => {
      disposed = true;
      clearTimeout(reconnectTimer);
      clearInterval(watchdog);
      window.removeEventListener("offline", onOffline);
      reconnect.current = () => {};
      socket?.close();
    };
  }, [wardId]);

  useEffect(() => {
    if (restored === 0) return;
    reconnect.current();
    currentLoader.current?.refresh();
    historyLoader.current?.refresh();
    forecastLoader.current?.refresh();
  }, [restored]);

  const visibleCurrent = current.wardId === wardId ? current : emptyCurrent(wardId);
  const visibleHistory = historyKey && history.wardId === historyKey ? history : null;
  const visibleForecast = forecast.wardId === wardId ? forecast : null;
  return {
    ...visibleCurrent,
    stale: Boolean(visibleCurrent.event) && visibleCurrent.status !== "Đang trực tuyến",
    offline: offlineSources.current || offlineSources.history || offlineSources.forecast,
    history: visibleHistory?.records ?? [],
    historyError: visibleHistory?.error ?? "",
    historyLoading: historyEnabled && Boolean(wardId) && (!visibleHistory || visibleHistory.loading),
    forecast: visibleForecast?.value ?? null,
    forecastError: visibleForecast?.error ?? "",
    forecastStale: Boolean(visibleForecast?.value) && visibleForecast?.fromCache === true,
    forecastLoading: Boolean(wardId) && (!visibleForecast || visibleForecast.loading),
    requestForecast: () => { forecastLoader.current?.refresh(); },
    online,
  };
}
