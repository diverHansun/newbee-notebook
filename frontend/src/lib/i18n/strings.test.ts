import { describe, expect, it } from "vitest";

import { uiStrings } from "@/lib/i18n/strings";

describe("uiStrings.chat.sessionCount", () => {
  it("documents the 50-session notebook cap in Chinese and English", () => {
    expect(uiStrings.chat.sessionCount.zh).toBe("{n} / 50 个会话");
    expect(uiStrings.chat.sessionCount.en).toBe("{n} / 50 sessions");
  });
});
