import { useEffect, useState } from "react";
import { connectionState, subscribe } from "../lib/connection";

export interface ConnectionState {
  online: boolean;
  /** Incremented every time the browser reports that the network is back. */
  restored: number;
}

export function useConnection(): ConnectionState {
  const [state, setState] = useState<ConnectionState>(connectionState);
  useEffect(() => subscribe((online, restored) => setState({ online, restored })), []);
  return state;
}
