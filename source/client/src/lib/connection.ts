// Single source of truth for the browser connection state.
type Listener = (online: boolean, restored: number) => void;

let restored = 0;
let online = typeof navigator === "undefined" ? true : navigator.onLine;
const listeners = new Set<Listener>();
let started = false;

function emit() {
  for (const listener of [...listeners]) listener(online, restored);
}

function ensureStarted() {
  if (started || typeof window === "undefined") return;
  started = true;
  window.addEventListener("online", () => {
    online = true;
    restored += 1;
    emit();
  });
  window.addEventListener("offline", () => {
    online = false;
    emit();
  });
}

/** Subscribe to connection changes; returns the unsubscribe function. */
export function subscribe(listener: Listener): () => void {
  ensureStarted();
  listeners.add(listener);
  return () => { listeners.delete(listener); };
}

export function connectionState(): { online: boolean; restored: number } {
  return { online, restored };
}
