"use client";

import { DOCUMENT_TYPE_GROUPS } from "@/lib/library/document-type-groups";
import { useLang } from "@/lib/hooks/useLang";
import { uiStrings } from "@/lib/i18n/strings";
import type { DocumentTypeGroup } from "@/lib/api/types";

type TypeFilterChipsProps = {
  selected: ReadonlySet<DocumentTypeGroup>;
  onToggle: (group: DocumentTypeGroup) => void;
  onClear: () => void;
};

const GROUP_LABEL_KEYS: Record<DocumentTypeGroup, keyof typeof uiStrings.libraryPage> = {
  document: "typeGroupDocument",
  word: "typeGroupWord",
  slides: "typeGroupSlides",
  web: "typeGroupWeb",
  image: "typeGroupImage",
  sheet: "typeGroupSheet",
  ebook: "typeGroupEbook",
  text: "typeGroupText",
};

export function TypeFilterChips({ selected, onToggle, onClear }: TypeFilterChipsProps) {
  const { t, ti } = useLang();
  const activeCount = selected.size;

  return (
    <div
      className="row"
      style={{ alignItems: "center", flexWrap: "wrap", rowGap: 6 }}
      role="group"
      aria-label={t(uiStrings.libraryPage.typeFilterLabel)}
    >
      <span className="muted" style={{ fontSize: 12, marginRight: 4 }}>
        {t(uiStrings.libraryPage.typeFilterLabel)}
      </span>
      <div className="chip-filter-bar">
        {DOCUMENT_TYPE_GROUPS.map((group) => {
          const labelKey = GROUP_LABEL_KEYS[group];
          const label = t(uiStrings.libraryPage[labelKey] as { zh: string; en: string });
          const isActive = selected.has(group);
          return (
            <button
              key={group}
              type="button"
              className="chip-filter"
              data-active={isActive}
              aria-pressed={isActive}
              onClick={() => onToggle(group)}
            >
              {label}
            </button>
          );
        })}
      </div>
      {activeCount > 0 && (
        <>
          <span className="muted" style={{ fontSize: 12, marginLeft: 4 }}>
            {ti(uiStrings.libraryPage.typeFilterActiveCount, { n: activeCount })}
          </span>
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            onClick={onClear}
          >
            {t(uiStrings.libraryPage.typeFilterClear)}
          </button>
        </>
      )}
    </div>
  );
}
