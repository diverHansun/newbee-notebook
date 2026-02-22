"use client";

import { useCallback, useEffect, useState } from "react";

type ConfirmDialogProps = {
  open: boolean;
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: "danger" | "warning";
  confirmDisabled?: boolean;
  onConfirm: () => void | Promise<void>;
  onCancel: () => void;
};

export function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel = "\u786e\u8ba4",
  cancelLabel = "\u53d6\u6d88",
  variant = "danger",
  confirmDisabled = false,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  const [submitting, setSubmitting] = useState(false);

  const handleConfirm = useCallback(async () => {
    if (submitting || confirmDisabled) return;
    const ret = onConfirm();
    if (ret && typeof (ret as Promise<void>).then === "function") {
      setSubmitting(true);
      try {
        await ret;
      } finally {
        setSubmitting(false);
      }
    }
  }, [confirmDisabled, onConfirm, submitting]);

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        if (!submitting) onCancel();
        return;
      }
      if (event.key === "Enter" && !submitting && !confirmDisabled) {
        event.preventDefault();
        void handleConfirm();
      }
    };

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [confirmDisabled, handleConfirm, onCancel, open, submitting]);

  if (!open) return null;

  const confirmStyle =
    variant === "warning"
      ? {
          background: "hsl(var(--bee-yellow-light))",
          color: "#92400E",
          borderColor: "hsl(var(--bee-yellow) / 0.5)",
        }
      : {
          background: "hsl(var(--destructive))",
          color: "hsl(var(--destructive-foreground))",
          borderColor: "hsl(var(--destructive))",
        };

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 1200,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "rgba(15, 23, 42, 0.45)",
        backdropFilter: "blur(4px)",
        padding: 16,
      }}
      onClick={() => {
        if (!submitting) onCancel();
      }}
      role="presentation"
    >
      <div
        className="card"
        style={{ width: "min(480px, 100%)", padding: 20 }}
        onClick={(event) => event.stopPropagation()}
      >
        <div className="stack-md">
          <div className="row-between">
            <strong style={{ fontSize: 16 }}>{title}</strong>
            <button
              className="btn btn-ghost btn-icon"
              type="button"
              disabled={submitting}
              onClick={onCancel}
              aria-label="\u5173\u95ed\u786e\u8ba4\u6846"
            >
              x
            </button>
          </div>
          <p className="muted" style={{ margin: 0, whiteSpace: "pre-wrap", lineHeight: 1.6 }}>
            {message}
          </p>
          <div className="row" style={{ justifyContent: "flex-end" }}>
            <button className="btn" type="button" disabled={submitting} onClick={onCancel}>
              {cancelLabel}
            </button>
            <button
              className="btn"
              type="button"
              disabled={submitting || confirmDisabled}
              style={confirmStyle}
              onClick={() => {
                void handleConfirm();
              }}
            >
              {submitting ? "\u5904\u7406\u4e2d..." : confirmLabel}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
