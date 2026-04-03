import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  associateVideoSummary,
  deleteVideoSummary,
  disassociateVideoSummary,
  getVideoInfo,
  getVideoSummary,
  listAllVideoSummaries,
  listVideoSummaries,
  summarizeVideoStream,
} from "@/lib/api/videos";

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

describe("video api client", () => {
  beforeEach(() => {
    fetchMock.mockReset();
    vi.stubGlobal("fetch", fetchMock);
  });

  it("lists all video summaries from the shared video endpoint", async () => {
    fetchMock.mockResolvedValue(
      createJsonResponse({
        summaries: [{ summary_id: "sum-1", notebook_id: null, platform: "bilibili", video_id: "BV1", title: "Video 1", cover_url: null, duration_seconds: 120, uploader_name: "UP", status: "completed", created_at: "2026-03-27T00:00:00Z", updated_at: "2026-03-27T00:00:00Z" }],
        total: 1,
      })
    );

    const result = await listAllVideoSummaries();

    expect(fetchMock).toHaveBeenCalledWith("/api/v1/videos", expect.any(Object));
    expect(result.total).toBe(1);
    expect(result.summaries[0]?.summary_id).toBe("sum-1");
  });

  it("lists notebook-scoped video summaries with notebook_id query param", async () => {
    fetchMock.mockResolvedValue(createJsonResponse({ summaries: [], total: 0 }));

    await listVideoSummaries("notebook-1");

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/videos?notebook_id=notebook-1",
      expect.any(Object)
    );
  });

  it("loads a single video summary", async () => {
    fetchMock.mockResolvedValue(
      createJsonResponse({
        summary_id: "sum-1",
        notebook_id: null,
        platform: "bilibili",
        video_id: "BV1",
        source_url: "https://www.bilibili.com/video/BV1",
        title: "Video 1",
        cover_url: null,
        duration_seconds: 120,
        uploader_name: "UP",
        uploader_id: "uploader-1",
        summary_content: "# Summary",
        status: "completed",
        error_message: null,
        document_ids: [],
        stats: null,
        transcript_source: "subtitle",
        transcript_path: null,
        created_at: "2026-03-27T00:00:00Z",
        updated_at: "2026-03-27T00:00:00Z",
      })
    );

    const result = await getVideoSummary("sum-1");

    expect(fetchMock).toHaveBeenCalledWith("/api/v1/videos/sum-1", expect.any(Object));
    expect(result.summary_content).toBe("# Summary");
  });

  it("supports association lifecycle operations", async () => {
    fetchMock.mockResolvedValue(new Response(null, { status: 204 }));

    await associateVideoSummary("sum-1", "notebook-1");
    await disassociateVideoSummary("sum-1");
    await deleteVideoSummary("sum-1");

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "/api/v1/videos/sum-1/notebook",
      expect.objectContaining({
        method: "POST",
      })
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "/api/v1/videos/sum-1/notebook",
      expect.objectContaining({
        method: "DELETE",
      })
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      "/api/v1/videos/sum-1",
      expect.objectContaining({
        method: "DELETE",
      })
    );
  });

  it("loads video info for a url or bvid", async () => {
    fetchMock.mockResolvedValue(
      createJsonResponse({
        video_id: "BV1",
        source_url: "https://www.bilibili.com/video/BV1",
        title: "Video 1",
        description: "desc",
        cover_url: null,
        duration_seconds: 120,
        uploader_name: "UP",
        uploader_id: "uploader-1",
        stats: { view: 100 },
      })
    );

    const result = await getVideoInfo("BV1");

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/videos/info?url_or_id=BV1",
      expect.any(Object)
    );
    expect(result.video_id).toBe("BV1");
  });

  it("parses backend video summarize sse events into typed client events", async () => {
    fetchMock.mockResolvedValue(
      createSseResponse([
        'event: start\ndata: {"video_id":"BV1"}\n\n',
        'event: info\ndata: {"video_id":"BV1","title":"Video 1","duration_seconds":120,"uploader_name":"UP"}\n\n',
        'event: subtitle\ndata: {"video_id":"BV1"}\n\n',
        'event: done\ndata: {"summary_id":"sum-1","status":"completed","reused":false}\n\n',
      ])
    );

    const events: unknown[] = [];

    await summarizeVideoStream(
      {
        url_or_id: "BV1",
        notebook_id: "notebook-1",
        lang: "en",
      },
      {
        onEvent: (event) => events.push(event),
      }
    );

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/videos/summarize",
      expect.objectContaining({
        method: "POST",
      })
    );
    expect(events).toEqual([
      { type: "start", video_id: "BV1" },
      {
        type: "info",
        video_id: "BV1",
        title: "Video 1",
        duration_seconds: 120,
        uploader_name: "UP",
        cover_url: undefined,
      },
      {
        type: "subtitle",
        video_id: "BV1",
        source: undefined,
        char_count: undefined,
        step: undefined,
        message: undefined,
        lang: undefined,
      },
      { type: "done", summary_id: "sum-1", status: "completed", reused: false },
    ]);
  });
});
