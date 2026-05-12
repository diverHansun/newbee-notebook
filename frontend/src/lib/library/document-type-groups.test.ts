import { describe, expect, it } from "vitest";

import {
  DOCUMENT_TYPE_GROUPS,
  assertFullCoverage,
  expandGroupsToTypes,
  typesForGroup,
} from "@/lib/library/document-type-groups";

const ALL_TYPES = ["pdf", "txt", "docx", "pptx", "epub", "md", "csv", "xlsx"] as const;

describe("document-type-groups", () => {
  it("covers all 6 declared groups", () => {
    expect(DOCUMENT_TYPE_GROUPS).toEqual([
      "document",
      "word",
      "slides",
      "sheet",
      "ebook",
      "text",
    ]);
  });

  it("covers every DocumentType across groups (no gaps)", () => {
    const covered = new Set<string>();
    for (const group of DOCUMENT_TYPE_GROUPS) {
      for (const type of typesForGroup(group)) {
        covered.add(type);
      }
    }
    for (const type of ALL_TYPES) {
      expect(covered.has(type)).toBe(true);
    }
    expect(covered.size).toBe(ALL_TYPES.length);
  });

  it("keeps groups mutually exclusive (each type in exactly one group)", () => {
    const seen = new Map<string, string>();
    for (const group of DOCUMENT_TYPE_GROUPS) {
      for (const type of typesForGroup(group)) {
        expect(seen.has(type)).toBe(false);
        seen.set(type, group);
      }
    }
  });

  it("assertFullCoverage passes without throwing", () => {
    expect(() => assertFullCoverage()).not.toThrow();
  });

  it("expandGroupsToTypes returns empty for empty input", () => {
    expect(expandGroupsToTypes([])).toEqual([]);
  });

  it("expands single group to its types", () => {
    expect(expandGroupsToTypes(["sheet"])).toEqual(["xlsx", "csv"]);
  });

  it("expands multiple groups and deduplicates", () => {
    const result = expandGroupsToTypes(["slides", "word"]);
    expect(result.sort()).toEqual(["docx", "pptx"]);
  });
});
