import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { LanguageContext } from "@/lib/i18n/language-context";
import { createQueryClient } from "@/test/test-utils";

const apiMocks = vi.hoisted(() => ({
  streamBilibiliQrLogin: vi.fn(),
  summarizeVideoStream: vi.fn(),
}));

const hookMocks = vi.hoisted(() => ({
  useBilibiliAuthStatus: vi.fn(),
  useBilibiliLogout: vi.fn(),
}));

vi.mock("@/lib/api/bilibili-auth", () => ({
  streamBilibiliQrLogin: (...args: unknown[]) => apiMocks.streamBilibiliQrLogin(...args),
}));

vi.mock("@/lib/api/videos", () => ({
  summarizeVideoStream: (...args: unknown[]) => apiMocks.summarizeVideoStream(...args),
}));

vi.mock("@/lib/hooks/use-bilibili-auth", () => ({
  useBilibiliAuthStatus: (...args: unknown[]) => hookMocks.useBilibiliAuthStatus(...args),
  useBilibiliLogout: (...args: unknown[]) => hookMocks.useBilibiliLogout(...args),
}));

import { VideoInputArea } from "@/components/studio/video-input-area";

function renderVideoInputArea(ui: ReactNode) {
  const queryClient = createQueryClient();
  const view = render(
    <QueryClientProvider client={queryClient}>
      <LanguageContext.Provider value={{ lang: "en", setLang: () => {} }}>
        {ui}
      </LanguageContext.Provider>
    </QueryClientProvider>
  );
  return { ...view, queryClient };
}

