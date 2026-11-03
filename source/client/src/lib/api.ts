export type City = "hanoi" | "danang" | "hcm";
export interface PaginatedData<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}
export interface Observation {
  id: string;
  city: City;
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
  city: City;
  method: string;
  is_ai: boolean;
  message: string;
  predicted_temperature: number;
  target_at: string;
  based_on: string;
}
export async function api<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`/api/v1${path}`, { signal });
  const body = await response.json().catch(() => null);
  if (!response.ok || body?.success !== true) {
    throw new Error(
      body?.error?.message || `Không tải được dữ liệu (${response.status}).`,
    );
  }
  return body.data as T;
}
