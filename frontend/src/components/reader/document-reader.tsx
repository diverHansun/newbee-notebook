"use client";

import { useQuery } from "@tanstack/react-query";
import { useRef } from "react";

import { MarkdownViewer } from "@/components/reader/markdown-viewer";
import { SelectionMenu } from "@/components/reader/selection-menu";
import { getDocument, getDocumentContent } from "@/lib/api/documents";
import { ApiError } from "@/lib/api/client";
import { useLang } from "@/lib/hooks/useLang";
import { uiStrings } from "@/lib/i18n/strings";
import { useTextSelection } from "@/lib/hooks/useTextSelection";
import { useReaderStore } from "@/stores/reader-store";

type DocumentReaderProps = {
  documentId: string;
  onBack: () => void;
  onExplain: (payload: { documentId: string; selectedText: string }) => void;
  onConclude: (payload: { documentId: string; selectedText: string }) => void;
};

export function DocumentReader({
  documentId,
  onBack,
  onExplain,
  onConclude,
}: DocumentReaderProps) {
  const { t, ti } = useLang();
  const viewerRef = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const isSelecting = useReaderStore((state) => state.isSelecting);

  const documentQuery = useQuery({
    queryKey: ["document", documentId],
    queryFn: () => getDocument(documentId),
    refetchInterval: (query) => {
      const doc = query.state.data;
      if (!doc) return false;
      if (doc.status === "uploaded" || doc.status === "pending" || doc.status === "processing") {
        return 3000;
      }
      if ((doc.status === "converted" || doc.status === "completed") && !doc.content_path) {
        return 3000;
      }
      return false;
    },
  });

  const status = documentQuery.data?.status;
  const canReadByStatus = status === "completed" || status === "converted";

  const contentQuery = useQuery({
    queryKey: ["document-content", documentId],
    queryFn: () => getDocumentContent(documentId, "markdown"),
    enabled: Boolean(documentId) && canReadByStatus,
  });

  useTextSelection({
    containerRef: viewerRef,
    documentId,
  });

  const renderBody = () => {
    if (documentQuery.isLoading) {
      return (
        <div className="stack-sm" style={{ padding: 24 }}>
          <div className="skeleton" style={{ height: 24, width: "40%" }} />
          <div className="skeleton" style={{ height: 16, width: "80%" }} />
          <div className="skeleton" style={{ height: 16, width: "60%" }} />
          <div className="skeleton" style={{ height: 16, width: "70%" }} />
        </div>
      );
    }

    if (documentQuery.isError) {
      return (
        <div className="empty-state">
          <span>{t(uiStrings.reader.loadFailed)}</span>
          <button className="btn btn-sm" type="button" onClick={() => documentQuery.refetch()}>
            {t(uiStrings.reader.retry)}
          </button>
        </div>
      );
    }

    if (!canReadByStatus) {
      const hint = statusHint(status, t);
      return (
        <div className="empty-state">
          <span className={`badge ${statusBadgeClass(status || "unknown")}`}>
            {status || "unknown"}
          </span>
          <span>{hint}</span>
        </div>
      );
    }

    if (contentQuery.isLoading) {
      return (
        <div className="stack-sm" style={{ padding: 24 }}>
          <div className="skeleton" style={{ height: 20, width: "50%" }} />
          <div className="skeleton" style={{ height: 14, width: "90%" }} />
          <div className="skeleton" style={{ height: 14, width: "75%" }} />
          <div className="skeleton" style={{ height: 14, width: "85%" }} />
          <div className="skeleton" style={{ height: 14, width: "65%" }} />
        </div>
      );
    }

    if (contentQuery.isError) {
      const err = contentQuery.error as ApiError;
      const friendlyMsg = contentErrorMessage(err, status, t, ti);
      return (
        <div className="empty-state">
          <span>{friendlyMsg}</span>
          <button className="btn btn-sm" type="button" onClick={() => contentQuery.refetch()}>
            {t(uiStrings.reader.retry)}
          </button>
        </div>
      );
    }

    return (
      <div style={{ padding: "8px 24px 24px" }}>
        <MarkdownViewer
          content={contentQuery.data?.content || ""}
          documentId={documentId}
          containerRef={viewerRef}
          scrollRootRef={scrollContainerRef}
          freezeLazyLoad={isSelecting}
        />
      </div>
    );
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      {/* Header */}
      <div
        className="row-between"
        style={{
          padding: "12px 16px",
          borderBottom: "1px solid hsl(var(--border))",
          flexShrink: 0,
        }}
      >
        <div className="row">
          <button className="btn btn-ghost btn-sm" type="button" onClick={onBack}>
            {t(uiStrings.reader.backToChat)}
          </button>
          <strong style={{ fontSize: 14, fontWeight: 600 }}>
            {documentQuery.data?.title || t(uiStrings.reader.documentFallbackTitle)}
          </strong>
        </div>
        {status && (
          <span className={`badge ${statusBadgeClass(status)}`}>
            {status}
          </span>
        )}
      </div>

      {/* Content */}
      <div ref={scrollContainerRef} style={{ flex: 1, overflow: "auto" }}>
        {renderBody()}
      </div>

      <SelectionMenu onExplain={onExplain} onConclude={onConclude} />
    </div>
  );
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

function statusHint(status: string | undefined, t: ReturnType<typeof useLang>["t"]): string {
  switch (status) {
    case "processing":
      return t(uiStrings.reader.processing);
    case "pending":
    case "uploaded":
      return t(uiStrings.reader.pending);
    case "failed":
      return t(uiStrings.reader.failed);
    default:
      return t(uiStrings.reader.notReady);
  }
}

function contentErrorMessage(
  err: ApiError,
  status: string | undefined,
  t: ReturnType<typeof useLang>["t"],
  ti: ReturnType<typeof useLang>["ti"]
): string {
  if (err.errorCode === "E4001" && status === "converted") {
    return t(uiStrings.reader.convertedBlocked);
  }
  if (
    err.errorCode === "E_HTTP_DETAIL" &&
    err.message?.toLowerCase().includes("content not available")
  ) {
    return t(uiStrings.reader.contentPathMissing);
  }
  if (err.errorCode === "E4001") {
    return t(uiStrings.reader.processing);
  }
  return ti(uiStrings.reader.contentLoadFailedWithCode, {
    errorCode: err.errorCode || "E_UNKNOWN",
    message: err.message || "Unknown error",
  });
}
