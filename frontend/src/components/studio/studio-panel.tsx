"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { listDocumentsInNotebook } from "@/lib/api/documents";
import { deleteMark, listMarksByNotebook } from "@/lib/api/marks";
import {
  addNoteDocument,
  createNote,
  deleteNote,
  getNote,
  listNotes,
  removeNoteDocument,
  updateNote,
} from "@/lib/api/notes";
import type { Mark, Note, NotebookDocumentItem } from "@/lib/api/types";
import { useLang } from "@/lib/hooks/useLang";
import { uiStrings } from "@/lib/i18n/strings";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { useStudioStore } from "@/stores/studio-store";

const NOTE_AUTOSAVE_DELAY_MS = 5_000;

type StudioPanelProps = {
  notebookId: string;
  onOpenDocument: (documentId: string, markId?: string | null) => void;
};

type SaveStatus = "saved" | "saving" | "unsaved";

function formatTimestamp(value: string, locale: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(locale, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function truncate(value: string, maxLength = 60): string {
  if (value.length <= maxLength) return value;
  return `${value.slice(0, maxLength - 1)}…`;
}

function groupMarksByDocument(marks: Mark[]): Map<string, Mark[]> {
  const groups = new Map<string, Mark[]>();
  marks.forEach((mark) => {
    const existing = groups.get(mark.document_id) ?? [];
    existing.push(mark);
    groups.set(mark.document_id, existing);
  });
  return groups;
}

export function StudioPanel({ notebookId, onOpenDocument }: StudioPanelProps) {
  const { t, ti, lang } = useLang();
  const queryClient = useQueryClient();
  const {
    studioView,
    activeNoteId,
    activeMarkId,
    noteDocFilter,
    markDocFilter,
    navigateTo,
    openNoteEditor,
    backToHome,
    backToList,
    setActiveMarkId,
    setNoteDocFilter,
    setMarkDocFilter,
  } = useStudioStore();
  const [marksExpanded, setMarksExpanded] = useState(false);
  const [draftTitle, setDraftTitle] = useState("");
  const [draftContent, setDraftContent] = useState("");
  const [saveStatus, setSaveStatus] = useState<SaveStatus>("saved");
  const [pendingDeleteNote, setPendingDeleteNote] = useState<Note | null>(null);
  const [selectedDocumentIdToAdd, setSelectedDocumentIdToAdd] = useState("");
  const [copiedMarkId, setCopiedMarkId] = useState<string | null>(null);
  const editorRef = useRef<HTMLTextAreaElement>(null);
  const saveTimerRef = useRef<number | null>(null);
  const hydratedNoteIdRef = useRef<string | null>(null);

  const documentsQuery = useQuery({
    queryKey: ["notebook-documents", notebookId],
    queryFn: () => listDocumentsInNotebook(notebookId, { limit: 100, offset: 0 }),
  });

  const notesQuery = useQuery({
    queryKey: ["notes", notebookId, noteDocFilter ?? "all"],
    queryFn: () => listNotes(notebookId, noteDocFilter ? { document_id: noteDocFilter } : undefined),
  });

  const marksQuery = useQuery({
    queryKey: ["marks", "notebook", notebookId, markDocFilter ?? "all"],
    queryFn: () => listMarksByNotebook(notebookId, markDocFilter ? { document_id: markDocFilter } : undefined),
  });

  const activeNoteQuery = useQuery({
    queryKey: ["note", activeNoteId],
    queryFn: () => getNote(activeNoteId!),
    enabled: Boolean(activeNoteId) && studioView === "note-detail",
  });

  const documents = useMemo(() => documentsQuery.data?.data ?? [], [documentsQuery.data?.data]);
  const notes = useMemo(() => notesQuery.data?.notes ?? [], [notesQuery.data?.notes]);
  const notebookMarks = useMemo(() => marksQuery.data?.marks ?? [], [marksQuery.data?.marks]);
  const activeNote = activeNoteQuery.data ?? null;
  const documentMap = useMemo(
    () => new Map(documents.map((item) => [item.document_id, item])),
    [documents]
  );
  const groupedMarks = useMemo(() => groupMarksByDocument(notebookMarks), [notebookMarks]);
  const locale = lang === "en" ? "en-US" : "zh-CN";

  const createNoteMutation = useMutation({
    mutationFn: () =>
      createNote({
        notebook_id: notebookId,
        title: "",
        content: "",
        document_ids: noteDocFilter ? [noteDocFilter] : [],
      }),
    onSuccess: (note) => {
      queryClient.setQueryData(["note", note.note_id], note);
      void queryClient.invalidateQueries({ queryKey: ["notes", notebookId] });
      openNoteEditor(note.note_id);
    },
  });

  const updateNoteMutation = useMutation({
    mutationFn: (input: { noteId: string; title: string; content: string }) =>
      updateNote(input.noteId, {
        title: input.title,
        content: input.content,
      }),
    onSuccess: (note) => {
      queryClient.setQueryData(["note", note.note_id], note);
      void queryClient.invalidateQueries({ queryKey: ["notes", notebookId] });
      setSaveStatus("saved");
    },
  });

  const deleteNoteMutation = useMutation({
    mutationFn: (noteId: string) => deleteNote(noteId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["notes", notebookId] });
      if (activeNoteId) {
        queryClient.removeQueries({ queryKey: ["note", activeNoteId] });
      }
      hydratedNoteIdRef.current = null;
      setPendingDeleteNote(null);
      backToList();
    },
  });

  const addNoteDocumentMutation = useMutation({
    mutationFn: (input: { noteId: string; documentId: string }) =>
      addNoteDocument(input.noteId, input.documentId),
    onSuccess: async () => {
      if (activeNoteId) {
        await queryClient.invalidateQueries({ queryKey: ["note", activeNoteId] });
      }
      await queryClient.invalidateQueries({ queryKey: ["notes", notebookId] });
      setSelectedDocumentIdToAdd("");
    },
  });

  const removeNoteDocumentMutation = useMutation({
    mutationFn: (input: { noteId: string; documentId: string }) =>
      removeNoteDocument(input.noteId, input.documentId),
    onSuccess: async () => {
      if (activeNoteId) {
        await queryClient.invalidateQueries({ queryKey: ["note", activeNoteId] });
      }
      await queryClient.invalidateQueries({ queryKey: ["notes", notebookId] });
    },
  });

  const deleteMarkMutation = useMutation({
    mutationFn: (markId: string) => deleteMark(markId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["marks", "notebook", notebookId] });
      void queryClient.invalidateQueries({ queryKey: ["marks", "document"] });
    },
  });

  const clearSaveTimer = useCallback(() => {
    if (saveTimerRef.current !== null) {
      window.clearTimeout(saveTimerRef.current);
      saveTimerRef.current = null;
    }
  }, []);

  const runSave = useCallback(async () => {
    if (!activeNoteId || !activeNote) return;
    clearSaveTimer();
    setSaveStatus("saving");
    await updateNoteMutation.mutateAsync({
      noteId: activeNoteId,
      title: draftTitle,
      content: draftContent,
    });
  }, [activeNote, activeNoteId, clearSaveTimer, draftContent, draftTitle, updateNoteMutation]);

  const scheduleSave = useCallback(() => {
    if (!activeNoteId) return;
    clearSaveTimer();
    saveTimerRef.current = window.setTimeout(() => {
      void runSave();
    }, NOTE_AUTOSAVE_DELAY_MS);
  }, [activeNoteId, clearSaveTimer, runSave]);

  useEffect(() => {
    if (!activeNote) return;
    if (hydratedNoteIdRef.current === activeNote.note_id) return;
    hydratedNoteIdRef.current = activeNote.note_id;
    setDraftTitle(activeNote.title);
    setDraftContent(activeNote.content);
    setSaveStatus("saved");
  }, [activeNote]);

  useEffect(() => {
    if (!activeMarkId) return;
    if (studioView === "home") {
      navigateTo("notes");
    }
    setMarksExpanded(true);
  }, [activeMarkId, navigateTo, studioView]);

  useEffect(() => {
    return () => {
      clearSaveTimer();
    };
  }, [clearSaveTimer]);

  useEffect(() => {
    if (!copiedMarkId) return;
    const timerId = window.setTimeout(() => setCopiedMarkId(null), 1500);
    return () => window.clearTimeout(timerId);
  }, [copiedMarkId]);

  const availableMarks = useMemo(() => {
    if (!activeNote) return notebookMarks;
    if (activeNote.document_ids.length === 0) return notebookMarks;
    const documentIdSet = new Set(activeNote.document_ids);
    return notebookMarks.filter((mark) => documentIdSet.has(mark.document_id));
  }, [activeNote, notebookMarks]);

  const availableDocumentsToAdd = useMemo(() => {
    if (!activeNote) return documents;
    const attached = new Set(activeNote.document_ids);
    return documents.filter((item) => !attached.has(item.document_id));
  }, [activeNote, documents]);

  const insertMarkReference = useCallback(
    (markId: string) => {
      const token = `[[mark:${markId}]]`;
      const textarea = editorRef.current;
      if (!textarea) {
        setDraftContent((prev) => `${prev}${prev ? "\n" : ""}${token}`);
        setSaveStatus("unsaved");
        scheduleSave();
        return;
      }

      const selectionStart = textarea.selectionStart ?? draftContent.length;
      const selectionEnd = textarea.selectionEnd ?? draftContent.length;
      const nextContent =
        draftContent.slice(0, selectionStart) + token + draftContent.slice(selectionEnd);
      setDraftContent(nextContent);
      setSaveStatus("unsaved");
      scheduleSave();

      const nextCursor = selectionStart + token.length;
      window.requestAnimationFrame(() => {
        textarea.focus();
        textarea.setSelectionRange(nextCursor, nextCursor);
      });
    },
    [draftContent, scheduleSave]
  );

  const renderHome = () => (
    <div style={{ padding: 16, display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
      <div className="card card-interactive" style={{ padding: 16, minHeight: 100 }} onClick={() => navigateTo("notes")}>
        <div className="stack-sm">
          <strong>{t(uiStrings.studio.notesAndMarks)}</strong>
          <span className="muted" style={{ fontSize: 12 }}>
            {t(uiStrings.studio.notesAndMarksDescription)}
          </span>
        </div>
      </div>
      <div className="card" style={{ padding: 16, minHeight: 100, opacity: 0.6 }}>
        <div className="stack-sm">
          <strong>{t(uiStrings.studio.mindMap)}</strong>
          <span className="muted" style={{ fontSize: 12 }}>
            {t(uiStrings.studio.mindMapDescription)}
          </span>
          <span className="badge badge-default" style={{ width: "fit-content" }}>
            {t(uiStrings.studio.comingSoon)}
          </span>
        </div>
      </div>
    </div>
  );

  const renderNotesList = () => (
    <div className="stack-md" style={{ height: "100%", padding: 16 }}>
      <div className="row-between" style={{ gap: 8, alignItems: "center" }}>
        <button className="btn btn-ghost btn-sm" type="button" onClick={backToHome}>
          {t(uiStrings.studio.backToStudio)}
        </button>
        <button
          className="btn btn-sm"
          type="button"
          onClick={() => {
            void createNoteMutation.mutateAsync();
          }}
        >
          {t(uiStrings.notes.createNote)}
        </button>
      </div>

      {/* ── Notes section ── */}
      <div className="stack-sm" style={{ flex: 1, minHeight: 0, overflow: "auto" }}>
        <div className="row-between">
          <strong>{t(uiStrings.notes.title)}</strong>
          <span className="muted" style={{ fontSize: 11 }}>
            {ti(uiStrings.notes.noteCount, { n: notes.length })}
          </span>
        </div>
        <div className="relative">
          <select
            className="w-full appearance-none rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--background))] px-3 py-1.5 pr-8 text-xs text-[hsl(var(--foreground))] transition-colors hover:border-[hsl(var(--ring))] focus:border-[hsl(var(--ring))] focus:outline-none"
            value={noteDocFilter ?? ""}
            onChange={(e) => setNoteDocFilter(e.target.value || null)}
          >
            <option value="">{t(uiStrings.studio.allFilter)}</option>
            {documents.map((doc) => (
              <option key={doc.document_id} value={doc.document_id}>
                {doc.title}
              </option>
            ))}
          </select>
          <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center pr-2 text-[hsl(var(--muted-foreground))]">
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none"><path d="M3 4.5L6 7.5L9 4.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg>
          </div>
        </div>
        {notes.length === 0 ? (
          <div className="empty-state" style={{ padding: "24px 12px" }}>
            <span>{t(uiStrings.notes.noNotes)}</span>
          </div>
        ) : (
          notes.map((note) => (
            <button
              key={note.note_id}
              type="button"
              className="list-item"
              style={{ width: "100%", textAlign: "left", padding: 12 }}
              onClick={() => openNoteEditor(note.note_id)}
            >
              <div className="stack-sm" style={{ width: "100%" }}>
                <strong>{note.title || t(uiStrings.notes.untitled)}</strong>
                <div className="row" style={{ flexWrap: "wrap", gap: 6 }}>
                  {note.document_ids.map((documentId) => (
                    <span key={documentId} className="chip">
                      {documentMap.get(documentId)?.title ?? documentId}
                    </span>
                  ))}
                </div>
                <span className="muted" style={{ fontSize: 11 }}>
                  {ti(uiStrings.notes.updatedAt, {
                    date: formatTimestamp(note.updated_at, locale),
                  })}
                </span>
              </div>
            </button>
          ))
        )}
      </div>

      {/* ── Marks section ── */}
      <div className="card" style={{ padding: 12 }}>
        <button
          className="row-between"
          type="button"
          style={{ width: "100%", background: "transparent", border: 0, padding: 0, cursor: "pointer" }}
          onClick={() => setMarksExpanded((prev) => !prev)}
        >
          <strong>{t(uiStrings.marks.title)}</strong>
          <span className="muted" style={{ fontSize: 11 }}>
            {ti(uiStrings.marks.markCount, { n: notebookMarks.length })}
          </span>
        </button>
        {marksExpanded ? (
          <div className="stack-sm" style={{ marginTop: 12, maxHeight: 280, overflow: "auto" }}>
            <div className="chip-filter-bar">
              <button
                type="button"
                className="chip-filter"
                data-active={markDocFilter === null}
                onClick={() => setMarkDocFilter(null)}
              >
                {t(uiStrings.studio.allFilter)}
              </button>
              {documents.map((doc) => (
                <button
                  key={doc.document_id}
                  type="button"
                  className="chip-filter"
                  data-active={markDocFilter === doc.document_id}
                  onClick={() => setMarkDocFilter(markDocFilter === doc.document_id ? null : doc.document_id)}
                  title={doc.title}
                >
                  {truncate(doc.title, 18)}
                </button>
              ))}
            </div>
            {groupedMarks.size === 0 ? (
              <div className="empty-state" style={{ padding: "16px 12px" }}>
                <span>{t(uiStrings.marks.noMarks)}</span>
              </div>
            ) : (
              Array.from(groupedMarks.entries()).map(([documentId, marks]) => (
                <div key={documentId} className="stack-sm">
                  <strong style={{ fontSize: 12 }}>
                    {documentMap.get(documentId)?.title ?? documentId}
                  </strong>
                  {marks.map((mark) => (
                    <div
                      key={mark.mark_id}
                      className="list-item"
                      style={{
                        padding: 10,
                        borderColor:
                          activeMarkId === mark.mark_id ? "hsl(var(--ring))" : "hsl(var(--border))",
                      }}
                    >
                      <button
                        type="button"
                        style={{ width: "100%", border: 0, background: "transparent", padding: 0, textAlign: "left", cursor: "pointer" }}
                        onClick={() => {
                          setActiveMarkId(mark.mark_id);
                          onOpenDocument(mark.document_id, mark.mark_id);
                        }}
                      >
                        <div className="stack-sm">
                          <span>{truncate(mark.anchor_text)}</span>
                          <span className="muted" style={{ fontSize: 11 }}>
                            {ti(uiStrings.marks.fromDocument, {
                              title: documentMap.get(mark.document_id)?.title ?? mark.document_id,
                            })}
                          </span>
                        </div>
                      </button>
                      <div className="row" style={{ justifyContent: "flex-end", marginTop: 8, gap: 4 }}>
                        <button
                          className="btn btn-ghost btn-sm"
                          type="button"
                          onClick={async () => {
                            await navigator.clipboard.writeText(`[[mark:${mark.mark_id}]]`);
                            setCopiedMarkId(mark.mark_id);
                          }}
                        >
                          {copiedMarkId === mark.mark_id
                            ? t(uiStrings.marks.referenceCopied)
                            : t(uiStrings.marks.copyReference)}
                        </button>
                        <button
                          className="btn btn-danger-ghost btn-sm"
                          type="button"
                          disabled={deleteMarkMutation.isPending}
                          onClick={() => {
                            void deleteMarkMutation.mutateAsync(mark.mark_id);
                          }}
                        >
                          {t(uiStrings.marks.deleteMark)}
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              ))
            )}
          </div>
        ) : null}
      </div>
    </div>
  );

  const renderNoteDetail = () => {
    if (!activeNote) {
      return (
        <div className="empty-state" style={{ padding: 24 }}>
          <span>{t(uiStrings.common.loading)}</span>
        </div>
      );
    }

    return (
      <div className="stack-md" style={{ height: "100%", padding: 16 }}>
        <div className="row-between" style={{ gap: 8 }}>
          <button
            className="btn btn-ghost btn-sm"
            type="button"
            onClick={() => {
              void runSave().finally(() => backToList());
            }}
          >
            {t(uiStrings.studio.backToList)}
          </button>
          <button
            className="btn btn-danger-ghost btn-sm"
            type="button"
            onClick={() => setPendingDeleteNote(activeNote)}
          >
            {t(uiStrings.notes.deleteNote)}
          </button>
        </div>

        <input
          className="input"
          placeholder={t(uiStrings.notes.titlePlaceholder)}
          value={draftTitle}
          onChange={(event) => {
            setDraftTitle(event.target.value);
            setSaveStatus("unsaved");
            scheduleSave();
          }}
          onBlur={() => {
            void runSave();
          }}
        />

        <div className="stack-sm">
          <strong style={{ fontSize: 12 }}>{t(uiStrings.notes.associatedDocs)}</strong>
          <div className="row" style={{ flexWrap: "wrap", gap: 6 }}>
            {activeNote.document_ids.map((documentId) => (
              <span key={documentId} className="chip">
                {documentMap.get(documentId)?.title ?? documentId}
                <button
                  type="button"
                  className="chat-input-source-chip-remove"
                  aria-label={ti(uiStrings.notes.removeDocConfirm, {
                    title: documentMap.get(documentId)?.title ?? documentId,
                  })}
                  onClick={() => {
                    void removeNoteDocumentMutation.mutateAsync({
                      noteId: activeNote.note_id,
                      documentId,
                    });
                  }}
                >
                  ×
                </button>
              </span>
            ))}
          </div>
          <div className="row" style={{ gap: 8 }}>
            <select
              className="select"
              value={selectedDocumentIdToAdd}
              onChange={(event) => setSelectedDocumentIdToAdd(event.target.value)}
            >
              <option value="">{t(uiStrings.notes.addDocument)}</option>
              {availableDocumentsToAdd.map((document) => (
                <option key={document.document_id} value={document.document_id}>
                  {document.title}
                </option>
              ))}
            </select>
            <button
              className="btn btn-sm"
              type="button"
              disabled={!selectedDocumentIdToAdd}
              onClick={() => {
                if (!selectedDocumentIdToAdd) return;
                void addNoteDocumentMutation.mutateAsync({
                  noteId: activeNote.note_id,
                  documentId: selectedDocumentIdToAdd,
                });
              }}
            >
              {t(uiStrings.notes.addDocument)}
            </button>
          </div>
        </div>

        <textarea
          ref={editorRef}
          className="textarea"
          style={{ minHeight: 220, fontFamily: "\"Cascadia Code\", monospace" }}
          placeholder={t(uiStrings.notes.notePlaceholder)}
          value={draftContent}
          onChange={(event) => {
            setDraftContent(event.target.value);
            setSaveStatus("unsaved");
            scheduleSave();
          }}
          onKeyDown={(event) => {
            if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "s") {
              event.preventDefault();
              void runSave();
            }
          }}
        />

        <div className="row-between" style={{ gap: 8 }}>
          <span className="muted" style={{ fontSize: 11 }}>
            {saveStatus === "saved"
              ? t(uiStrings.notes.saveSaved)
              : saveStatus === "saving"
                ? t(uiStrings.notes.saveSaving)
                : t(uiStrings.notes.saveUnsaved)}
          </span>
          <button className="btn btn-ghost btn-sm" type="button" onClick={() => void runSave()}>
            {t(uiStrings.common.confirm)}
          </button>
        </div>

        <div className="card" style={{ padding: 12, flex: 1, minHeight: 0, overflow: "auto" }}>
          <div className="row-between">
            <strong>{t(uiStrings.notes.availableMarks)}</strong>
            <span className="muted" style={{ fontSize: 11 }}>
              {ti(uiStrings.marks.markCount, { n: availableMarks.length })}
            </span>
          </div>
          {availableMarks.length === 0 ? (
            <div className="empty-state" style={{ padding: "20px 12px" }}>
              <span>{t(uiStrings.notes.noAvailableMarks)}</span>
            </div>
          ) : (
            <div className="stack-sm" style={{ marginTop: 12 }}>
              {availableMarks.map((mark) => (
                <div key={mark.mark_id} className="list-item" style={{ padding: 10 }}>
                  <div className="stack-sm">
                    <span>{truncate(mark.anchor_text)}</span>
                    <span className="muted" style={{ fontSize: 11 }}>
                      {ti(uiStrings.marks.fromDocument, {
                        title: documentMap.get(mark.document_id)?.title ?? mark.document_id,
                      })}
                    </span>
                  </div>
                  <div className="row" style={{ justifyContent: "flex-end", marginTop: 8 }}>
                    <button
                      className="btn btn-ghost btn-sm"
                      type="button"
                      onClick={() => insertMarkReference(mark.mark_id)}
                    >
                      {t(uiStrings.notes.insertMark)}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    );
  };

  return (
    <>
      {studioView === "home" ? renderHome() : null}
      {studioView === "notes" ? renderNotesList() : null}
      {studioView === "note-detail" ? renderNoteDetail() : null}

      <ConfirmDialog
        open={Boolean(pendingDeleteNote)}
        title={t(uiStrings.notes.deleteNote)}
        message={t(uiStrings.notes.deleteNoteConfirm)}
        variant="danger"
        confirmDisabled={deleteNoteMutation.isPending}
        onCancel={() => setPendingDeleteNote(null)}
        onConfirm={() => {
          if (!pendingDeleteNote) return;
          return deleteNoteMutation.mutateAsync(pendingDeleteNote.note_id);
        }}
      />
    </>
  );
}
