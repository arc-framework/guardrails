/**
 * Generic timed playback over an ordered sequence of node ids. Drives the
 * "active-flow animation" both for the new-flow architecture canvas (when
 * a rid is supplied, we feed it the executed-stage sequence) and the
 * workspace LifecycleCanvas (same idea, against the canonical 12-stage
 * graph instead of the architecture diagram).
 *
 * State machine:
 *
 *   idle         — playhead at end (or empty path); play() restarts
 *   playing      — advancing every `stepMs` ms
 *   paused       — manually paused; resume() continues from current step
 *   complete     — reached end of path; auto-pauses at the last step
 *
 * The hook deliberately does NOT animate via requestAnimationFrame — we
 * step in discrete 250–500 ms beats so each stage is readable, not
 * interpolated. Operators report "I want to see what happened next", not
 * "I want a movie".
 */

import { useCallback, useEffect, useRef, useState } from "react";

export type PlaybackStatus = "idle" | "playing" | "paused" | "complete";

export interface UsePathPlaybackOptions {
  /** Ordered list of node ids in the path. Empty = no animation. */
  path: string[];
  /** Milliseconds between steps. Default 400. */
  stepMs?: number;
  /** Auto-start when the path becomes non-empty. Default false. */
  autoStart?: boolean;
}

export interface UsePathPlaybackReturn {
  /** Index into `path` of the most recently activated node, or -1 if not started. */
  currentIndex: number;
  /** Current node id, or null. */
  currentId: string | null;
  /** Set of ids visited so far (inclusive of current). */
  visited: Set<string>;
  status: PlaybackStatus;
  /** Start (or restart) playback from index 0. */
  play: () => void;
  /** Pause an in-flight playback. */
  pause: () => void;
  /** Resume a paused playback. */
  resume: () => void;
  /** Jump straight to the end (mark all as visited). */
  skipToEnd: () => void;
  /** Return to idle (currentIndex = -1, no visited). */
  reset: () => void;
}

const DEFAULT_STEP_MS = 400;

export function usePathPlayback({
  path,
  stepMs = DEFAULT_STEP_MS,
  autoStart = false,
}: UsePathPlaybackOptions): UsePathPlaybackReturn {
  const [currentIndex, setCurrentIndex] = useState(-1);
  const [status, setStatus] = useState<PlaybackStatus>("idle");
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const clearTimer = useCallback(() => {
    if (timerRef.current !== null) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  // Scheduled tick: advance one step. We use setTimeout (not setInterval)
  // so a paused-then-resumed sequence doesn't fire backlogged ticks all at
  // once.
  useEffect(() => {
    if (status !== "playing") return;
    if (currentIndex >= path.length - 1) {
      setStatus("complete");
      return;
    }
    timerRef.current = setTimeout(() => {
      setCurrentIndex((idx) => Math.min(idx + 1, path.length - 1));
    }, stepMs);
    return clearTimer;
  }, [status, currentIndex, path.length, stepMs, clearTimer]);

  // Auto-start when the path arrives.
  useEffect(() => {
    if (!autoStart) return;
    if (path.length === 0) return;
    if (status !== "idle") return;
    setCurrentIndex(0);
    setStatus("playing");
  }, [autoStart, path.length, status]);

  // Reset on path identity change so a different rid restarts the timeline.
  const pathKey = path.join("|");
  useEffect(() => {
    clearTimer();
    setCurrentIndex(-1);
    setStatus("idle");
  }, [pathKey, clearTimer]);

  const play = useCallback(() => {
    clearTimer();
    if (path.length === 0) return;
    setCurrentIndex(0);
    setStatus("playing");
  }, [path.length, clearTimer]);

  const pause = useCallback(() => {
    clearTimer();
    setStatus((s) => (s === "playing" ? "paused" : s));
  }, [clearTimer]);

  const resume = useCallback(() => {
    setStatus((s) => (s === "paused" ? "playing" : s));
  }, []);

  const skipToEnd = useCallback(() => {
    clearTimer();
    if (path.length === 0) return;
    setCurrentIndex(path.length - 1);
    setStatus("complete");
  }, [path.length, clearTimer]);

  const reset = useCallback(() => {
    clearTimer();
    setCurrentIndex(-1);
    setStatus("idle");
  }, [clearTimer]);

  const visited = new Set<string>();
  for (let i = 0; i <= currentIndex && i < path.length; i++) {
    const id = path[i];
    if (id) visited.add(id);
  }
  const currentId = currentIndex >= 0 ? (path[currentIndex] ?? null) : null;

  return {
    currentIndex,
    currentId,
    visited,
    status,
    play,
    pause,
    resume,
    skipToEnd,
    reset,
  };
}
