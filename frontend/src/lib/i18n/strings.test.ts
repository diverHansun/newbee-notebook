import { describe, expect, it } from "vitest";

import { uiStrings } from "@/lib/i18n/strings";

describe("uiStrings.chat.sessionCount", () => {
  it("documents the 50-session notebook cap in Chinese and English", () => {
    expect(uiStrings.chat.sessionCount.zh).toBe("{n} / 50 个会话");
    expect(uiStrings.chat.sessionCount.en).toBe("{n} / 50 sessions");
  });
});

describe("uiStrings.libraryPage type filter strings", () => {
  const requiredKeys = [
    "typeFilterLabel",
    "typeFilterClear",
    "typeFilterActiveCount",
    "typeGroupDocument",
    "typeGroupWord",
    "typeGroupSlides",
    "typeGroupWeb",
    "typeGroupImage",
    "typeGroupSheet",
    "typeGroupEbook",
    "typeGroupText",
    "tableType",
    "typeBadgeAriaLabel",
  ] as const;

  it.each(requiredKeys)("has non-empty zh and en for %s", (key) => {
    const entry = uiStrings.libraryPage[key];
    expect(entry).toBeDefined();
    expect(entry.zh.length).toBeGreaterThan(0);
    expect(entry.en.length).toBeGreaterThan(0);
  });
});
