import type { DocumentType, DocumentTypeGroup } from "@/lib/api/types";

export const DOCUMENT_TYPE_GROUPS: readonly DocumentTypeGroup[] = [
  "document",
  "word",
  "slides",
  "web",
  "image",
  "sheet",
  "ebook",
  "text",
] as const;

const GROUP_TO_TYPES: Readonly<Record<DocumentTypeGroup, readonly DocumentType[]>> = {
  document: ["pdf"],
  word: ["docx"],
  slides: ["pptx"],
  web: ["html"],
  image: ["image"],
  sheet: ["xlsx", "csv"],
  ebook: ["epub"],
  text: ["md", "txt"],
};

const ALL_DOCUMENT_TYPES: readonly DocumentType[] = [
  "pdf",
  "txt",
  "docx",
  "pptx",
  "epub",
  "md",
  "csv",
  "xlsx",
  "html",
  "image",
];

export function typesForGroup(group: DocumentTypeGroup): readonly DocumentType[] {
  return GROUP_TO_TYPES[group];
}

export function expandGroupsToTypes(
  groups: Iterable<DocumentTypeGroup>
): DocumentType[] {
  const out: DocumentType[] = [];
  const seen = new Set<DocumentType>();
  for (const group of groups) {
    for (const type of GROUP_TO_TYPES[group]) {
      if (!seen.has(type)) {
        seen.add(type);
        out.push(type);
      }
    }
  }
  return out;
}

export function assertFullCoverage(): void {
  const covered = new Set<DocumentType>();
  for (const group of DOCUMENT_TYPE_GROUPS) {
    for (const type of GROUP_TO_TYPES[group]) {
      if (covered.has(type)) {
        throw new Error(
          `document-type-groups: type "${type}" appears in multiple groups`
        );
      }
      covered.add(type);
    }
  }
  for (const type of ALL_DOCUMENT_TYPES) {
    if (!covered.has(type)) {
      throw new Error(`document-type-groups: type "${type}" is not in any group`);
    }
  }
  if (covered.size !== ALL_DOCUMENT_TYPES.length) {
    throw new Error(
      `document-type-groups: covered ${covered.size} types but expected ${ALL_DOCUMENT_TYPES.length}`
    );
  }
}
