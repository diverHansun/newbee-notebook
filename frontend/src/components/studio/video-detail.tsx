"use client";

import { saveAs } from "file-saver";
import { useState } from "react";

import { MarkdownViewer } from "@/components/reader/markdown-viewer";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { exportVideoSummaryMarkdown } from "@/lib/api/videos";
import {
  useAssociateVideoSummary,
  useDeleteVideoSummary,
  useDisassociateVideoSummary,
  useVideoSummary,
} from "@/lib/hooks/use-videos";
import { useLang } from "@/lib/hooks/useLang";
import { uiStrings } from "@/lib/i18n/strings";

type VideoDetailProps = {
  notebookId: string;
  summaryId: string;
  onBack: () => void;
};

function formatDuration(durationSeconds: number): string {
  const totalSeconds = Math.max(0, durationSeconds || 0);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${String(seconds).padStart(2, "0")}`;
}

function formatPlatform(platform: string): string {
  return platform === "youtube" ? "YouTube" : "Bilibili";
}

function sanitizeFilename(name: string): string {
  return name.replace(/[<>:"/\\|?*]/g, "_").trim() || "untitled";
}

export function VideoDetail({ notebookId, summaryId, onBack }: VideoDetailProps) {
  const { t } = useLang();
  const summaryQuery = useVideoSummary(summaryId);
  const associateMutation = useAssociateVideoSummary(notebookId);
  const disassociateMutation = useDisassociateVideoSummary(notebookId);
  const deleteMutation = useDeleteVideoSummary(notebookId);
  const [confirmDeleteOpen, setConfirmDeleteOpen] = useState(false);
  const [exportingMarkdown, setExportingMarkdown] = useState(false);

  if (summaryQuery.isLoading) {
    return (
      <div className="empty-state" style={{ padding: 24 }}>
        <span>{t(uiStrings.common.loading)}</span>
      </div>
    );
  }

  const summary = summaryQuery.data;
  if (!summary) {
    return (
      <div className="empty-state" style={{ padding: 24 }}>
        <span>{t(uiStrings.video.emptyDetail)}</span>
      </div>
    );
  }

  const isAssociated = summary.notebook_id === notebookId;
  const shouldShowMetadataChips = !(summary.platform === "youtube" && summary.metadata_ready === false);

  const handleExportMarkdown = async () => {
    setExportingMarkdown(true);
    try {
      const { blob, filename } = await exportVideoSummaryMarkdown(summary.summary_id);
      const fallbackFilename = `${sanitizeFilename(summary.title)}.md`;
      saveAs(blob, filename || fallbackFilename);
    } finally {
      setExportingMarkdown(false);
    }
  };

  return (
    <>
      <div className="stack-md" style={{ height: "100%", padding: 0 }}>
        <div className="row-between" style={{ gap: 8 }}>
          <button className="btn btn-ghost btn-sm" type="button" onClick={onBack}>
            {t(uiStrings.studio.backToList)}
          </button>
          <div className="row" style={{ gap: 8 }}>
            <button
              className="btn btn-ghost btn-sm"
              type="button"
              onClick={() =>
                void (isAssociated
                  ? disassociateMutation.mutateAsync(summary.summary_id)
                  : associateMutation.mutateAsync(summary.summary_id))
              }
            >
              {isAssociated ? t(uiStrings.video.disassociate) : t(uiStrings.video.associate)}
            </button>
            <button
              className="btn btn-danger-ghost btn-sm"
              type="button"
              onClick={() => setConfirmDeleteOpen(true)}
            >
              {t(uiStrings.common.delete)}
            </button>
          </div>
        </div>

        <div className="card video-detail-card">
          <div className="stack-sm">
            <strong>{summary.title}</strong>
            <div className="row-between" style={{ gap: 8, alignItems: "flex-start" }}>
              <div className="video-summary-meta" style={{ flex: 1 }}>
                <span className="chip">{formatPlatform(summary.platform)}</span>
                {shouldShowMetadataChips ? (
                  <span className="chip">{summary.uploader_name || t(uiStrings.video.unknownUploader)}</span>
                ) : null}
                {shouldShowMetadataChips ? <span className="chip">{formatDuration(summary.duration_seconds)}</span> : null}
                <span className="chip">{summary.video_id}</span>
              </div>
              <button
                className="btn btn-ghost btn-sm"
                type="button"
                disabled={exportingMarkdown}
                aria-label={t(uiStrings.video.exportMarkdown)}
                title={t(uiStrings.video.exportMarkdown)}
                style={{ padding: "4px 6px" }}
                onClick={() => {
                  void handleExportMarkdown();
                }}
              >
                <svg
                  width="16"
                  height="16"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                  <polyline points="7 10 12 15 17 10" />
                  <line x1="12" y1="15" x2="12" y2="3" />
                </svg>
              </button>
            </div>
          </div>
        </div>

        <div className="card video-detail-markdown">
          <MarkdownViewer content={summary.summary_content} />
        </div>
      </div>

      <ConfirmDialog
        open={confirmDeleteOpen}
        title={t(uiStrings.video.deleteTitle)}
        message={t(uiStrings.video.deleteConfirm)}
        variant="danger"
        confirmDisabled={deleteMutation.isPending}
        onCancel={() => setConfirmDeleteOpen(false)}
        onConfirm={async () => {
          await deleteMutation.mutateAsync(summary.summary_id);
          setConfirmDeleteOpen(false);
          onBack();
        }}
      />
    </>
  );
}
