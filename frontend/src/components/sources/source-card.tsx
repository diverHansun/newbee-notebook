"use client";

import { NotebookDocumentItem } from "@/lib/api/types";

type SourceCardProps = {
  document: NotebookDocumentItem;
  onView: (documentId: string) => void;
  onRemove: (documentId: string) => void;
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

function statusLabel(status: string, stage?: string | null): string {
  const map: Record<string, string> = {
    uploaded: "等待处理",
    pending: "等待处理",
    processing: stage ? stageLabel(stage) : "处理中...",
    converted: "已转换，待索引",
    completed: "已完成",
    failed: "处理失败",
  };
  return map[status] || status;
}

function stageLabel(stage: string): string {
  const map: Record<string, string> = {
    converting: "转换文档中...",
    splitting: "文本分块中...",
    indexing_pg: "构建向量索引...",
    indexing_es: "构建全文索引...",
    finalizing: "完成处理中...",
  };
  return map[stage] || stage;
}

export function SourceCard({ document, onView, onRemove }: SourceCardProps) {
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
            {statusLabel(document.status, document.processing_stage)}
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
          View
        </button>
        <button
          className="btn btn-ghost btn-sm"
          type="button"
          style={{ color: "hsl(var(--muted-foreground))" }}
          onClick={() => onRemove(document.document_id)}
        >
          移除
        </button>
      </div>
    </li>
  );
}
