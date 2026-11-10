// The standalone multi-day forecast page currently supports these three cities.
export type City = "hanoi" | "danang" | "hcm";
export interface Province {
  id: string;
  name: string;
}
export interface Ward {
  id: string;
  name: string;
  province_id: string;
  administrative_type: string | null;
  latitude: number | null;
  longitude: number | null;
}
export interface PaginatedData<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}
export interface Observation {
  id: string;
  ward_id: string;
  temperature: number;
  humidity: number;
  wind_speed: number;
  rainfall: number;
  source: string;
  observed_at: string;
}
export interface WeatherEvent {
  type: "weather.update";
  observation: Observation;
  alerts: { code: string; severity: string; message: string }[];
}
export interface Forecast {
  ward_id: string;
  provider: "open_meteo";
  method: "open_meteo_hourly";
  data_kind: "model_forecast";
  predicted_temperature: number;
  predicted_humidity: number;
  predicted_wind_speed: number;
  precipitation_mm: number;
  interval_seconds: 3600;
  target_at: string;
  fetched_at: string;
}
export class ApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export const REQUEST_TIMEOUT_MS = 10000;

export function networkError(error: unknown): ApiError {
  if (error instanceof ApiError) return error;
  const name = error instanceof Error ? error.name : "";
  if (name === "TimeoutError" || name === "AbortError") {
    return new ApiError("Máy chủ không phản hồi. Kiểm tra kết nối mạng.", 0);
  }
  return new ApiError("Không kết nối được tới máy chủ.", 0);
}

/** True when the request failed because the server could not be reached. */
export function isConnectionError(error: unknown): boolean {
  return error instanceof ApiError && error.status === 0;
}

export function withTimeout(signal?: AbortSignal, ms = REQUEST_TIMEOUT_MS): AbortSignal {
  const timeout = AbortSignal.timeout(ms);
  if (!signal) return timeout;
  if (typeof AbortSignal.any === "function") return AbortSignal.any([signal, timeout]);
  const controller = new AbortController();
  const abort = () => controller.abort();
  signal.addEventListener("abort", abort, { once: true });
  timeout.addEventListener("abort", abort, { once: true });
  return controller.signal;
}

export async function api<T>(
  path: string, signal?: AbortSignal, cache: RequestCache = "default",
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api/v1${path}`, { signal: withTimeout(signal), cache });
  } catch (error) {
    throw networkError(error);
  }
  const body = await response.json().catch(() => null);
  if (!response.ok || body?.success !== true) {
    throw new ApiError(
      body?.error?.message || `Không tải được dữ liệu (${response.status}).`,
      response.status,
    );
  }
  return body.data as T;
}
export async function catalog<T>(path: string, signal: AbortSignal): Promise<T[]> {
  const records: T[] = [];
  for (let page = 1; ; page++) {
    const separator = path.includes("?") ? "&" : "?";
    const result = await api<PaginatedData<T>>(
      `${path}${separator}page=${page}&page_size=100`, signal,
    );
    records.push(...result.results);
    if (!result.next) return records;
  }
}
