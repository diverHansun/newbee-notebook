import { renderHook, waitFor } from "@testing-library/react";
import { act } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useChatImageUpload } from "@/lib/hooks/useChatImageUpload";

const uploadChatImage = vi.fn();

vi.mock("@/lib/api/chat-images", () => ({
  uploadChatImage: (...args: unknown[]) => uploadChatImage(...args),
}));

describe("useChatImageUpload", () => {
  beforeEach(() => {
    uploadChatImage.mockReset();
    uploadChatImage.mockResolvedValue({
      image_id: "img-1",
      mime_type: "image/png",
      size_bytes: 128,
      width: 64,
      height: 64,
      preview_url: "/api/v1/chat/images/img-1/thumbnail",
      thumbnail_url: "/api/v1/chat/images/img-1/thumbnail",
    });
    Object.defineProperty(URL, "createObjectURL", {
      configurable: true,
      value: vi.fn(() => "blob:preview"),
    });
    Object.defineProperty(URL, "revokeObjectURL", {
      configurable: true,
      value: vi.fn(),
    });
  });

  it("uploads an added image and exposes ready image ids", async () => {
    const { result } = renderHook(() =>
      useChatImageUpload({
        sessionId: "session-1",
        ensureSession: async () => "session-1",
      })
    );

    await act(async () => {
      await result.current.add(new File(["png"], "diagram.png", { type: "image/png" }));
    });

    await waitFor(() => {
      expect(result.current.attachments[0]).toEqual(
        expect.objectContaining({
          status: "ready",
          imageId: "img-1",
          localUrl: "blob:preview",
        })
      );
    });
    expect(result.current.imageIds).toEqual(["img-1"]);
    expect(uploadChatImage).toHaveBeenCalledWith("session-1", expect.any(File));
  });

  it("limits the current message to ten images and keeps rejected files out", async () => {
    const { result } = renderHook(() =>
      useChatImageUpload({
        sessionId: "session-1",
        ensureSession: async () => "session-1",
      })
    );

    for (let i = 0; i < 11; i += 1) {
      await act(async () => {
        await result.current.add(new File(["png"], `diagram-${i}.png`, { type: "image/png" }));
      });
    }

    expect(result.current.attachments).toHaveLength(10);
    expect(result.current.lastError?.code).toBe("count_exceeded");
  });

  it("releases object urls on reset", async () => {
    const { result } = renderHook(() =>
      useChatImageUpload({
        sessionId: "session-1",
        ensureSession: async () => "session-1",
      })
    );

    await act(async () => {
      await result.current.add(new File(["png"], "diagram.png", { type: "image/png" }));
    });

    await act(async () => {
      result.current.reset();
    });

    expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:preview");
    expect(result.current.attachments).toHaveLength(0);
  });

  it("releases object urls when an image is removed", async () => {
    const { result } = renderHook(() =>
      useChatImageUpload({
        sessionId: "session-1",
        ensureSession: async () => "session-1",
      })
    );

    await act(async () => {
      await result.current.add(new File(["png"], "diagram.png", { type: "image/png" }));
    });

    const attachmentId = result.current.attachments[0]?.id;
    expect(attachmentId).toBeTruthy();

    act(() => {
      result.current.remove(attachmentId!);
    });

    expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:preview");
    expect(result.current.attachments).toHaveLength(0);
  });

  it("releases object urls when the hook unmounts", async () => {
    const { result, unmount } = renderHook(() =>
      useChatImageUpload({
        sessionId: "session-1",
        ensureSession: async () => "session-1",
      })
    );

    await act(async () => {
      await result.current.add(new File(["png"], "diagram.png", { type: "image/png" }));
    });

    unmount();

    expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:preview");
  });
});
