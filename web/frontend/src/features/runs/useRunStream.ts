// Slice D1 — `useRunStream`
//
// Subscribes to `ws://${host}/api/ws/runs/{runId}/stream` while a run is
// flagged as `running` and exposes accumulated live state:
//
//   - per-phase rolling log buffer (capped at LOG_LINES_PER_PHASE_CAP)
//   - per-phase progress (completed / total batches when available)
//   - per-phase running cost in USD
//   - `connected` flag + `reconnectAttempt` counter for the header badge
//   - cumulative `droppedCount` of log lines the backend dropped server-side
//
// Lifecycle:
//   - When `enabled` flips to `true` we open the socket.
//   - When the socket closes with a non-1000 code we retry with the
//     backoff schedule [1, 2, 5, 10, 30] (seconds); after MAX_ATTEMPTS we
//     give up and surface `connected: false`.
//   - When `enabled` flips to `false` (e.g. the run terminated) we close
//     cleanly and stop reconnecting.
//   - On unmount the socket is closed and any pending reconnect timer is
//     cleared so we don't leak handles between routes.

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import type { RunDetail, StreamEvent } from "./types";

/**
 * Maximum number of log lines retained per phase. Above this we drop the
 * oldest entries; `LogTail` is display-only and assumes the hook has
 * already capped the buffer.
 */
export const LOG_LINES_PER_PHASE_CAP = 5000;

/**
 * Exponential-ish backoff schedule (seconds) for WebSocket reconnects.
 * The 6th-and-onward attempt repeats the last value (30s) until the
 * `MAX_RECONNECT_ATTEMPTS` ceiling is reached.
 */
export const RECONNECT_BACKOFF_SECONDS: readonly number[] = [1, 2, 5, 10, 30];

/** Hard ceiling on reconnect attempts before the hook surrenders. */
export const MAX_RECONNECT_ATTEMPTS = 10;

/** Per-phase progress snapshot. */
export interface PhaseProgress {
  completed: number;
  total: number;
  /** Raw `snapshot` payload from the backend, useful for tooltip display. */
  snapshot?: Record<string, unknown>;
}

/** Per-phase cost accumulator. */
export interface PhaseCost {
  /** Running USD total for this phase (sum of `delta_usd` events). */
  cost_usd: number;
}

export interface UseRunStreamResult {
  /** Map of phase_id -> capped log buffer. */
  logsByPhase: Record<string, string[]>;
  /** Map of phase_id -> latest progress snapshot. */
  progressByPhase: Record<string, PhaseProgress>;
  /** Map of phase_id -> cumulative cost. */
  costByPhase: Record<string, PhaseCost>;
  /** Cumulative number of log lines the backend has dropped. */
  droppedCount: number;
  /** True while a WebSocket is OPEN. */
  connected: boolean;
  /**
   * 1-based attempt counter while we're in the middle of reconnecting.
   * 0 when not currently reconnecting (either freshly connected, or we
   * have surrendered).
   */
  reconnectAttempt: number;
  /** True once we've burnt through `MAX_RECONNECT_ATTEMPTS`. */
  givenUp: boolean;
}

interface UseRunStreamOptions {
  /**
   * When `false`, the hook is dormant — no socket is opened, no
   * accumulators are kept. Toggling back to `true` re-initialises state.
   */
  enabled: boolean;
}

/**
 * Resolve the absolute `ws://` / `wss://` URL for a run stream.
 *
 * Tests can pass a hand-rolled `location`-like object; production code
 * defers to `window.location`.
 */
export function buildStreamUrl(
  runId: string,
  loc: { protocol: string; host: string } = window.location,
): string {
  const scheme = loc.protocol === "https:" ? "wss:" : "ws:";
  return `${scheme}//${loc.host}/api/ws/runs/${encodeURIComponent(runId)}/stream`;
}

function appendCapped(buf: string[], line: string, cap: number): string[] {
  if (buf.length < cap) {
    return [...buf, line];
  }
  // Drop oldest. Allocating a new array is cheaper than splice() on the
  // mutable buffer once we factor in React's referential-equality checks.
  return [...buf.slice(buf.length - cap + 1), line];
}

