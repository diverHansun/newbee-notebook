import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { LanguageContext } from "@/lib/i18n/language-context";
import { createQueryClient } from "@/test/test-utils";

const mocks = vi.hoisted(() => ({
  useAssociateVideoSummary: vi.fn(),
  useDeleteVideoSummary: vi.fn(),
  useDisassociateVideoSummary: vi.fn(),
  useVideoSummary: vi.fn(),
}));

vi.mock("@/lib/hooks/use-videos", () => ({
  useAssociateVideoSummary: (...args: unknown[]) => mocks.useAssociateVideoSummary(...args),
  useDeleteVideoSummary: (...args: unknown[]) => mocks.useDeleteVideoSummary(...args),
  useDisassociateVideoSummary: (...args: unknown[]) => mocks.useDisassociateVideoSummary(...args),
  useVideoSummary: (...args: unknown[]) => mocks.useVideoSummary(...args),
}));

vi.mock("@/components/reader/markdown-viewer", () => ({
  MarkdownViewer: ({ content }: { content: string }) => <div>{content}</div>,
}));

import { VideoDetail } from "@/components/studio/video-detail";

function renderVideoDetail(ui: ReactNode) {
  const queryClient = createQueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <LanguageContext.Provider value={{ lang: "en", setLang: () => {} }}>
        {ui}
      </LanguageContext.Provider>
    </QueryClientProvider>
  );
}

describe("VideoDetail", () => {
  beforeEach(() => {
    mocks.useAssociateVideoSummary.mockReset();
    mocks.useDeleteVideoSummary.mockReset();
    mocks.useDisassociateVideoSummary.mockReset();
    mocks.useVideoSummary.mockReset();

    mocks.useAssociateVideoSummary.mockReturnValue({
      isPending: false,
      mutateAsync: vi.fn().mockResolvedValue(undefined),
    });
    mocks.useDisassociateVideoSummary.mockReturnValue({
      isPending: false,
      mutateAsync: vi.fn().mockResolvedValue(undefined),
    });
    mocks.useDeleteVideoSummary.mockReturnValue({
      isPending: false,
      mutateAsync: vi.fn().mockResolvedValue(undefined),
    });
    mocks.useVideoSummary.mockReturnValue({
      data: {
        summary_id: "sum-1",
        notebook_id: null,
        platform: "bilibili",
        video_id: "BV1",
        source_url: "https://www.bilibili.com/video/BV1",
        title: "Video Detail",
        cover_url: null,
        duration_seconds: 240,
        uploader_name: "UP Detail",
        uploader_id: "uploader-1",
        summary_content: "# Detailed Summary",
        status: "completed",
        error_message: null,
        document_ids: [],
        stats: null,
        transcript_source: "subtitle",
        transcript_path: null,
        created_at: "2026-03-27T00:00:00Z",
        updated_at: "2026-03-27T00:00:00Z",
      },
      isLoading: false,
      isError: false,
    });
  });

  it("renders summary details and associates to the current notebook", async () => {
    const user = userEvent.setup();
    const onBack = vi.fn();

    renderVideoDetail(
      <VideoDetail notebookId="notebook-1" summaryId="sum-1" onBack={onBack} />
    );

    expect(screen.getByText("Video Detail")).toBeInTheDocument();
    expect(screen.getByText("# Detailed Summary")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /associate to notebook/i }));

    expect(mocks.useAssociateVideoSummary.mock.results[0]?.value.mutateAsync).toHaveBeenCalledWith("sum-1");
  });

  it("confirms deletion and returns to the list after delete succeeds", async () => {
    const user = userEvent.setup();
    const onBack = vi.fn();

    renderVideoDetail(
      <VideoDetail notebookId="notebook-1" summaryId="sum-1" onBack={onBack} />
    );

    await user.click(screen.getByRole("button", { name: /^delete$/i }));
    await user.click(screen.getByRole("button", { name: /^confirm$/i }));

    await waitFor(() => {
      expect(mocks.useDeleteVideoSummary.mock.results[0]?.value.mutateAsync).toHaveBeenCalledWith("sum-1");
      expect(onBack).toHaveBeenCalledOnce();
    });
  });
});