describe("VideoInputArea", () => {
  beforeEach(() => {
    apiMocks.streamBilibiliQrLogin.mockReset();
    apiMocks.summarizeVideoStream.mockReset();
    hookMocks.useBilibiliAuthStatus.mockReset();
    hookMocks.useBilibiliLogout.mockReset();

    hookMocks.useBilibiliAuthStatus.mockReturnValue({
      data: { logged_in: false },
      isLoading: false,
    });
    hookMocks.useBilibiliLogout.mockReturnValue({
      isPending: false,
      mutateAsync: vi.fn().mockResolvedValue(undefined),
    });
  });

  it("rejects non-bilibili urls before starting summarize stream", async () => {
    const user = userEvent.setup();
    renderVideoInputArea(<VideoInputArea notebookId="notebook-1" />);

    await user.type(screen.getByPlaceholderText(/bilibili.*youtube/i), "https://example.com/video/123");
    await user.click(screen.getByRole("button", { name: /summarize/i }));

    expect(apiMocks.summarizeVideoStream).not.toHaveBeenCalled();
    expect(screen.getByText(/enter a valid bilibili or youtube link or id/i)).toBeInTheDocument();
  });

  it("runs the summarize stream and refreshes the shared video list when done", async () => {
    const user = userEvent.setup();
    apiMocks.summarizeVideoStream.mockImplementation(
      async (_request: unknown, options?: { onEvent?: (event: unknown) => void }) => {
        options?.onEvent?.({ type: "start", video_id: "BV1" });
        options?.onEvent?.({ type: "summarize", video_id: "BV1" });
        options?.onEvent?.({
          type: "done",
          summary_id: "sum-1",
          status: "completed",
          reused: false,
        });
      }
    );

    const { queryClient } = renderVideoInputArea(<VideoInputArea notebookId="notebook-1" />);
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

    await user.type(screen.getByPlaceholderText(/bilibili.*youtube/i), "BV1abc411c7mD");
    await user.click(screen.getByRole("button", { name: /summarize/i }));

    await waitFor(() => {
      expect(apiMocks.summarizeVideoStream).toHaveBeenCalledOnce();
      expect(invalidateSpy).toHaveBeenCalledWith({
        queryKey: ["video-summaries", "all"],
      });
    });
  });

  it("refreshes video lists as soon as the summarize stream starts", async () => {
    const user = userEvent.setup();
    apiMocks.summarizeVideoStream.mockImplementation(
      async (_request: unknown, options?: { onEvent?: (event: unknown) => void }) => {
        options?.onEvent?.({ type: "start", video_id: "BV1" });
      }
    );

    const { queryClient } = renderVideoInputArea(<VideoInputArea notebookId="notebook-1" />);
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

    await user.type(screen.getByPlaceholderText(/bilibili.*youtube/i), "BV1abc411c7mD");
    await user.click(screen.getByRole("button", { name: /summarize/i }));

    await waitFor(() => {
      expect(apiMocks.summarizeVideoStream).toHaveBeenCalledOnce();
      expect(invalidateSpy).toHaveBeenCalledWith({
        queryKey: ["video-summaries", "all"],
      });
      expect(invalidateSpy).toHaveBeenCalledWith({
        queryKey: ["video-summaries", "notebook-1"],
      });
    });
  });

  it("opens the qr login dialog and shows the qr image when login starts", async () => {
    const user = userEvent.setup();
    apiMocks.streamBilibiliQrLogin.mockImplementation(
      async (options?: { onEvent?: (event: unknown) => void }) => {
        options?.onEvent?.({
          type: "qr_generated",
          qr_url: "https://qr.example",
          image_base64: "abc123",
        });
      }
    );

    renderVideoInputArea(<VideoInputArea notebookId="notebook-1" />);

    await user.type(screen.getByPlaceholderText(/bilibili.*youtube/i), "BV1abc411c7mD");
    await user.click(screen.getByRole("button", { name: /bilibili login/i }));

    await waitFor(() => {
      expect(screen.getByText(/scan qr code with bilibili app/i)).toBeInTheDocument();
      expect(screen.getByAltText(/bilibili login qr/i)).toBeInTheDocument();
    });
  });

  it("shows step-by-step progress during summarization", async () => {
    const user = userEvent.setup();
    apiMocks.summarizeVideoStream.mockImplementation(
      async (_request: unknown, options?: { onEvent?: (event: unknown) => void }) => {
        options?.onEvent?.({ type: "start", video_id: "BV1" });
        options?.onEvent?.({ type: "subtitle", video_id: "BV1" });
        options?.onEvent?.({ type: "summarize", video_id: "BV1" });
        options?.onEvent?.({
          type: "done",
          summary_id: "sum-1",
          status: "completed",
          reused: false,
        });
      }
    );

    renderVideoInputArea(<VideoInputArea notebookId="notebook-1" />);

    await user.type(screen.getByPlaceholderText(/bilibili.*youtube/i), "BV1abc411c7mD");
    await user.click(screen.getByRole("button", { name: /summarize/i }));

    await waitFor(() => {
      expect(screen.getByText("Loading video info")).toBeInTheDocument();
      expect(screen.getByText("Fetching subtitles")).toBeInTheDocument();
      expect(screen.getByText("Generating summary")).toBeInTheDocument();
      expect(screen.getByText("Summary complete")).toBeInTheDocument();
    });
  });

  it("shows reused message when summary already exists", async () => {
    const user = userEvent.setup();
    apiMocks.summarizeVideoStream.mockImplementation(
      async (_request: unknown, options?: { onEvent?: (event: unknown) => void }) => {
        options?.onEvent?.({
          type: "done",
          summary_id: "sum-1",
          status: "completed",
          reused: true,
        });
      }
    );

    renderVideoInputArea(<VideoInputArea notebookId="notebook-1" />);

    await user.type(screen.getByPlaceholderText(/bilibili.*youtube/i), "BV1abc411c7mD");
    await user.click(screen.getByRole("button", { name: /summarize/i }));

    await waitFor(() => {
      expect(screen.getByText("Existing summary found")).toBeInTheDocument();
    });
  });

  it("shows friendly error and login button for auth errors", async () => {
    const user = userEvent.setup();
    apiMocks.summarizeVideoStream.mockImplementation(
      async (_request: unknown, options?: { onEvent?: (event: unknown) => void }) => {
        options?.onEvent?.({ type: "start", video_id: "BV1" });
        options?.onEvent?.({
          type: "error",
          message: "get_player_info: Credential 类未提供 sessdata 或者为空。",
        });
      }
    );

    renderVideoInputArea(<VideoInputArea notebookId="notebook-1" />);

    await user.type(screen.getByPlaceholderText(/bilibili.*youtube/i), "BV1abc411c7mD");
    await user.click(screen.getByRole("button", { name: /summarize/i }));

    await waitFor(() => {
      expect(
        screen.getByText(/bilibili session expired or not logged in/i)
      ).toBeInTheDocument();
      const loginButtons = screen.getAllByRole("button", { name: /bilibili login/i });
      expect(loginButtons.length).toBeGreaterThanOrEqual(1);
    });
  });

  it("falls back to a qr link when the backend only returns qr_url", async () => {
    const user = userEvent.setup();
    apiMocks.streamBilibiliQrLogin.mockImplementation(
      async (options?: { onEvent?: (event: unknown) => void }) => {
        options?.onEvent?.({
          type: "qr_generated",
          qr_url: "https://qr.example/fallback",
        });
      }
    );

    renderVideoInputArea(<VideoInputArea notebookId="notebook-1" />);

    await user.type(screen.getByPlaceholderText(/bilibili.*youtube/i), "BV1abc411c7mD");
    await user.click(screen.getByRole("button", { name: /bilibili login/i }));

    await waitFor(() => {
      expect(screen.getByRole("link", { name: /open qr link/i })).toHaveAttribute(
        "href",
        "https://qr.example/fallback"
      );
    });
  });

  it("shows youtube status without bilibili login controls for youtube input", async () => {
    const user = userEvent.setup();
    renderVideoInputArea(<VideoInputArea notebookId="notebook-1" />);

    await user.type(screen.getByPlaceholderText(/bilibili.*youtube/i), "https://youtu.be/dQw4w9WgXcQ");

    expect(screen.getByText("YouTube")).toBeInTheDocument();
    expect(screen.getByText(/no login required/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /bilibili login/i })).not.toBeInTheDocument();
  });
});
