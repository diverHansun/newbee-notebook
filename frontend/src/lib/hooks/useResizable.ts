"use client";

import { useCallback, useRef, useState } from "react";

type Size = { width: number; height: number };

type UseResizableOptions = {
  initialSize: Size;
  minSize?: Size;
  maxSize?: Size;
};

type UseResizableReturn = {
  size: Size;
  onResizePointerDown: (e: React.PointerEvent) => void;
  isResizing: boolean;
};

export function useResizable(options: UseResizableOptions): UseResizableReturn {
  const { minSize = { width: 300, height: 150 }, maxSize = { width: 600, height: 500 } } =
    options;
  const [size, setSize] = useState<Size>(options.initialSize);
  const [isResizing, setIsResizing] = useState(false);
  const ref = useRef<{
    startX: number;
    startY: number;
    originW: number;
    originH: number;
  } | null>(null);

  const onResizePointerDown = useCallback(
    (e: React.PointerEvent) => {
      if (e.button !== 0) return;
      e.preventDefault();
      e.stopPropagation();
      e.currentTarget.setPointerCapture(e.pointerId);

      ref.current = {
        startX: e.clientX,
        startY: e.clientY,
        originW: size.width,
        originH: size.height,
      };
      setIsResizing(true);

      const onMove = (ev: PointerEvent) => {
        if (!ref.current) return;
        const dw = ev.clientX - ref.current.startX;
        const dh = ev.clientY - ref.current.startY;

        const nw = Math.max(minSize.width, Math.min(maxSize.width, ref.current.originW + dw));
        const nh = Math.max(minSize.height, Math.min(maxSize.height, ref.current.originH + dh));

        setSize({ width: nw, height: nh });
      };

      const onUp = () => {
        ref.current = null;
        setIsResizing(false);
        window.removeEventListener("pointermove", onMove);
        window.removeEventListener("pointerup", onUp);
      };

      window.addEventListener("pointermove", onMove);
      window.addEventListener("pointerup", onUp);
    },
    [size.width, size.height, minSize.width, minSize.height, maxSize.width, maxSize.height]
  );

  return { size, onResizePointerDown, isResizing };
}
