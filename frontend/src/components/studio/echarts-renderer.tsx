"use client";

import { saveAs } from "file-saver";
import {
  forwardRef,
  useEffect,
  useImperativeHandle,
  useMemo,
  useRef,
  useState,
} from "react";

import {
  ECHARTS_SERIES_TYPE_WHITELIST,
  echarts,
  ensureEChartsRegistered,
} from "@/lib/diagram/echarts-modules";
import { useTheme } from "@/lib/theme/theme-context";

import type { DiagramExportHandle } from "@/components/studio/reactflow-renderer";

type EChartsRendererProps = {
  content: string;
  height?: number | string;
};

const DEFAULT_HEIGHT = 320;

type EChartsInstance = ReturnType<typeof echarts.init>;

type ParseResult =
  | { status: "ok"; option: Record<string, unknown> }
  | { status: "error"; message: string };

function tryParseOption(content: string): ParseResult {
  const normalized = content.trim();
  if (!normalized) {
    return { status: "error", message: "empty" };
  }
  try {
    const parsed = JSON.parse(normalized) as unknown;
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
      return { status: "error", message: "not an object" };
    }
    return { status: "ok", option: parsed as Record<string, unknown> };
  } catch (err) {
    return { status: "error", message: (err as Error).message };
  }
}

function applyDarkOverlay(option: Record<string, unknown>): Record<string, unknown> {
  return {
    ...option,
    backgroundColor: "transparent",
    textStyle: {
      ...(typeof option.textStyle === "object" && option.textStyle !== null
        ? (option.textStyle as Record<string, unknown>)
        : {}),
      color: "hsl(210, 40%, 92%)",
    },
  };
}

function applyLightOverlay(option: Record<string, unknown>): Record<string, unknown> {
  return {
    ...option,
    backgroundColor: "transparent",
  };
}

export const EChartsRenderer = forwardRef<DiagramExportHandle, EChartsRendererProps>(
  function EChartsRenderer({ content, height = DEFAULT_HEIGHT }, ref) {
    const { theme } = useTheme();
    const isDark = theme === "dark";
    const containerRef = useRef<HTMLDivElement>(null);
    const instanceRef = useRef<EChartsInstance | null>(null);
    const [renderError, setRenderError] = useState<string | null>(null);

    const parsed = useMemo(() => tryParseOption(content), [content]);

    useEffect(() => {
      ensureEChartsRegistered();
    }, []);

    useEffect(() => {
      const container = containerRef.current;
      if (!container) return;
      if (parsed.status !== "ok") {
        if (instanceRef.current) {
          instanceRef.current.dispose();
          instanceRef.current = null;
        }
        return;
      }

      let instance = instanceRef.current;
      const targetTheme = isDark ? "dark" : undefined;
      const existingTheme = (instance as unknown as { _theme?: string } | null)?._theme;
      if (instance && existingTheme !== targetTheme) {
        instance.dispose();
        instance = null;
        instanceRef.current = null;
      }

      if (!instance) {
        instance = echarts.init(container, targetTheme, { renderer: "canvas" });
        (instance as unknown as { _theme?: string })._theme = targetTheme ?? "";
        instanceRef.current = instance;
      }

      const overlayed = isDark ? applyDarkOverlay(parsed.option) : applyLightOverlay(parsed.option);
      try {
        instance.setOption(overlayed, { notMerge: true });
        setRenderError(null);
      } catch (err) {
        setRenderError((err as Error).message);
      }
    }, [parsed, isDark]);

    useEffect(() => {
      const container = containerRef.current;
      if (!container || typeof ResizeObserver === "undefined") return;
      const observer = new ResizeObserver(() => {
        instanceRef.current?.resize();
      });
      observer.observe(container);
      return () => observer.disconnect();
    }, []);

    useEffect(() => {
      return () => {
        if (instanceRef.current) {
          instanceRef.current.dispose();
          instanceRef.current = null;
        }
      };
    }, []);

    useImperativeHandle(ref, () => ({
      async exportImage(filename: string) {
        const instance = instanceRef.current;
        if (!instance) return;
        const dataUrl = instance.getDataURL({
          type: "png",
          pixelRatio: 2,
          backgroundColor: "#ffffff",
        });
        const response = await fetch(dataUrl);
        const blob = await response.blob();
        saveAs(blob, filename);
      },
    }));

    if (parsed.status === "error") {
      return (
        <pre
          data-testid="echarts-renderer-fallback"
          style={{
            margin: 0,
            whiteSpace: "pre-wrap",
            wordBreak: "break-word",
            fontFamily: "\"Cascadia Code\", monospace",
            fontSize: 12,
            lineHeight: 1.5,
          }}
        >
          {content}
        </pre>
      );
    }

    return (
      <div
        ref={containerRef}
        data-testid="echarts-renderer-canvas"
        data-render-error={renderError ?? undefined}
        style={{
          width: "100%",
          height: typeof height === "number" ? `${height}px` : height,
        }}
      />
    );
  }
);

export { ECHARTS_SERIES_TYPE_WHITELIST };
