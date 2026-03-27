import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  getBilibiliAuthStatus,
  logoutBilibili,
  streamBilibiliQrLogin,
} from "@/lib/api/bilibili-auth";

const fetchMock = vi.fn();

function createJsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "Content-Type": "application/json",
    },
  });
}

function createSseResponse(chunks: string[]) {
  const encoder = new TextEncoder();
  return new Response(
    new ReadableStream<Uint8Array>({
      start(controller) {
        for (const chunk of chunks) {
          controller.enqueue(encoder.encode(chunk));
        }
        controller.close();
      },
    }),
    {
      status: 200,
      headers: {
        "Content-Type": "text/event-stream",
      },
    }
  );
}

describe("bilibili auth api client", () => {
  beforeEach(() => {
    fetchMock.mockReset();
    vi.stubGlobal("fetch", fetchMock);
  });

  it("loads bilibili auth status", async () => {
    fetchMock.mockResolvedValue(createJsonResponse({ logged_in: true }));

    const result = await getBilibiliAuthStatus();

    expect(fetchMock).toHaveBeenCalledWith("/api/v1/bilibili/auth/status", expect.any(Object));
    expect(result.logged_in).toBe(true);
  });

  it("logs out the current bilibili session", async () => {
    fetchMock.mockResolvedValue(new Response(null, { status: 204 }));

    await logoutBilibili();

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/bilibili/auth/logout",
      expect.objectContaining({
        method: "POST",
      })
    );
  });

  it("parses qr login sse events", async () => {
    fetchMock.mockResolvedValue(
      createSseResponse([
        'event: qr_generated\ndata: {"qr_url":"https://qr.example","image_base64":"abc"}\n\n',
        "event: scanned\ndata: {}\n\n",
        "event: done\ndata: {}\n\n",
      ])
    );

    const events: unknown[] = [];

    await streamBilibiliQrLogin({
      onEvent: (event) => events.push(event),
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/bilibili/auth/qr",
      expect.objectContaining({
        method: "GET",
      })
    );
    expect(events).toEqual([
      { type: "qr_generated", qr_url: "https://qr.example", image_base64: "abc" },
      { type: "scanned" },
      { type: "done" },
    ]);
  });
});
