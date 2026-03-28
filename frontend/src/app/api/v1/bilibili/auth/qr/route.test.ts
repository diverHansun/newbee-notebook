// @vitest-environment node

import { afterEach, describe, expect, it, vi } from "vitest";

import { GET } from "./route";

describe("GET /api/v1/bilibili/auth/qr", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
    delete process.env.INTERNAL_API_URL;
  });

  it("streams SSE events from the backend without buffering", async () => {
    process.env.INTERNAL_API_URL = "http://127.0.0.1:8000";
    const backendStream = new ReadableStream({
      start(controller) {
        controller.enqueue(new TextEncoder().encode("event: qr_generated\n"));
        controller.enqueue(new TextEncoder().encode('data: {"qr_url":"https://example.com"}\n\n'));
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

    const response = await GET(new Request("http://localhost:3000/api/v1/bilibili/auth/qr"));

    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/v1/bilibili/auth/qr",
      expect.objectContaining({
        method: "GET",
        headers: expect.objectContaining({
          accept: "text/event-stream",
        }),
        cache: "no-store",
      })
    );
    expect(response.status).toBe(200);
    expect(response.headers.get("content-type")).toContain("text/event-stream");
    expect(await response.text()).toContain("event: qr_generated");
  });
});
