"use client";

import { useQuery } from "@tanstack/react-query";
import { saveAs } from "file-saver";
import JSZip from "jszip";
import { useCallback, useMemo, useState } from "react";

import { listLibraryDocuments } from "@/lib/api/library";
import { getNote, listAllNotes } from "@/lib/api/notes";
import type { NoteListItem } from "@/lib/api/types";
import { useLang } from "@/lib/hooks/useLang";
import { uiStrings } from "@/lib/i18n/strings";

type SortField = "created_at" | "updated_at";
type SortOrder = "asc" | "desc";

function formatTimestamp(value: string, locale: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(locale, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function buildMarkdownContent(note: {
  note_id: string;
  title: string;
  content: string;
  created_at: string;
  updated_at: string;
  document_ids: string[];
}, documentTitleMap: Map<string, string>): string {
  const docTitles = note.document_ids
    .map((id) => documentTitleMap.get(id) ?? id)
    .join(", ");

  return [
    "---",
    `id: ${note.note_id}`,
    `created: ${note.created_at}`,
    `updated: ${note.updated_at}`,
    `documents: [${docTitles}]`,
    "---",
    "",
    `# ${note.title || "Untitled"}`,
    "",
    note.content,
    "",
  ].join("\n");
}

function sanitizeFilename(name: string): string {
  return name.replace(/[<>:"/\\|?*]/g, "_").trim() || "untitled";
}

function triggerDownload(blob: Blob, filename: string) {
  saveAs(blob, filename);
}

export function NotesExportPanel() {
  const { t, ti, lang } = useLang();
  const locale = lang === "en" ? "en-US" : "zh-CN";

  const [sortBy, setSortBy] = useState<SortField>("updated_at");
  const [order, setOrder] = useState<SortOrder>("desc");
  const [documentFilter, setDocumentFilter] = useState<string>("");
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [exporting, setExporting] = useState(false);

  const notesQuery = useQuery({
    queryKey: ["notes-all", documentFilter || "all", sortBy, order],
    queryFn: () =>
      listAllNotes({
        document_id: documentFilter || undefined,
        sort_by: sortBy,
        order,
      }),
  });

  const documentsQuery = useQuery({
    queryKey: ["library-documents-for-filter"],
    queryFn: () => listLibraryDocuments({ limit: 200, offset: 0 }),
    staleTime: 60_000,
  });

  const documents = useMemo(
    () => documentsQuery.data?.data ?? [],
    [documentsQuery.data?.data]
  );
  const documentTitleMap = useMemo(
    () => new Map(documents.map((d) => [d.document_id, d.title])),
    [documents]
  );
  const notes = useMemo(
    () => notesQuery.data?.notes ?? [],
    [notesQuery.data?.notes]
  );

  const toggleSelect = useCallback((noteId: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(noteId)) {
        next.delete(noteId);
      } else {
        next.add(noteId);
      }
      return next;
    });
  }, []);

  const toggleSelectAll = useCallback(() => {
    setSelectedIds((prev) => {
      if (prev.size === notes.length) {
        return new Set();
      }
      return new Set(notes.map((n) => n.note_id));
    });
  }, [notes]);

  const exportSingleNote = useCallback(
    async (noteItem: NoteListItem) => {
      const note = await getNote(noteItem.note_id);
      const md = buildMarkdownContent(note, documentTitleMap);
      const filename = `${sanitizeFilename(note.title || "untitled")}_${note.note_id}.md`;
      const blob = new Blob([md], { type: "text/markdown;charset=utf-8" });
      triggerDownload(blob, filename);
    },
    [documentTitleMap]
  );

  const exportMultipleNotes = useCallback(
    async (noteIds: string[]) => {
      setExporting(true);
      try {
        const zip = new JSZip();
        const fullNotes = await Promise.all(noteIds.map((id) => getNote(id)));
        for (const note of fullNotes) {
          const md = buildMarkdownContent(note, documentTitleMap);
          const filename = `${sanitizeFilename(note.title || "untitled")}_${note.note_id}.md`;
          zip.file(filename, md);
        }
        const today = new Date().toISOString().slice(0, 10);
        const zipBlob = await zip.generateAsync({ type: "blob" });
        triggerDownload(zipBlob, `newbee-notes-export-${today}.zip`);
      } finally {
        setExporting(false);
      }
    },
    [documentTitleMap]
  );

  const handleExportSelected = useCallback(() => {
    const ids = Array.from(selectedIds);
    if (ids.length === 1) {
      const item = notes.find((n) => n.note_id === ids[0]);
      if (item) void exportSingleNote(item);
    } else if (ids.length > 1) {
      void exportMultipleNotes(ids);
    }
  }, [selectedIds, notes, exportSingleNote, exportMultipleNotes]);

  const handleExportAll = useCallback(() => {
    void exportMultipleNotes(notes.map((n) => n.note_id));
  }, [notes, exportMultipleNotes]);

  return (
    <div className="control-panel-stack">
      <div className="control-panel-card">
        <div className="control-panel-card-title">
          {t(uiStrings.dataPanel.personalNotes)}
        </div>
        <div className="control-panel-card-hint">
          {t(uiStrings.dataPanel.personalNotesDesc)}
        </div>

        {/* Filter and sort controls */}
        <div
          className="control-panel-card-body"
          style={{ display: "flex", flexDirection: "column", gap: 10 }}
        >
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
            <div className="relative" style={{ flex: 1, minWidth: 140 }}>
              <select
                className="w-full appearance-none rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--background))] px-3 py-1.5 pr-8 text-xs text-[hsl(var(--foreground))] transition-colors hover:border-[hsl(var(--ring))] focus:border-[hsl(var(--ring))] focus:outline-none"
                value={documentFilter}
                onChange={(e) => setDocumentFilter(e.target.value)}
              >
                <option value="">{t(uiStrings.dataPanel.allDocuments)}</option>
                {documents.map((doc) => (
                  <option key={doc.document_id} value={doc.document_id}>
                    {doc.title}
                  </option>
                ))}
              </select>
              <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center pr-2 text-[hsl(var(--muted-foreground))]">
                <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                  <path d="M3 4.5L6 7.5L9 4.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </div>
            </div>
          </div>

          <div style={{ display: "flex", gap: 6, alignItems: "center", flexWrap: "wrap" }}>
            <span className="muted" style={{ fontSize: 11, whiteSpace: "nowrap" }}>
              {t(uiStrings.dataPanel.sortBy)}
            </span>
            <div className="chip-filter-bar" style={{ gap: 4 }}>
              <button
                type="button"
                className="chip-filter"
                data-active={sortBy === "updated_at"}
                style={{ fontSize: 11, padding: "2px 8px" }}
                onClick={() => setSortBy("updated_at")}
              >
                {t(uiStrings.dataPanel.sortUpdatedAt)}
              </button>
              <button
                type="button"
                className="chip-filter"
                data-active={sortBy === "created_at"}
                style={{ fontSize: 11, padding: "2px 8px" }}
                onClick={() => setSortBy("created_at")}
              >
                {t(uiStrings.dataPanel.sortCreatedAt)}
              </button>
            </div>
            <div className="chip-filter-bar" style={{ gap: 4 }}>
              <button
                type="button"
                className="chip-filter"
                data-active={order === "desc"}
                style={{ fontSize: 11, padding: "2px 8px" }}
                onClick={() => setOrder("desc")}
              >
                {t(uiStrings.dataPanel.sortDesc)}
              </button>
              <button
                type="button"
                className="chip-filter"
                data-active={order === "asc"}
                style={{ fontSize: 11, padding: "2px 8px" }}
                onClick={() => setOrder("asc")}
              >
                {t(uiStrings.dataPanel.sortAsc)}
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Notes list */}
      <div className="control-panel-card">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
          <span className="muted" style={{ fontSize: 11 }}>
            {ti(uiStrings.dataPanel.noteCount, { n: notes.length })}
          </span>
          {notes.length > 0 && (
            <button
              className="btn btn-ghost btn-sm"
              type="button"
              style={{ fontSize: 11 }}
              onClick={toggleSelectAll}
            >
              {selectedIds.size === notes.length
                ? t(uiStrings.dataPanel.deselectAll)
                : t(uiStrings.dataPanel.selectAll)}
            </button>
          )}
        </div>

        <div
          className="control-panel-card-body"
          style={{ maxHeight: 300, overflow: "auto", padding: 0 }}
        >
          {notesQuery.isLoading ? (
            <div style={{ padding: 16, textAlign: "center" }}>
              <span className="muted">{t(uiStrings.common.loading)}</span>
            </div>
          ) : notes.length === 0 ? (
            <div style={{ padding: 16, textAlign: "center" }}>
              <span className="muted">{t(uiStrings.dataPanel.noNotes)}</span>
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
              {notes.map((note) => (
                <label
                  key={note.note_id}
                  style={{
                    display: "flex",
                    gap: 10,
                    padding: "8px 10px",
                    borderRadius: 8,
                    cursor: "pointer",
                    background: selectedIds.has(note.note_id)
                      ? "hsl(var(--accent))"
                      : "transparent",
                    transition: "background 0.15s",
                  }}
                >
                  <input
                    type="checkbox"
                    checked={selectedIds.has(note.note_id)}
                    onChange={() => toggleSelect(note.note_id)}
                    style={{ marginTop: 2, accentColor: "hsl(var(--ring))" }}
                  />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontWeight: 500, fontSize: 13, lineHeight: 1.4 }}>
                      {note.title || t(uiStrings.notes.untitled)}
                    </div>
                    <div style={{ display: "flex", gap: 4, flexWrap: "wrap", marginTop: 4 }}>
                      {note.document_ids.map((docId) => (
                        <span
                          key={docId}
                          className="chip"
                          style={{ fontSize: 10 }}
                        >
                          {documentTitleMap.get(docId) ?? docId.slice(0, 8)}
                        </span>
                      ))}
                    </div>
                    <span className="muted" style={{ fontSize: 10 }}>
                      {formatTimestamp(
                        sortBy === "created_at" ? note.created_at : note.updated_at,
                        locale,
                      )}
                    </span>
                  </div>
                  <button
                    className="btn btn-ghost btn-sm"
                    type="button"
                    style={{ alignSelf: "center", fontSize: 11, whiteSpace: "nowrap" }}
                    onClick={(e) => {
                      e.preventDefault();
                      void exportSingleNote(note);
                    }}
                  >
                    .md
                  </button>
                </label>
              ))}
            </div>
          )}
        </div>

        {/* Export action bar */}
        {notes.length > 0 && (
          <div
            style={{
              display: "flex",
              gap: 8,
              justifyContent: "flex-end",
              marginTop: 10,
              paddingTop: 10,
              borderTop: "1px solid hsl(var(--border))",
            }}
          >
            <button
              className="btn btn-sm"
              type="button"
              disabled={selectedIds.size === 0 || exporting}
              onClick={handleExportSelected}
            >
              {exporting
                ? t(uiStrings.dataPanel.exporting)
                : ti(uiStrings.dataPanel.exportSelected, { n: selectedIds.size })}
            </button>
            <button
              className="btn btn-sm"
              type="button"
              disabled={exporting}
              onClick={handleExportAll}
            >
              {exporting
                ? t(uiStrings.dataPanel.exporting)
                : t(uiStrings.dataPanel.exportAll)}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
