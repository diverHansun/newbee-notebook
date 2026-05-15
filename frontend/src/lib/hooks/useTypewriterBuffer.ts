"use client";

import { useCallback, useEffect, useRef } from "react";

import { buildMarkdownVisibleMap, type MarkdownVisibleMap } from "@/lib/utils/markdown-typewriter";

const DEFAULT_BASE_CPS = 60;
const DEFAULT_DRAIN_CPS = 240;
const DRAIN_RAMP_MS = 240;

type BufferState = {
  rawContent: string;
  visibleMap: MarkdownVisibleMap;
  visibleChars: number;
  displayedRawIndex: number;
  fractionalCarry: number;
  lastTickAt: number | null;
  drainPending: boolean;
  drainStartedAt: number | null;
  rafHandle: number | null;
};

export type UseTypewriterBufferOptions = {
  onDelta: (visibleDelta: string) => void;
  baseCharsPerSecond?: number;
  drainCharsPerSecond?: number;
};

export type TypewriterBuffer = {
  push: (delta: string) => void;
  flush: () => void;
  drain: () => void;
  reset: () => void;
};

export function useTypewriterBuffer({
  onDelta,
  baseCharsPerSecond = DEFAULT_BASE_CPS,
  drainCharsPerSecond = DEFAULT_DRAIN_CPS,
}: UseTypewriterBufferOptions): TypewriterBuffer {
  const stateRef = useRef<BufferState | null>(null);
  const onDeltaRef = useRef(onDelta);

  useEffect(() => {
    onDeltaRef.current = onDelta;
  }, [onDelta]);

  const cancelFrame = useCallback(() => {
    const state = stateRef.current;
    if (!state || state.rafHandle === null) return;
    window.cancelAnimationFrame(state.rafHandle);
    state.rafHandle = null;
  }, []);

  const emitDelta = useCallback((delta: string) => {
    if (!delta) return;
    onDeltaRef.current(delta);
  }, []);

  const runFrame = useCallback(
    (now: number) => {
      const state = stateRef.current;
      if (!state) return;
      state.rafHandle = null;

      const lastTickAt = state.lastTickAt ?? now;
      const elapsedMs = Math.max(0, now - lastTickAt);
      state.lastTickAt = now;

      let cps = baseCharsPerSecond;
      if (state.drainPending) {
        if (state.drainStartedAt === null) {
          state.drainStartedAt = now;
        }
        const ramp = Math.min(1, Math.max(0, (now - state.drainStartedAt) / DRAIN_RAMP_MS));
        cps = baseCharsPerSecond + (drainCharsPerSecond - baseCharsPerSecond) * ramp;
      }

      state.fractionalCarry += (elapsedMs / 1000) * cps;
      const stepChars = Math.floor(state.fractionalCarry);
      if (stepChars > 0) {
        state.fractionalCarry -= stepChars;
        state.visibleChars = Math.min(
          state.visibleMap.totalVisibleChars,
          state.visibleChars + stepChars
        );
      }

      const nextRawIndex =
        state.visibleMap.visibleToRawIndex[state.visibleChars] ?? state.rawContent.length;
      if (nextRawIndex > state.displayedRawIndex) {
        const delta = state.rawContent.slice(state.displayedRawIndex, nextRawIndex);
        state.displayedRawIndex = nextRawIndex;
        emitDelta(delta);
      }

      const reachedTarget =
        state.visibleChars >= state.visibleMap.totalVisibleChars &&
        state.displayedRawIndex >= state.rawContent.length;

      if (reachedTarget) {
        state.drainPending = false;
        state.drainStartedAt = null;
        return;
      }

      state.rafHandle = window.requestAnimationFrame(runFrame);
    },
    [baseCharsPerSecond, drainCharsPerSecond, emitDelta]
  );

  const ensureRunning = useCallback(() => {
    const state = stateRef.current;
    if (!state || state.rafHandle !== null) return;
    state.rafHandle = window.requestAnimationFrame(runFrame);
  }, [runFrame]);

  const push = useCallback(
    (delta: string) => {
      if (!delta) return;
      let state = stateRef.current;
      if (!state) {
        state = {
          rawContent: "",
          visibleMap: buildMarkdownVisibleMap(""),
          visibleChars: 0,
          displayedRawIndex: 0,
          fractionalCarry: 0,
          lastTickAt: null,
          drainPending: false,
          drainStartedAt: null,
          rafHandle: null,
        };
        stateRef.current = state;
      }

      state.rawContent += delta;
      state.visibleMap = buildMarkdownVisibleMap(state.rawContent);
      state.visibleChars = Math.min(state.visibleChars, state.visibleMap.totalVisibleChars);

      const immediateRawIndex =
        state.visibleMap.visibleToRawIndex[state.visibleChars] ?? state.rawContent.length;
      if (immediateRawIndex > state.displayedRawIndex) {
        const immediateDelta = state.rawContent.slice(state.displayedRawIndex, immediateRawIndex);
        state.displayedRawIndex = immediateRawIndex;
        emitDelta(immediateDelta);
      }

      ensureRunning();
    },
    [emitDelta, ensureRunning]
  );

  const flush = useCallback(() => {
    const state = stateRef.current;
    if (!state) return;
    state.visibleChars = state.visibleMap.totalVisibleChars;
    state.fractionalCarry = 0;
    state.drainPending = false;
    state.drainStartedAt = null;
    cancelFrame();
    if (state.rawContent.length > state.displayedRawIndex) {
      const remaining = state.rawContent.slice(state.displayedRawIndex);
      state.displayedRawIndex = state.rawContent.length;
      emitDelta(remaining);
    }
  }, [cancelFrame, emitDelta]);

  const drain = useCallback(() => {
    const state = stateRef.current;
    if (!state) return;
    const hasRemaining =
      state.visibleChars < state.visibleMap.totalVisibleChars ||
      state.displayedRawIndex < state.rawContent.length;
    if (!hasRemaining) return;
    state.drainPending = true;
    state.drainStartedAt = null;
    ensureRunning();
  }, [ensureRunning]);

  const reset = useCallback(() => {
    cancelFrame();
    stateRef.current = null;
  }, [cancelFrame]);

  useEffect(() => {
    return () => {
      cancelFrame();
      stateRef.current = null;
    };
  }, [cancelFrame]);

  return { push, flush, drain, reset };
}
