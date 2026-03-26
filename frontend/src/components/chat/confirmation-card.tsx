"use client";

import { useMemo } from "react";

import { useLang } from "@/lib/hooks/useLang";
import type { LocalizedString } from "@/lib/i18n/strings";
import { uiStrings } from "@/lib/i18n/strings";
import type {
  ConfirmationActionType,
  ConfirmationTargetType,
  PendingConfirmation,
} from "@/stores/chat-store";

type TranslateFn = ReturnType<typeof useLang>["t"];

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
  status: string,
  t: TranslateFn
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

function confirmationTitle(
  actionType: ConfirmationActionType,
  targetType: ConfirmationTargetType,
  t: TranslateFn
): string {
  const actionGroup = uiStrings.confirmation.actionTitle[actionType] as
    | Record<string, LocalizedString>
    | undefined;
  const key = actionGroup?.[targetType];
  if (key) return t(key);
  return t(uiStrings.confirmation.title);
}

export function ConfirmationCard({
  confirmation,
  onConfirm,
  onReject,
}: ConfirmationCardProps) {
  const { t } = useLang();
  const summaryEntries = useMemo(
    () => Object.entries(confirmation.argsSummary ?? {}),
    [confirmation.argsSummary]
  );
  const isPending = confirmation.status === "pending";
  const isResolving = ["confirmed", "rejected", "timeout"].includes(confirmation.status);
  const title = confirmationTitle(confirmation.actionType, confirmation.targetType, t);
  const statusBadge = !isPending ? statusLabel(confirmation.status, t) : null;
  const isDestructive = confirmation.actionType === "delete";

  return (
    <div
      className={`confirmation-card ${
        isResolving ? "confirmation-card--resolving" : "confirmation-card--pending"
      }`}
      data-action-type={confirmation.actionType}
      data-confirmation-status={confirmation.status}
    >
      <div className="confirmation-card-header">
        <strong>{title}</strong>
        {statusBadge ? <span className="badge badge-default">{statusBadge}</span> : null}
      </div>

      {summaryEntries.length > 0 ? (
        <dl className="confirmation-card-summary">
          {summaryEntries.map(([key, value]) => (
            <div key={key} className="confirmation-card-summary-row">
              <dt>{key}</dt>
              <dd>{formatSummaryValue(value)}</dd>
            </div>
          ))}
        </dl>
      ) : null}

      {isPending ? (
        <div className="confirmation-card-actions">
          <button
            className={`btn btn-sm ${isDestructive ? "btn-destructive" : ""}`}
            type="button"
            onClick={onConfirm}
          >
            {isDestructive
              ? t(uiStrings.confirmation.confirmDelete)
              : t(uiStrings.confirmation.confirm)}
          </button>
          <button className="btn btn-ghost btn-sm" type="button" onClick={onReject}>
            {t(uiStrings.confirmation.reject)}
          </button>
        </div>
      ) : null}
    </div>
  );
}

export function ConfirmationInlineTag({
  confirmation,
}: {
  confirmation: PendingConfirmation;
}) {
  const { t } = useLang();
  const title = confirmationTitle(confirmation.actionType, confirmation.targetType, t);
  const resolvedStatus = confirmation.resolvedFrom ?? "confirmed";
  const icon = resolvedStatus === "rejected" || resolvedStatus === "timeout" ? "\u2715" : "\u2713";
  const verb = statusLabel(resolvedStatus, t) || t(uiStrings.confirmation.confirmed);

  return (
    <span className="confirmation-inline-tag" data-status={resolvedStatus}>
      {icon} {verb} — {title}
    </span>
  );
}
