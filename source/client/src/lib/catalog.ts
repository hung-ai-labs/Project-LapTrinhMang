// Resource loading with an offline cache, background retry and an explicit refresh trigger.
import { nextRetryDelay } from "./realtime";

export const PROVINCE_CACHE_KEY = "weather-stream.catalog.provinces";
export const SELECTION_CACHE_KEY = "weather-stream.selection";

export const wardCacheKey = (provinceId: string) => `weather-stream.catalog.wards.${provinceId}`;
export const forecastCacheKey = (wardId: string) => `weather-stream.forecast.${wardId}`;

export interface StoredSelection {
  provinceId: string | null;
  wardId: string | null;
  wardName: string | null;
}

export interface ResourceCache<T> {
  key: string;
  parse: (raw: string) => T | null;
  serialize: (value: T) => string;
}

export interface ResourceLoaderOptions<T> {
  load: (signal: AbortSignal) => Promise<T>;
  onValue: (value: T, fromCache: boolean) => void;
  onError: (message: string, error: unknown) => void;
  onLoading?: (loading: boolean) => void;
  cache?: ResourceCache<T>;
  retryDelay?: (attempt: number) => number;
  pollIntervalMs?: number;
  storage?: Storage | null;
}

export function browserStorage(): Storage | null {
  try {
    return typeof window === "undefined" ? null : window.localStorage;
  } catch {
    return null;
  }
}

export function readRaw(key: string, storage: Storage | null = browserStorage()): string | null {
  try {
    return storage?.getItem(key) ?? null;
  } catch {
    return null;
  }
}

export function writeRaw(key: string, raw: string, storage: Storage | null = browserStorage()) {
  try {
    storage?.setItem(key, raw);
  } catch {
    // A full or disabled storage must not break the dashboard.
  }
}

export function readSelection(storage: Storage | null = browserStorage()): StoredSelection {
  const empty: StoredSelection = { provinceId: null, wardId: null, wardName: null };
  const raw = readRaw(SELECTION_CACHE_KEY, storage);
  if (!raw) return empty;
  try {
    const value = JSON.parse(raw) as Partial<StoredSelection>;
    return {
      provinceId: typeof value.provinceId === "string" ? value.provinceId : null,
      wardId: typeof value.wardId === "string" ? value.wardId : null,
      wardName: typeof value.wardName === "string" ? value.wardName : null,
    };
  } catch {
    return empty;
  }
}

export function writeSelection(selection: StoredSelection, storage: Storage | null = browserStorage()) {
  writeRaw(SELECTION_CACHE_KEY, JSON.stringify(selection), storage);
}

/**
 * Keeps the last known value on screen while a request fails and retries in the
 * background, so an outage never empties the dashboard and every resource
 * recovers on its own as soon as the network is back.
 */
export class ResourceLoader<T> {
  private readonly options: ResourceLoaderOptions<T>;
  private controller: AbortController | undefined;
  private retryTimer: ReturnType<typeof setTimeout> | undefined;
  private pollTimer: ReturnType<typeof setInterval> | undefined;
  private attempt = 0;
  private stopped = false;

  constructor(options: ResourceLoaderOptions<T>) {
    this.options = options;
  }

  start(): void {
    const cache = this.options.cache;
    if (cache) {
      const raw = readRaw(cache.key, this.options.storage ?? undefined);
      if (raw) {
        const cached = cache.parse(raw);
        if (cached !== null) this.options.onValue(cached, true);
      }
    }
    void this.load();
  }

  /** Reload right now, for example when the browser reports that the network is back. */
  refresh(): void {
    this.attempt = 0;
    this.clearRetry();
    void this.load();
  }

  stop(): void {
    this.stopped = true;
    this.clearRetry();
    this.clearPoll();
    this.controller?.abort();
  }

  private clearRetry() {
    if (this.retryTimer !== undefined) {
      clearTimeout(this.retryTimer);
      this.retryTimer = undefined;
    }
  }

  private clearPoll() {
    if (this.pollTimer !== undefined) {
      clearInterval(this.pollTimer);
      this.pollTimer = undefined;
    }
  }

  private schedulePoll() {
    this.clearPoll();
    const interval = this.options.pollIntervalMs;
    if (!interval) return;
    this.pollTimer = setInterval(() => { void this.load(); }, interval);
  }

  private async load(): Promise<void> {
    if (this.stopped) return;
    this.controller?.abort();
    const controller = new AbortController();
    this.controller = controller;
    this.options.onLoading?.(true);
    try {
      const value = await this.options.load(controller.signal);
      if (this.stopped || controller.signal.aborted) return;
      this.attempt = 0;
      const cache = this.options.cache;
      if (cache) writeRaw(cache.key, cache.serialize(value), this.options.storage ?? undefined);
      this.options.onValue(value, false);
      this.options.onError("", null);
      this.schedulePoll();
    } catch (error) {
      if (this.stopped || controller.signal.aborted) return;
      this.options.onError(
        error instanceof Error ? error.message : "Không tải được dữ liệu.", error,
      );
      this.clearPoll();
      const delay = (this.options.retryDelay ?? nextRetryDelay)(this.attempt++);
      this.clearRetry();
      this.retryTimer = setTimeout(() => { void this.load(); }, delay);
    } finally {
      if (!this.stopped) this.options.onLoading?.(false);
    }
  }
}
