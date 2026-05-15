import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useTypewriterBuffer } from "@/lib/hooks/useTypewriterBuffer";

describe("useTypewriterBuffer", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.stubGlobal("requestAnimationFrame", (callback: FrameRequestCallback) =>
      window.setTimeout(() => callback(window.performance.now()), 16)
    );
    vi.stubGlobal("cancelAnimationFrame", (handle: number) => {
      window.clearTimeout(handle);
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  it("reveals pushed content over animation frames", () => {
    const deltas: string[] = [];
    const { result } = renderHook(() =>
      useTypewriterBuffer({
        onDelta: (delta) => deltas.push(delta),
        baseCharsPerSecond: 60,
      })
    );

    act(() => {
      result.current.push("Hello");
    });

    expect(deltas.join("")).not.toBe("Hello");

    act(() => {
      vi.advanceTimersByTime(120);
    });

    expect(deltas.join("")).toBe("Hello");
  });

  it("flushes the remaining content immediately", () => {
    const deltas: string[] = [];
    const { result } = renderHook(() =>
      useTypewriterBuffer({
        onDelta: (delta) => deltas.push(delta),
        baseCharsPerSecond: 1,
      })
    );

    act(() => {
      result.current.push("Hello");
      result.current.flush();
    });

    expect(deltas.join("")).toBe("Hello");
  });

  it("drain() finishes remaining content via accelerated ramp, not instantly", () => {
    const deltas: string[] = [];
    const { result } = renderHook(() =>
      useTypewriterBuffer({
        onDelta: (delta) => deltas.push(delta),
        baseCharsPerSecond: 60,
        drainCharsPerSecond: 240,
      })
    );

    act(() => {
      result.current.push("Hello world");
      result.current.drain();
    });

    expect(deltas.join("")).not.toBe("Hello world");

    act(() => {
      vi.advanceTimersByTime(80);
    });
    expect(deltas.join("")).not.toBe("Hello world");

    act(() => {
      vi.advanceTimersByTime(800);
    });
    expect(deltas.join("")).toBe("Hello world");
  });

  it("starts fresh after reset", () => {
    const deltas: string[] = [];
    const { result } = renderHook(() =>
      useTypewriterBuffer({
        onDelta: (delta) => deltas.push(delta),
        baseCharsPerSecond: 1,
      })
    );

    act(() => {
      result.current.push("Old");
      result.current.reset();
      result.current.push("New");
      result.current.flush();
    });

    expect(deltas.join("")).toBe("New");
  });
});
