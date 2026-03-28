import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { LanguageContext } from "@/lib/i18n/language-context";
import { createQueryClient } from "@/test/test-utils";

const mocks = vi.hoisted(() => ({
  useAllVideoSummaries: vi.fn(),
  useVideoSummaries: vi.fn(),
}));

vi.mock("@/lib/hooks/use-videos", () => ({
  useAllVideoSummaries: (...args: unknown[]) => mocks.useAllVideoSummaries(...args),
  useVideoSummaries: (...args: unknown[]) => mocks.useVideoSummaries(...args),
}));

vi.mock("@/components/studio/video-input-area", () => ({
  VideoInputArea: () => <div data-testid="video-input-area" />,
}));

import { VideoList } from "@/components/studio/video-list";

function renderVideoList(ui: ReactNode) {
  const queryClient = createQueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <LanguageContext.Provider value={{ lang: "en", setLang: () => {} }}>
        {ui}
      </LanguageContext.Provider>
    </QueryClientProvider>
  );
}

describe("VideoList", () => {
  beforeEach(() => {
    mocks.useAllVideoSummaries.mockReset();
    mocks.useVideoSummaries.mockReset();
    mocks.useAllVideoSummaries.mockReturnValue({
      data: {
        summaries: [
          {
            summary_id: "sum-all-1",
            notebook_id: null,
            platform: "bilibili",
            video_id: "BV1",
            title: "All Videos Entry",
            cover_url: null,
            duration_seconds: 120,
            uploader_name: "UP All",
            status: "completed",
            created_at: "2026-03-27T00:00:00Z",
            updated_at: "2026-03-27T00:00:00Z",
          },
        ],
        total: 1,
      },
      isLoading: false,
      isError: false,
    });
    mocks.useVideoSummaries.mockReturnValue({
      data: {
        summaries: [
          {
            summary_id: "sum-nb-1",
            notebook_id: "notebook-1",
            platform: "bilibili",
            video_id: "BV2",
            title: "Notebook Videos Entry",
            cover_url: null,
            duration_seconds: 180,
            uploader_name: "UP Notebook",
            status: "completed",
            created_at: "2026-03-27T00:00:00Z",
            updated_at: "2026-03-27T00:00:00Z",
          },
        ],
        total: 1,
      },
      isLoading: false,
      isError: false,
    });
  });

  it("renders the input area and switches between all and notebook-scoped lists", async () => {
    const user = userEvent.setup();
    const onOpenSummary = vi.fn();

    renderVideoList(<VideoList notebookId="notebook-1" onOpenSummary={onOpenSummary} onBack={vi.fn()} />);

    expect(screen.getByTestId("video-input-area")).toBeInTheDocument();
    expect(screen.getByText("All Videos Entry")).toBeInTheDocument();

    await user.click(screen.getByRole("radio", { name: "This Notebook" }));

    expect(screen.getByText("Notebook Videos Entry")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Notebook Videos Entry/i }));

    expect(onOpenSummary).toHaveBeenCalledWith("sum-nb-1");
  });

  it("preserves the selected filter when the list remounts", async () => {
    const user = userEvent.setup();
    const onOpenSummary = vi.fn();

    const view = renderVideoList(<VideoList notebookId="notebook-1" onOpenSummary={onOpenSummary} onBack={vi.fn()} />);

    await user.click(screen.getByRole("radio", { name: "This Notebook" }));
    expect(screen.getByText("Notebook Videos Entry")).toBeInTheDocument();

    view.unmount();
    renderVideoList(<VideoList notebookId="notebook-1" onOpenSummary={onOpenSummary} onBack={vi.fn()} />);

    expect(screen.getByRole("radio", { name: "This Notebook" })).toBeChecked();
    expect(screen.getByText("Notebook Videos Entry")).toBeInTheDocument();
    expect(screen.queryByText("All Videos Entry")).not.toBeInTheDocument();
  });
});
