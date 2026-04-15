import { describe, expect, it } from "vitest";

import {
  buildSessionDisplayTitleMap,
  getSessionDisplayTitle,
} from "@/lib/chat/session-labels";
import type { Session } from "@/lib/api/types";

const sessions: Session[] = [
  {
    session_id: "session-2",
    notebook_id: "nb-1",
    title: null,
    message_count: 0,
    include_ec_context: false,
    created_at: "2026-04-02T00:00:00.000Z",
    updated_at: "2026-04-04T00:00:00.000Z",
  },
  {
    session_id: "session-1",
    notebook_id: "nb-1",
    title: null,
    message_count: 0,
    include_ec_context: false,
    created_at: "2026-04-01T00:00:00.000Z",
    updated_at: "2026-04-05T00:00:00.000Z",
  },
  {
    session_id: "session-3",
    notebook_id: "nb-1",
    title: "Focused review",
    message_count: 0,
    include_ec_context: false,
    created_at: "2026-04-03T00:00:00.000Z",
    updated_at: "2026-04-06T00:00:00.000Z",
  },
];

describe("session-labels", () => {
  it("renders untitled sessions from creation order instead of session ids", () => {
    const titleMap = buildSessionDisplayTitleMap(sessions, "Session {n}");

    expect(getSessionDisplayTitle(sessions[1], titleMap, "Select session")).toBe("Session 1");
    expect(getSessionDisplayTitle(sessions[0], titleMap, "Select session")).toBe("Session 2");
  });

  it("keeps explicit titles and preserves the placeholder for an empty selection", () => {
    const titleMap = buildSessionDisplayTitleMap(sessions, "Session {n}");

    expect(getSessionDisplayTitle(sessions[2], titleMap, "Select session")).toBe("Focused review");
    expect(getSessionDisplayTitle(null, titleMap, "Select session")).toBe("Select session");
  });
});