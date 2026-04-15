"use client";

import { VideoSummaryListItem } from "@/lib/api/types";
import { useLang } from "@/lib/hooks/useLang";
import { uiStrings } from "@/lib/i18n/strings";

type VideoListItemProps = {
  summary: VideoSummaryListItem;
  isAssociated: boolean;
  onOpenSummary: (summaryId: string) => void;
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

function formatStatus(
  status: string,
  t: (value: { zh: string; en: string }) => string
): string {
  if (status === "completed") return t(uiStrings.video.statusCompleted);
  if (status === "processing") return t(uiStrings.video.statusProcessing);
  if (status === "failed") return t(uiStrings.video.statusFailed);
  return status;
}

function formatTimestamp(value: string, locale: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(locale, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

export function VideoListItem({
  summary,
  isAssociated,
  onOpenSummary,
}: VideoListItemProps) {
  const { lang, t, ti } = useLang();
  const locale = lang === "en" ? "en-US" : "zh-CN";
  const uploaderName = summary.uploader_name || t(uiStrings.video.unknownUploader);
  const shouldShowMetadataChips = !(summary.platform === "youtube" && summary.metadata_ready === false);

  return (
    <button
      type="button"
      className="video-summary-item"
      aria-label={summary.title}
      onClick={() => onOpenSummary(summary.summary_id)}
    >
      <div className="stack-sm" style={{ width: "100%" }}>
        <div className="row-between" style={{ gap: 8, alignItems: "flex-start" }}>
          <strong className="video-summary-title">{summary.title}</strong>
          {isAssociated ? <span className="chip">{t(uiStrings.video.associatedTag)}</span> : null}
        </div>
        <div className="video-summary-meta">
          <span className="chip">{formatPlatform(summary.platform)}</span>
          {shouldShowMetadataChips ? <span className="chip">{uploaderName}</span> : null}
          {shouldShowMetadataChips ? <span className="chip">{formatDuration(summary.duration_seconds)}</span> : null}
          <span className="chip video-status-chip" data-status={summary.status}>
            {formatStatus(summary.status, t)}
          </span>
        </div>
        <div className="row-between" style={{ gap: 8, flexWrap: "wrap" }}>
          <span className="video-summary-subline">
            {ti(uiStrings.video.videoId, { id: summary.video_id })}
          </span>
          <span className="video-summary-subline">
            {ti(uiStrings.video.updatedAt, {
              date: formatTimestamp(summary.updated_at, locale),
            })}
          </span>
        </div>
      </div>
    </button>
  );
}
