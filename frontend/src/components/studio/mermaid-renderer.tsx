"use client";

import { saveAs } from "file-saver";
import { toPng } from "html-to-image";
import mermaid from "mermaid";
import {
  forwardRef,
  useCallback,
  useEffect,
  useId,
  useImperativeHandle,
  useRef,
  useState,
  type PointerEvent as ReactPointerEvent,
  type WheelEvent as ReactWheelEvent,
} from "react";

import type { DiagramExportHandle } from "@/components/studio/reactflow-renderer";

type MermaidRendererProps = {
  syntax: string;
};

const MIN_ZOOM = 0.4;
const MAX_ZOOM = 2.2;
const ZOOM_STEP = 0.1;

function clampZoom(value: number): number {
  return Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, Number(value.toFixed(2))));
}

export const MermaidRenderer = forwardRef<DiagramExportHandle, MermaidRendererProps>(
  function MermaidRenderer({ syntax }, ref) {
  const mermaidId = useId().replace(/:/g, "-");
  const [svgMarkup, setSvgMarkup] = useState("");
  const [pending, setPending] = useState(false);
  const [zoom, setZoom] = useState(1);
  const [offset, setOffset] = useState({ x: 0, y: 0 });
  const canvasRef = useRef<HTMLDivElement>(null);
  const dragStartRef = useRef<{
    pointerX: number;
    pointerY: number;
    startX: number;
    startY: number;
  } | null>(null);

  useEffect(() => {
    if (syntax.trim().length === 0) {
      setSvgMarkup("");
      setPending(false);
      return;
    }

    let active = true;
    const theme =
      typeof document !== "undefined" && document.documentElement.classList.contains("dark")
        ? "dark"
        : "default";

    setPending(true);
    mermaid.initialize({
      startOnLoad: false,
      securityLevel: "loose",
      theme,
    });

    mermaid
      .render(`diagram-${mermaidId}`, syntax)
      .then(({ svg }) => {
        if (!active) return;
        setSvgMarkup(svg);
        setPending(false);
        setZoom(1);
        setOffset({ x: 0, y: 0 });
      })
      .catch(() => {
        if (!active) return;
        setSvgMarkup("");
        setPending(false);
      });

    return () => {
      active = false;
    };
  }, [mermaidId, syntax]);

  const zoomIn = useCallback(() => {
    setZoom((current) => clampZoom(current + ZOOM_STEP));
  }, []);

  const zoomOut = useCallback(() => {
    setZoom((current) => clampZoom(current - ZOOM_STEP));
  }, []);

  const resetView = useCallback(() => {
    setZoom(1);
    setOffset({ x: 0, y: 0 });
  }, []);

  const handleWheel = useCallback((event: ReactWheelEvent<HTMLDivElement>) => {
    event.preventDefault();
    const delta = event.deltaY < 0 ? ZOOM_STEP : -ZOOM_STEP;
    setZoom((current) => clampZoom(current + delta));
  }, []);

  const handlePointerDown = useCallback((event: ReactPointerEvent<HTMLDivElement>) => {
    if (event.button !== 0) {
      return;
    }
    dragStartRef.current = {
      pointerX: event.clientX,
      pointerY: event.clientY,
      startX: offset.x,
      startY: offset.y,
    };
    event.currentTarget.setPointerCapture(event.pointerId);
  }, [offset.x, offset.y]);

  const handlePointerMove = useCallback((event: ReactPointerEvent<HTMLDivElement>) => {
    if (!dragStartRef.current) {
      return;
    }
    const nextX = dragStartRef.current.startX + (event.clientX - dragStartRef.current.pointerX);
    const nextY = dragStartRef.current.startY + (event.clientY - dragStartRef.current.pointerY);
    setOffset({
      x: Number(nextX.toFixed(1)),
      y: Number(nextY.toFixed(1)),
    });
  }, []);

  const handlePointerEnd = useCallback((event: ReactPointerEvent<HTMLDivElement>) => {
    if (dragStartRef.current) {
      dragStartRef.current = null;
    }
    event.currentTarget.releasePointerCapture(event.pointerId);
  }, []);

  useImperativeHandle(ref, () => ({
    async exportImage(filename: string) {
      const container = canvasRef.current;
      if (!container) return;

      const svgEl = container.querySelector("svg");
      if (!svgEl) return;

      const dataUrl = await toPng(container, {
        backgroundColor: "#ffffff",
        width: svgEl.clientWidth + 32,
        height: svgEl.clientHeight + 32,
        style: {
          transform: "none",
          width: `${svgEl.clientWidth + 32}px`,
          height: `${svgEl.clientHeight + 32}px`,
        },
      });

      const response = await fetch(dataUrl);
      const blob = await response.blob();
      saveAs(blob, filename);
    },
  }));

  if (svgMarkup.length > 0) {
    return (
      <div data-testid="diagram-mermaid" style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        <div className="row" style={{ justifyContent: "flex-end", gap: 6 }}>
          <button type="button" className="btn btn-ghost btn-sm" aria-label="Zoom out" onClick={zoomOut}>
            -
          </button>
          <button type="button" className="btn btn-ghost btn-sm" aria-label="Zoom in" onClick={zoomIn}>
            +
          </button>
          <button type="button" className="btn btn-ghost btn-sm" aria-label="Reset view" onClick={resetView}>
            100%
          </button>
        </div>
        <div
          style={{
            borderRadius: 8,
            background:
              "linear-gradient(180deg, rgba(247,250,246,0.6) 0%, rgba(255,255,255,0.4) 100%)",
            minHeight: 240,
            overflow: "hidden",
            position: "relative",
            cursor: dragStartRef.current ? "grabbing" : "grab",
            touchAction: "none",
          }}
          onWheel={handleWheel}
          onPointerDown={handlePointerDown}
          onPointerMove={handlePointerMove}
          onPointerUp={handlePointerEnd}
          onPointerCancel={handlePointerEnd}
        >
          <div
            ref={canvasRef}
            data-testid="diagram-mermaid-canvas"
            style={{
              transform: `translate(${offset.x}px, ${offset.y}px) scale(${zoom})`,
              transformOrigin: "0 0",
              width: "max-content",
              maxWidth: "none",
              padding: 16,
            }}
            dangerouslySetInnerHTML={{ __html: svgMarkup }}
          />
        </div>
        <div className="muted" style={{ fontSize: 11 }}>
          {`Zoom ${Math.round(zoom * 100)}%`}
        </div>
      </div>
    );
  }

  if (pending) {
    return <span className="muted">Loading...</span>;
  }

  return (
    <pre
      style={{
        margin: 0,
        whiteSpace: "pre-wrap",
        wordBreak: "break-word",
        fontFamily: "\"Cascadia Code\", monospace",
        fontSize: 12,
        lineHeight: 1.5,
      }}
    >
      {syntax}
    </pre>
  );
});
