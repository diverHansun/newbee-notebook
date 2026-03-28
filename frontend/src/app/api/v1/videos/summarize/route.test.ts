// @vitest-environment node

import { afterEach, describe, expect, it, vi } from "vitest";

import { POST } from "./route";

describe("POST /api/v1/videos/summarize", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
    delete process.env.INTERNAL_API_URL;
  });

  it("streams summarize SSE events from the backend without buffering", async () => {
    process.env.INTERNAL_API_URL = "http://127.0.0.1:8000";
    const backendStream = new ReadableStream({
      start(controller) {
        controller.enqueue(new TextEncoder().encode("event: start\n"));
        controller.enqueue(new TextEncoder().encode('data: {"video_id":"BV1"}\n\n'));
        controller.close();
      },
    });

    const fetchMock = vi.fn().mockResolvedValue(
      new Response(backendStream, {
        status: 200,
        headers: {
          "content-type": "text/event-stream; charset=utf-8",
          "cache-control": "no-cache, no-transform",
          "x-accel-buffering": "no",
        },
      })
    );
    vi.stubGlobal("fetch", fetchMock);

    const response = await POST(
      new Request("http://localhost:3000/api/v1/videos/summarize", {
        method: "POST",
        headers: {
          "content-type": "application/json",
        },
        body: JSON.stringify({
          url_or_bvid: "BV1",
          notebook_id: "notebook-1",
        }),
      })
    );

    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/v1/videos/summarize",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          accept: "text/event-stream",
          "content-type": "application/json",
        }),
        body: JSON.stringify({
          url_or_bvid: "BV1",
          notebook_id: "notebook-1",
        }),
        cache: "no-store",
      })
    );
    expect(response.status).toBe(200);
    expect(response.headers.get("content-type")).toContain("text/event-stream");
    expect(await response.text()).toContain("event: start");
  });
});
