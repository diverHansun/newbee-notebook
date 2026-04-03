"use client";

import { VideoSummaryListItem } from "@/lib/api/types";

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

export function VideoListItem({
  summary,
  isAssociated,
  onOpenSummary,
}: VideoListItemProps) {
  return (
    <button
      type="button"
      className="list-item"
      style={{ width: "100%", textAlign: "left", padding: 12 }}
      aria-label={summary.title}
      onClick={() => onOpenSummary(summary.summary_id)}
    >
      <div className="stack-sm" style={{ width: "100%" }}>
        <div className="row-between" style={{ gap: 8, alignItems: "flex-start" }}>
          <strong>{summary.title}</strong>
          {isAssociated ? <span className="chip">Notebook</span> : null}
        </div>
        <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
          <span className="chip">{formatPlatform(summary.platform)}</span>
          <span className="chip">{summary.uploader_name}</span>
          <span className="chip">{formatDuration(summary.duration_seconds)}</span>
          <span className="chip">{summary.status}</span>
        </div>
      </div>
    </button>
  );
}
