"use client";

import { useCallback, useRef, useState } from "react";

type Position = { x: number; y: number };

type UseDraggableOptions = {
  initialPosition?: Position;
};

type UseDraggableReturn = {
  position: Position;
  onPointerDown: (e: React.PointerEvent) => void;
  isDragging: boolean;
  resetPosition: (pos: Position) => void;
};

export function useDraggable(
  options: UseDraggableOptions = {}
): UseDraggableReturn {
  const [position, setPosition] = useState<Position>(
    options.initialPosition ?? { x: 0, y: 0 }
  );
  const [isDragging, setIsDragging] = useState(false);
  const dragRef = useRef<{
    startX: number;
    startY: number;
    originX: number;
    originY: number;
  } | null>(null);

  const onPointerDown = useCallback(
    (e: React.PointerEvent) => {
      if (e.button !== 0) return;
      e.preventDefault();
      e.currentTarget.setPointerCapture(e.pointerId);

      dragRef.current = {
        startX: e.clientX,
        startY: e.clientY,
        originX: position.x,
        originY: position.y,
      };
      setIsDragging(true);

      const onMove = (ev: PointerEvent) => {
        if (!dragRef.current) return;
        const dx = ev.clientX - dragRef.current.startX;
        const dy = ev.clientY - dragRef.current.startY;

        let nx = dragRef.current.originX + dx;
        let ny = dragRef.current.originY + dy;

        const vw = window.innerWidth;
        const vh = window.innerHeight;
        nx = Math.max(-vw + 80, Math.min(nx, vw - 80));
        ny = Math.max(-vh + 40, Math.min(ny, vh - 40));

        setPosition({ x: nx, y: ny });
      };

      const onUp = () => {
        dragRef.current = null;
        setIsDragging(false);
        window.removeEventListener("pointermove", onMove);
        window.removeEventListener("pointerup", onUp);
      };

      window.addEventListener("pointermove", onMove);
      window.addEventListener("pointerup", onUp);
    },
    [position.x, position.y]
  );

  const resetPosition = useCallback((pos: Position) => {
    setPosition(pos);
  }, []);

  return { position, onPointerDown, isDragging, resetPosition };
}
