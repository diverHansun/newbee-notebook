// @vitest-environment node

import type { NextRequest } from "next/server";
import { afterEach, describe, expect, it, vi } from "vitest";

import { POST } from "./route";

describe("POST /api/v1/documents/library/upload", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
    delete process.env.INTERNAL_API_URL;
  });

  it("defaults to 127.0.0.1 for host-debug uploads when INTERNAL_API_URL is unset", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ documents: [], total: 0, failed: [] }), {
        status: 201,
        headers: {
          "content-type": "application/json",
        },
      })
    );
    vi.stubGlobal("fetch", fetchMock);

    const formData = new FormData();
    formData.append("files", new File(["demo"], "demo.epub", { type: "application/epub+zip" }));

    const response = await POST(
      new Request("http://localhost:3000/api/v1/documents/library/upload", {
        method: "POST",
        body: formData,
      }) as NextRequest
    );

    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/v1/documents/library/upload",
      expect.objectContaining({
        method: "POST",
      })
    );
    expect(response.status).toBe(201);
  });
});
