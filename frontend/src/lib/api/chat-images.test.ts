import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  getChatImageDataUrl,
  getChatImageThumbnailUrl,
  uploadChatImage,
} from "@/lib/api/chat-images";

const fetchMock = vi.fn();

function createJsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "Content-Type": "application/json",
    },
  });
}

describe("chat images api client", () => {
  beforeEach(() => {
    fetchMock.mockReset();
    vi.stubGlobal("fetch", fetchMock);
  });

  it("uploads a single image as multipart files field", async () => {
    fetchMock.mockResolvedValue(
      createJsonResponse({
        images: [
          {
            image_id: "img-1",
            mime_type: "image/png",
            size_bytes: 12,
            width: 32,
            height: 32,
            preview_url: "/api/v1/chat/images/img-1/thumbnail",
            thumbnail_url: "/api/v1/chat/images/img-1/thumbnail",
          },
        ],
        errors: [],
      })
    );

    const file = new File(["png"], "diagram.png", { type: "image/png" });
    const result = await uploadChatImage("session-1", file);

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/chat/sessions/session-1/images",
      expect.objectContaining({
        method: "POST",
        body: expect.any(FormData),
      })
    );
    const body = fetchMock.mock.calls[0]?.[1]?.body as FormData;
    expect(body.getAll("files")).toEqual([file]);
    expect(result.image_id).toBe("img-1");
  });

  it("builds same-origin thumbnail and data urls", () => {
    expect(getChatImageThumbnailUrl("img-1")).toBe("/api/v1/chat/images/img-1/thumbnail");
    expect(getChatImageDataUrl("img-1")).toBe("/api/v1/chat/images/img-1/data");
  });
});
