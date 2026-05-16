import { beforeEach, describe, expect, it, vi } from "vitest";

import { deleteSkill, listSkills, toggleSkill } from "@/lib/api/skills";

const fetchMock = vi.fn();

function createJsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "Content-Type": "application/json",
    },
  });
}

describe("skills api client", () => {
  beforeEach(() => {
    fetchMock.mockReset();
    vi.stubGlobal("fetch", fetchMock);
  });

  it("lists the skills catalog", async () => {
    fetchMock.mockResolvedValue(
      createJsonResponse({
        skills: [
          {
            name: "note",
            command: "/note",
            description: "Note and mark management skill",
            enabled: true,
            kind: "builtin",
            source: "studio",
            content_hash: "",
            path: "",
            scopes: ["/note"],
            manageable: false,
            deletable: false,
            readonly_reason: "builtin",
          },
        ],
      })
    );

    const result = await listSkills();

    expect(fetchMock).toHaveBeenCalledWith("/api/v1/skills", expect.any(Object));
    expect(result.skills[0].kind).toBe("builtin");
  });

  it("toggles an installed skill", async () => {
    fetchMock.mockResolvedValue(
      createJsonResponse({
        name: "demo",
        command: "/demo",
        description: "Demo skill",
        enabled: false,
        kind: "installed",
        source: "local",
        content_hash: "hash123",
        path: "configs/skills/demo",
        scopes: ["/demo"],
        manageable: true,
        deletable: true,
        readonly_reason: null,
      })
    );

    await toggleSkill("demo", false);

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/skills/demo/toggle",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ enabled: false }),
      })
    );
  });

  it("deletes an installed skill", async () => {
    fetchMock.mockResolvedValue(createJsonResponse({ deleted: true, name: "demo" }));

    const result = await deleteSkill("demo");

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/skills/demo",
      expect.objectContaining({ method: "DELETE" })
    );
    expect(result.deleted).toBe(true);
  });
});
