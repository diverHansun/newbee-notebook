"use client";

import { useMemo } from "react";

import { VideoInputArea } from "@/components/studio/video-input-area";
import { VideoListItem } from "@/components/studio/video-list-item";
import { SegmentedControl } from "@/components/ui/segmented-control";
import { useAllVideoSummaries, useVideoSummaries } from "@/lib/hooks/use-videos";
import { useLang } from "@/lib/hooks/useLang";
import { uiStrings } from "@/lib/i18n/strings";
import { useStudioStore } from "@/stores/studio-store";

type VideoListProps = {
  notebookId: string;
  onOpenSummary: (summaryId: string) => void;
  onBack: () => void;
};

export function VideoList({ notebookId, onOpenSummary, onBack }: VideoListProps) {
  const { t } = useLang();
  const {
    videoFilterMode,
    videoPlatformFilter,
    setVideoFilterMode,
    setVideoPlatformFilter,
  } = useStudioStore();
  const allVideosQuery = useAllVideoSummaries();
  const notebookVideosQuery = useVideoSummaries(notebookId);

  const activeQuery = videoFilterMode === "all" ? allVideosQuery : notebookVideosQuery;
  const summaries = useMemo(
    () =>
      (activeQuery.data?.summaries ?? []).filter((summary) =>
        videoPlatformFilter === "all" ? true : summary.platform === videoPlatformFilter
      ),
    [activeQuery.data?.summaries, videoPlatformFilter]
  );

  return (
    <div className="stack-md" style={{ height: "100%", padding: 0 }}>
      <div className="row-between" style={{ gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        <button className="btn btn-ghost btn-sm" type="button" onClick={onBack}>
          {t(uiStrings.studio.backToStudio)}
        </button>
        <SegmentedControl
          value={videoFilterMode}
          options={[
            { value: "all", label: t(uiStrings.studio.allFilter) },
            { value: "notebook", label: t(uiStrings.studio.thisNotebook) },
          ]}
          onChange={(value) => setVideoFilterMode(value as "all" | "notebook")}
        />
      </div>

      <div className="row" style={{ gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        <span className="muted" style={{ fontSize: 12 }}>
          {t(uiStrings.video.platformFilterLabel)}
        </span>
        <SegmentedControl
          value={videoPlatformFilter}
          options={[
            { value: "all", label: t(uiStrings.video.platformAll) },
            { value: "bilibili", label: t(uiStrings.video.platformBilibili) },
            { value: "youtube", label: t(uiStrings.video.platformYouTube) },
          ]}
          onChange={(value) => setVideoPlatformFilter(value as "all" | "bilibili" | "youtube")}
        />
      </div>

      <VideoInputArea notebookId={notebookId} />

      {activeQuery.isLoading ? (
        <div className="empty-state" style={{ padding: "24px 12px" }}>
          <span>{t(uiStrings.common.loading)}</span>
        </div>
      ) : activeQuery.isError ? (
        <div className="empty-state" style={{ padding: "24px 12px" }}>
          <span>{t(uiStrings.common.retry)}</span>
        </div>
      ) : summaries.length === 0 ? (
        <div className="empty-state" style={{ padding: "24px 12px" }}>
          <span>{t(uiStrings.video.emptyState)}</span>
        </div>
      ) : (
        <div className="stack-sm" style={{ flex: 1, minHeight: 0, overflow: "auto" }}>
          {summaries.map((summary) => (
            <VideoListItem
              key={summary.summary_id}
              summary={summary}
              isAssociated={summary.notebook_id === notebookId}
              onOpenSummary={onOpenSummary}
            />
          ))}
        </div>
      )}
    </div>
  );
}
