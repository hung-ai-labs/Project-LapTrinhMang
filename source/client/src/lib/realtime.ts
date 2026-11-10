// Reconnect policy for the realtime weather socket.
export const BASE_BACKOFF_MS = 1000;
export const MAX_BACKOFF_MS = 15000;
export const HEARTBEAT_TIMEOUT_MS = 45000;
export const HEARTBEAT_CHECK_MS = 5000;

export function backoffDelay(attempt: number): number {
  const step = Number.isFinite(attempt) && attempt > 0 ? Math.floor(attempt) : 0;
  return Math.min(BASE_BACKOFF_MS * 2 ** step, MAX_BACKOFF_MS);
}

export function heartbeatExpired(
  lastMessageAt: number,
  now: number,
  timeout: number = HEARTBEAT_TIMEOUT_MS,
): boolean {
  if (!Number.isFinite(lastMessageAt) || !Number.isFinite(now)) return false;
  return now - lastMessageAt > timeout;
}