export function useRunStream(
  runId: string | undefined,
  options: UseRunStreamOptions,
): UseRunStreamResult {
  const { enabled } = options;
  const queryClient = useQueryClient();

  const [logsByPhase, setLogsByPhase] = useState<Record<string, string[]>>({});
  const [progressByPhase, setProgressByPhase] = useState<
    Record<string, PhaseProgress>
  >({});
  const [costByPhase, setCostByPhase] = useState<Record<string, PhaseCost>>({});
  const [droppedCount, setDroppedCount] = useState(0);
  const [connected, setConnected] = useState(false);
  const [reconnectAttempt, setReconnectAttempt] = useState(0);
  const [givenUp, setGivenUp] = useState(false);

  // Refs are used for handles whose identity must not trigger a render.
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<number | null>(null);
  // We deliberately track the "current run we are streaming" inside the
  // effect so a runId change tears down cleanly before opening a new
  // socket; this avoids a half-reconnect on quick route changes.
  const attemptsRef = useRef(0);
  const terminatedRef = useRef(false);

  /** Bump the TanStack-Query detail cache from a snapshot frame. */
  const upsertDetailCache = useCallback(
    (rid: string, snap: RunDetail | Record<string, unknown> | null) => {
      if (snap === null) return;
      // The supervisor's `LiveStatus` shape doesn't carry every field
      // the REST `RunDetail` does — we merge over the previous cache so
      // file-system-only fields (`branch_name`, `spec_sources`, ...) are
      // preserved across reconnects.
      queryClient.setQueryData<RunDetail | undefined>(
        ["runs", "detail", rid],
        (prev) => {
          if (!prev) return snap as RunDetail;
          return { ...prev, ...(snap as Partial<RunDetail>) };
        },
      );
    },
    [queryClient],
  );

  // Reset accumulators whenever the run we're streaming changes; without
  // this, navigating between two running runs would show the other run's
  // log tail until the new socket caught up.
  useEffect(() => {
    setLogsByPhase({});
    setProgressByPhase({});
    setCostByPhase({});
    setDroppedCount(0);
    setReconnectAttempt(0);
    setGivenUp(false);
    attemptsRef.current = 0;
    terminatedRef.current = false;
  }, [runId]);

  useEffect(() => {
    if (!enabled || !runId) {
      return;
    }

    let cancelled = false;
    terminatedRef.current = false;

    const clearReconnectTimer = () => {
      if (reconnectTimerRef.current !== null) {
        window.clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
    };

    const handleEvent = (event: StreamEvent) => {
      switch (event.type) {
        case "state_snapshot":
          upsertDetailCache(runId, event.data);
          break;
        case "phase_started":
          // Surface in progress map so the row badge can flip from
          // "queued" to "running" without waiting for the next REST poll.
          setProgressByPhase((prev) => ({
            ...prev,
            [event.phase]: prev[event.phase] ?? { completed: 0, total: 0 },
          }));
          break;
        case "phase_progress": {
          const completed =
            typeof event.completed === "number" ? event.completed : undefined;
          const total =
            typeof event.total === "number" ? event.total : undefined;
          setProgressByPhase((prev) => {
            const prior = prev[event.phase] ?? { completed: 0, total: 0 };
            return {
              ...prev,
              [event.phase]: {
                completed: completed ?? prior.completed,
                total: total ?? prior.total,
                snapshot: event.snapshot ?? prior.snapshot,
              },
            };
          });
          break;
        }
        case "log_line":
          setLogsByPhase((prev) => {
            const buf = prev[event.phase] ?? [];
            return {
              ...prev,
              [event.phase]: appendCapped(
                buf,
                event.line,
                LOG_LINES_PER_PHASE_CAP,
              ),
            };
          });
          break;
        case "cost_update": {
          const delta = Number(event.delta_usd) || 0;
          if (delta !== 0) {
            setCostByPhase((prev) => {
              const prior = prev[event.phase]?.cost_usd ?? 0;
              return {
                ...prev,
                [event.phase]: { cost_usd: prior + delta },
              };
            });
          }
          break;
        }
        case "phase_completed":
          // Force a REST refetch so the manifest-side fields (duration,
          // ended_at) settle without waiting for the next list refresh.
          queryClient.invalidateQueries({
            queryKey: ["runs", "detail", runId],
          });
          break;
        case "run_terminated":
          terminatedRef.current = true;
          // Final refetch so the page transitions out of "running" UI.
          queryClient.invalidateQueries({
            queryKey: ["runs", "detail", runId],
          });
          queryClient.invalidateQueries({ queryKey: ["runs", "list"] });
          break;
        case "log_dropped":
          setDroppedCount((prev) => prev + (Number(event.count) || 0));
          break;
        case "ping":
        case "error":
          // ping: explicitly ignored (keepalive only).
          // error: backend already closed; rely on onclose to reconnect.
          break;
      }
    };

    const open = () => {
      if (cancelled) return;
      clearReconnectTimer();
      let ws: WebSocket;
      try {
        ws = new WebSocket(buildStreamUrl(runId));
      } catch (err) {
        // Malformed URL or browser denial — treat like a closed socket
        // so the backoff branch can kick in.
        // eslint-disable-next-line no-console
        console.warn("speca: failed to construct WS", err);
        scheduleReconnect();
        return;
      }
      wsRef.current = ws;

      ws.onopen = () => {
        if (cancelled) {
          ws.close(1000, "unmounted");
          return;
        }
        setConnected(true);
        setReconnectAttempt(0);
        attemptsRef.current = 0;
      };

      ws.onmessage = (msg) => {
        if (cancelled) return;
        try {
          const parsed = JSON.parse(msg.data as string) as StreamEvent;
          handleEvent(parsed);
        } catch (err) {
          // eslint-disable-next-line no-console
          console.warn("speca: malformed WS frame", err, msg.data);
        }
      };

      ws.onerror = () => {
        // We don't surface errors directly — `onclose` always follows
        // and carries the close code, which is the more useful signal.
      };

      ws.onclose = (closeEv) => {
        wsRef.current = null;
        setConnected(false);
        if (cancelled) return;
        // 1000 = normal closure from the server (run terminated). Or we
        // received `run_terminated` first and shouldn't reconnect.
        if (closeEv.code === 1000 || terminatedRef.current) {
          return;
        }
        scheduleReconnect();
      };
    };

    const scheduleReconnect = () => {
      if (cancelled) return;
      if (attemptsRef.current >= MAX_RECONNECT_ATTEMPTS) {
        setGivenUp(true);
        setReconnectAttempt(0);
        return;
      }
      const delaySec =
        RECONNECT_BACKOFF_SECONDS[
          Math.min(attemptsRef.current, RECONNECT_BACKOFF_SECONDS.length - 1)
        ];
      attemptsRef.current += 1;
      setReconnectAttempt(attemptsRef.current);
      clearReconnectTimer();
      reconnectTimerRef.current = window.setTimeout(() => {
        reconnectTimerRef.current = null;
        open();
      }, delaySec * 1000);
    };

    open();

    return () => {
      cancelled = true;
      clearReconnectTimer();
      const ws = wsRef.current;
      wsRef.current = null;
      if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
        try {
          ws.close(1000, "unmounted");
        } catch {
          // Ignore — browsers throw if close() is called during connecting.
        }
      }
      setConnected(false);
    };
    // We intentionally re-run on `enabled` *and* `runId`; the cache
    // helpers are memoised so they don't add churn.
  }, [enabled, runId, queryClient, upsertDetailCache]);

  return useMemo(
    () => ({
      logsByPhase,
      progressByPhase,
      costByPhase,
      droppedCount,
      connected,
      reconnectAttempt,
      givenUp,
    }),
    [
      logsByPhase,
      progressByPhase,
      costByPhase,
      droppedCount,
      connected,
      reconnectAttempt,
      givenUp,
    ],
  );
}
