"use client";

import { useMemo } from "react";

import { useLang } from "@/lib/hooks/useLang";
import type { PermissionResponseChoice } from "@/lib/api/types";
import { toolDisplayName } from "@/lib/chat/tool-presentation";
import type { LocalizedString } from "@/lib/i18n/strings";
import { uiStrings } from "@/lib/i18n/strings";
import type { PendingPermissionRequest } from "@/stores/chat-store";

type TranslateFn = ReturnType<typeof useLang>["t"];

type PermissionRequestCardProps = {
  request: PendingPermissionRequest;
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
      return t(uiStrings.permissionRequest.allowed);
    case "rejected":
      return t(uiStrings.permissionRequest.rejected);
    case "timeout":
      return t(uiStrings.permissionRequest.timeout);
    case "resolving":
      return t(uiStrings.common.processing);
    case "error":
      return t(uiStrings.permissionRequest.submitFailed);
    default:
      return "";
  }
}

function permissionRequestTitle(actionType: string, targetType: string, t: TranslateFn): string {
  const actionGroup = (uiStrings.permissionRequest.actionTitle as Record<
    string,
    Record<string, LocalizedString>
  >)[actionType];
  const key = actionGroup?.[targetType];
  if (key) return t(key);
  return t(uiStrings.permissionRequest.title);
}

const DEFAULT_RESPONSE_OPTIONS: PermissionResponseChoice[] = [
  "once",
  "always_session",
  "always_persist",
  "reject",
];

function responseLabel(option: PermissionResponseChoice): LocalizedString {
  if (option === "once") return uiStrings.permissionRequest.allowOnce;
  if (option === "always_session") return uiStrings.permissionRequest.allowSession;
  if (option === "always_persist") return uiStrings.permissionRequest.allowNotebook;
  return uiStrings.permissionRequest.reject;
}

function localizedDescription(
  toolName: string,
  fallback: string,
  t: TranslateFn
): string {
  const map = uiStrings.permissionRequest.toolRequest as Record<string, LocalizedString | undefined>;
  const entry = map[toolName];
  return entry ? t(entry) : fallback;
}

function summaryValueClassName(key: string): string {
  const normalized = key.toLowerCase();
  return normalized === "command" || normalized.endsWith("_command")
    ? "permission-request-card-summary-value permission-request-card-summary-value--code"
    : "permission-request-card-summary-value";
}

export function PermissionRequestCard({
  request,
  onResolve,
}: PermissionRequestCardProps) {
  const { t } = useLang();
  const summaryEntries = useMemo(
    () => Object.entries(request.argsSummary ?? {}),
    [request.argsSummary]
  );
  const isPending = request.status === "pending";
  const isResolving = ["confirmed", "rejected", "timeout", "resolving"].includes(request.status);
  const statusBadge = !isPending ? statusLabel(request.status, t) : null;
  const isDestructive = request.actionType === "delete";
  const options =
    request.responseOptions && request.responseOptions.length > 0
      ? request.responseOptions
      : DEFAULT_RESPONSE_OPTIONS;

  return (
    <div
      className={`permission-request-card ${
        isResolving ? "permission-request-card--resolving" : "permission-request-card--pending"
      }`}
      data-action-type={request.actionType}
      data-permission-status={request.status}
    >
      {statusBadge ? (
        <div className="permission-request-card-header">
          <span className="badge badge-default">{statusBadge}</span>
        </div>
      ) : null}

      <p className="permission-request-card-description">
        {localizedDescription(request.toolName, request.description, t)}
      </p>

      <dl className="permission-request-card-summary">
        <div className="permission-request-card-summary-row">
          <dt>{t(uiStrings.permissionRequest.tool)}</dt>
          <dd>{toolDisplayName(request.toolName)}</dd>
        </div>
      </dl>

      {summaryEntries.length > 0 ? (
        <dl className="permission-request-card-summary">
          {summaryEntries.map(([key, value]) => (
            <div key={key} className="permission-request-card-summary-row">
              <dt>{key}</dt>
              <dd className={summaryValueClassName(key)}>{formatSummaryValue(value)}</dd>
            </div>
          ))}
        </dl>
      ) : null}

      {isPending ? (
        <ul
          className="permission-request-card-actions"
          aria-label={t(uiStrings.permissionRequest.permissionChoices)}
          data-layout="vertical"
        >
          {options.map((option) => (
            <li key={option}>
              <button
                className={`permission-request-card-action ${
                  option === "reject"
                    ? "permission-request-card-action--reject"
                    : isDestructive && option === "once"
                      ? "permission-request-card-action--danger"
                      : option === "once"
                        ? "permission-request-card-action--primary"
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

export function PermissionStatusTag({
  request,
}: {
  request: PendingPermissionRequest;
}) {
  const { t } = useLang();
  const title = permissionRequestTitle(request.actionType, request.targetType, t);
  const resolvedStatus = request.resolvedFrom ?? "confirmed";
  if (resolvedStatus === "confirmed") return null;
  const icon = resolvedStatus === "rejected" || resolvedStatus === "timeout" ? "\u2715" : "\u2713";
  const verb = statusLabel(resolvedStatus, t) || t(uiStrings.permissionRequest.allowed);

  return (
    <span className="permission-status-tag" data-status={resolvedStatus}>
      {icon} {verb} — {title}
    </span>
  );
}
