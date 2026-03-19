"use client";

import { useEffect, useMemo, useState } from "react";

import { useLang } from "@/lib/hooks/useLang";
import { uiStrings } from "@/lib/i18n/strings";
import type { PendingConfirmation } from "@/stores/chat-store";

type ConfirmationCardProps = {
  confirmation: PendingConfirmation;
  onConfirm: () => void;
  onReject: () => void;
};

function formatSummaryValue(value: unknown): string {
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  if (Array.isArray(value)) return value.map((item) => formatSummaryValue(item)).join(", ");
  if (value && typeof value === "object") return JSON.stringify(value);
  return "-";
}

function statusLabel(
  status: PendingConfirmation["status"],
  t: ReturnType<typeof useLang>["t"]
): string {
  switch (status) {
    case "confirmed":
      return t(uiStrings.confirmation.confirmed);
    case "rejected":
      return t(uiStrings.confirmation.rejected);
    case "timeout":
      return t(uiStrings.confirmation.timeout);
    default:
      return "";
  }
}

function formatCountdown(remainingMs: number): string {
  const totalSeconds = Math.max(0, Math.ceil(remainingMs / 1000));
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}

export function ConfirmationCard({
  confirmation,
  onConfirm,
  onReject,
}: ConfirmationCardProps) {
  const { t } = useLang();
  const [now, setNow] = useState(() => Date.now());
  const summaryEntries = useMemo(
    () => Object.entries(confirmation.argsSummary ?? {}),
    [confirmation.argsSummary]
  );
  const resolvedStatus = statusLabel(confirmation.status, t);
  const isPending = confirmation.status === "pending";
  const remainingLabel = formatCountdown(confirmation.expiresAt - now);

  useEffect(() => {
    if (!isPending) return;

    setNow(Date.now());
    const intervalId = window.setInterval(() => {
      setNow(Date.now());
    }, 1000);

    return () => window.clearInterval(intervalId);
  }, [isPending]);

  return (
    <div className="confirmation-card" data-confirmation-status={confirmation.status}>
      <div className="confirmation-card-header">
        <strong>{t(uiStrings.confirmation.title)}</strong>
        {resolvedStatus ? <span className="badge badge-default">{resolvedStatus}</span> : null}
      </div>
      <p className="confirmation-card-description">{confirmation.description}</p>
      <dl className="confirmation-card-summary">
        {isPending ? (
          <div className="confirmation-card-summary-row">
            <dt>{t(uiStrings.confirmation.timeLeft)}</dt>
            <dd>{remainingLabel}</dd>
          </div>
        ) : null}
        <div className="confirmation-card-summary-row">
          <dt>{t(uiStrings.confirmation.requestId)}</dt>
          <dd>{confirmation.requestId}</dd>
        </div>
        <div className="confirmation-card-summary-row">
          <dt>{t(uiStrings.confirmation.tool)}</dt>
          <dd>{confirmation.toolName}</dd>
        </div>
        {summaryEntries.map(([key, value]) => (
          <div key={key} className="confirmation-card-summary-row">
            <dt>{key}</dt>
            <dd>{formatSummaryValue(value)}</dd>
          </div>
        ))}
      </dl>
      {isPending ? (
        <div className="confirmation-card-actions">
          <button className="btn btn-sm" type="button" onClick={onConfirm}>
            {t(uiStrings.confirmation.confirm)}
          </button>
          <button className="btn btn-ghost btn-sm" type="button" onClick={onReject}>
            {t(uiStrings.confirmation.reject)}
          </button>
        </div>
      ) : null}
    </div>
  );
}
