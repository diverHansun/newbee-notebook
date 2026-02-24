"use client";

import { NotebookDocumentItem } from "@/lib/api/types";
import { useLang } from "@/lib/hooks/useLang";
import { uiStrings } from "@/lib/i18n/strings";

type SourceCardProps = {
  document: NotebookDocumentItem;
  onView: (documentId: string) => void;
  onRemove: (document: NotebookDocumentItem) => void;
};

function canViewDocument(status: string) {
  return status === "completed" || status === "converted";
}

function statusBadgeClass(status: string): string {
  const map: Record<string, string> = {
    uploaded: "badge-default",
    pending: "badge-default",
    processing: "badge-processing",
    converted: "badge-converted",
    completed: "badge-completed",
    failed: "badge-failed",
  };
  return map[status] || "badge-default";
}

function statusLabel(
  status: string,
  stage: string | null | undefined,
  t: ReturnType<typeof useLang>["t"]
): string {
  const map: Record<string, string> = {
    uploaded: t(uiStrings.sourceCard.waiting),
    pending: t(uiStrings.sourceCard.waiting),
    processing: stage ? stageLabel(stage, t) : t(uiStrings.sourceCard.processing),
    converted: t(uiStrings.sourceCard.converted),
    completed: t(uiStrings.sourceCard.completed),
    failed: t(uiStrings.sourceCard.failed),
  };
  return map[status] || status;
}

function stageLabel(stage: string, t: ReturnType<typeof useLang>["t"]): string {
  const map: Record<string, string> = {
    converting: t(uiStrings.sourceCard.converting),
    splitting: t(uiStrings.sourceCard.splitting),
    indexing_pg: t(uiStrings.sourceCard.indexingPg),
    indexing_es: t(uiStrings.sourceCard.indexingEs),
    finalizing: t(uiStrings.sourceCard.finalizing),
  };
  return map[stage] || stage;
}

export function SourceCard({ document, onView, onRemove }: SourceCardProps) {
  const { t } = useLang();
  const canView = canViewDocument(document.status);

  return (
    <li
      className="list-item"
      style={{ display: "flex", alignItems: "flex-start", gap: 12, padding: 12 }}
    >
      {/* File icon placeholder */}
      <div
        style={{
          width: 36,
          height: 36,
          borderRadius: "calc(var(--radius) - 2px)",
          background: "hsl(var(--muted))",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontSize: 14,
          flexShrink: 0,
        }}
      >
        📄
      </div>

      {/* Content */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div
          style={{
            fontSize: 13,
            fontWeight: 500,
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
          }}
        >
          {document.title}
        </div>
        <div className="row" style={{ marginTop: 6, flexWrap: "wrap" }}>
          <span className={`badge ${statusBadgeClass(document.status)}`}>
            {statusLabel(document.status, document.processing_stage, t)}
          </span>
        </div>
      </div>

      {/* Actions */}
      <div className="row" style={{ flexShrink: 0, gap: 4 }}>
        <button
          className="btn btn-ghost btn-sm"
          type="button"
          disabled={!canView}
          onClick={() => onView(document.document_id)}
        >
          {t(uiStrings.common.view)}
        </button>
        <button
          className="btn btn-ghost btn-danger-ghost btn-sm"
          type="button"
          onClick={() => onRemove(document)}
        >
          {t(uiStrings.common.remove)}
        </button>
      </div>
    </li>
  );
}
