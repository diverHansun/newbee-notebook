"use client";

import { useMemo } from "react";

import { useLang } from "@/lib/hooks/useLang";
import type { PermissionResponseChoice } from "@/lib/api/types";
import type { LocalizedString } from "@/lib/i18n/strings";
import { uiStrings } from "@/lib/i18n/strings";
import type { PendingConfirmation } from "@/stores/chat-store";

type TranslateFn = ReturnType<typeof useLang>["t"];

type ConfirmationCardProps = {
  confirmation: PendingConfirmation;
  onResolve: (response: PermissionResponseChoice) => void;
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
    case "resolving":
      return t(uiStrings.common.processing);
    case "error":
      return t(uiStrings.confirmation.submitFailed);
    default:
      return "";
  }
}

function confirmationTitle(actionType: string, targetType: string, t: TranslateFn): string {
  const actionGroup = (uiStrings.confirmation.actionTitle as Record<
    string,
    Record<string, LocalizedString>
  >)[actionType];
  const key = actionGroup?.[targetType];
  if (key) return t(key);
  return t(uiStrings.confirmation.title);
}

const DEFAULT_RESPONSE_OPTIONS: PermissionResponseChoice[] = [
  "once",
  "always_session",
  "always_persist",
  "reject",
];

function responseLabel(option: PermissionResponseChoice): LocalizedString {
  if (option === "once") return uiStrings.confirmation.allowOnce;
  if (option === "always_session") return uiStrings.confirmation.allowSession;
  if (option === "always_persist") return uiStrings.confirmation.allowNotebook;
  return uiStrings.confirmation.reject;
}

function localizedDescription(
  toolName: string,
  fallback: string,
  t: TranslateFn
): string {
  const map = uiStrings.confirmation.toolRequest as Record<string, LocalizedString | undefined>;
  const entry = map[toolName];
  return entry ? t(entry) : fallback;
}

function summaryValueClassName(key: string): string {
  const normalized = key.toLowerCase();
  return normalized === "command" || normalized.endsWith("_command")
    ? "confirmation-card-summary-value confirmation-card-summary-value--code"
    : "confirmation-card-summary-value";
}

export function ConfirmationCard({
  confirmation,
  onResolve,
}: ConfirmationCardProps) {
  const { t } = useLang();
  const summaryEntries = useMemo(
    () => Object.entries(confirmation.argsSummary ?? {}),
    [confirmation.argsSummary]
  );
  const isPending = confirmation.status === "pending";
  const isResolving = ["confirmed", "rejected", "timeout", "resolving"].includes(confirmation.status);
  const statusBadge = !isPending ? statusLabel(confirmation.status, t) : null;
  const isDestructive = confirmation.actionType === "delete";
  const options =
    confirmation.responseOptions && confirmation.responseOptions.length > 0
      ? confirmation.responseOptions
      : DEFAULT_RESPONSE_OPTIONS;

  return (
    <div
      className={`confirmation-card ${
        isResolving ? "confirmation-card--resolving" : "confirmation-card--pending"
      }`}
      data-action-type={confirmation.actionType}
      data-confirmation-status={confirmation.status}
    >
      {statusBadge ? (
        <div className="confirmation-card-header">
          <span className="badge badge-default">{statusBadge}</span>
        </div>
      ) : null}

      <p className="confirmation-card-description">
        {localizedDescription(confirmation.toolName, confirmation.description, t)}
      </p>

      <dl className="confirmation-card-summary">
        <div className="confirmation-card-summary-row">
          <dt>{t(uiStrings.confirmation.tool)}</dt>
          <dd>{confirmation.toolName}</dd>
        </div>
      </dl>

      {summaryEntries.length > 0 ? (
        <dl className="confirmation-card-summary">
          {summaryEntries.map(([key, value]) => (
            <div key={key} className="confirmation-card-summary-row">
              <dt>{key}</dt>
              <dd className={summaryValueClassName(key)}>{formatSummaryValue(value)}</dd>
            </div>
          ))}
        </dl>
      ) : null}

      {isPending ? (
        <ul
          className="confirmation-card-actions"
          aria-label={t(uiStrings.confirmation.permissionChoices)}
          data-layout="vertical"
        >
          {options.map((option) => (
            <li key={option}>
              <button
                className={`confirmation-card-action ${
                  option === "reject"
                    ? "confirmation-card-action--reject"
                    : isDestructive && option === "once"
                      ? "confirmation-card-action--danger"
                      : option === "once"
                        ? "confirmation-card-action--primary"
                        : ""
                }`}
                type="button"
                onClick={() => onResolve(option)}
              >
                {t(responseLabel(option))}
              </button>
            </li>
          ))}
        </ul>
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
