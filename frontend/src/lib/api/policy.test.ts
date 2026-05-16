import { beforeEach, describe, expect, it, vi } from "vitest";

import { getEffectivePolicy, updatePolicyPreference } from "@/lib/api/policy";

const fetchMock = vi.fn();

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "Content-Type": "application/json",
    },
  });
}

describe("policy api client", () => {
  beforeEach(() => {
    fetchMock.mockReset();
    vi.stubGlobal("fetch", fetchMock);
  });

  it("reads the effective session policy", async () => {
    fetchMock.mockResolvedValue(
      jsonResponse({
        notebook_id: "nb-1",
        session_id: "session-1",
        policy: "default",
        source: "default",
      })
    );

    const result = await getEffectivePolicy("nb-1", "session-1");

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/policy/notebooks/nb-1/effective?session_id=session-1",
      expect.objectContaining({ headers: expect.any(Headers) })
    );
    expect(result.policy).toBe("default");
  });

  it("updates a policy preference with explicit scope", async () => {
    fetchMock.mockResolvedValue(
      jsonResponse({
        notebook_id: "nb-1",
        session_id: "session-1",
        policy: "yolo",
        source: "session",
      })
    );

    const result = await updatePolicyPreference("nb-1", {
      scope: "session",
      session_id: "session-1",
      policy: "yolo",
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/policy/notebooks/nb-1",
      expect.objectContaining({
        method: "PUT",
        body: JSON.stringify({
          scope: "session",
          session_id: "session-1",
          policy: "yolo",
        }),
      })
    );
    expect(result.source).toBe("session");
  });
});
