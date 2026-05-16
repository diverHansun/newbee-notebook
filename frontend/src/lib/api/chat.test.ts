import { describe, expect, it, vi } from "vitest";

const apiFetch = vi.fn();

vi.mock("@/lib/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api/client")>();
  return {
    ...actual,
    apiFetch: (...args: unknown[]) => apiFetch(...args),
  };
});

import { confirmChatAction } from "@/lib/api/chat";

describe("chat api", () => {
  it("resolves permission requests through the canonical endpoint", async () => {
    apiFetch.mockResolvedValueOnce({ status: "resolved" });

    await confirmChatAction("session-1", {
      request_id: "req-1",
      response: "once",
    });

    expect(apiFetch).toHaveBeenCalledWith("/chat/session-1/permission-requests/resolve", {
      method: "POST",
      body: {
        request_id: "req-1",
        response: "once",
      },
    });
  });
});
