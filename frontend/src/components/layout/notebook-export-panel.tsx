"use client";

import { useQuery } from "@tanstack/react-query";
import { saveAs } from "file-saver";
import { usePathname } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

import { exportNotebook, listAllNotebooks } from "@/lib/api/notebooks";
import type { Notebook } from "@/lib/api/types";
import { useLang } from "@/lib/hooks/useLang";
import { uiStrings } from "@/lib/i18n/strings";

type ExportType = "documents" | "notes" | "marks" | "diagrams" | "video_summaries";

const EXPORT_TYPE_OPTIONS: Array<{ key: ExportType; labelKey: keyof typeof uiStrings.dataPanel }> = [
  { key: "documents", labelKey: "documents" },
  { key: "notes", labelKey: "notes" },
  { key: "marks", labelKey: "marks" },
  { key: "diagrams", labelKey: "diagrams" },
  { key: "video_summaries", labelKey: "videoSummaries" },
];
const EXPORT_FEEDBACK_TTL_MS = 5_000;

function sanitizeFilename(name: string): string {
  return name.replace(/[<>:"/\\|?*]/g, "_").trim() || "notebook";
}

function parseNotebookIdFromPathname(pathname: string): string | null {
  const match = pathname.match(/^\/notebooks\/([^/]+)$/);
  return match?.[1] ?? null;
}

function formatErrorMessage(error: unknown): string {
  if (error instanceof Error) return error.message;
  return String(error ?? "Unknown error");
}

type FailedExportItem = {
  notebookId: string;
  title: string;
  reason: string;
};

export function NotebookExportPanel() {
  const { t, ti } = useLang();
  const pathname = usePathname();
  const currentNotebookId = useMemo(
    () => parseNotebookIdFromPathname(pathname),
    [pathname]
  );

  const [keyword, setKeyword] = useState("");
  const [selectedNotebookIds, setSelectedNotebookIds] = useState<Set<string>>(
    () => (currentNotebookId ? new Set([currentNotebookId]) : new Set())
  );
  const [selectedTypes, setSelectedTypes] = useState<Set<ExportType>>(
    () => new Set(EXPORT_TYPE_OPTIONS.map((item) => item.key))
  );
  const [exporting, setExporting] = useState(false);
  const [exportProgress, setExportProgress] = useState<{ done: number; total: number }>({
    done: 0,
    total: 0,
  });
  const [failedExports, setFailedExports] = useState<FailedExportItem[]>([]);
  const [lastExportSuccessCount, setLastExportSuccessCount] = useState(0);

  const notebooksQuery = useQuery({
    queryKey: ["notebooks-all-for-export"],
    queryFn: () => listAllNotebooks(),
    staleTime: 60_000,
  });

  const notebooks = useMemo(
    () => notebooksQuery.data?.data ?? [],
    [notebooksQuery.data?.data]
  );

  useEffect(() => {
    if (!currentNotebookId) return;
    setSelectedNotebookIds((prev) => {
      if (prev.has(currentNotebookId)) return prev;
      if (prev.size > 0) return prev;
      return new Set([currentNotebookId]);
    });
  }, [currentNotebookId]);

  useEffect(() => {
    if (exporting || (lastExportSuccessCount === 0 && failedExports.length === 0)) return;
    const timeoutId = window.setTimeout(() => {
      setLastExportSuccessCount(0);
      setFailedExports([]);
    }, EXPORT_FEEDBACK_TTL_MS);
    return () => window.clearTimeout(timeoutId);
  }, [exporting, lastExportSuccessCount, failedExports]);

  const notebookMap = useMemo(
    () => new Map(notebooks.map((item) => [item.notebook_id, item])),
    [notebooks]
  );

  const filteredNotebooks = useMemo(() => {
    const normalized = keyword.trim().toLowerCase();
    if (!normalized) return notebooks;
    return notebooks.filter((item) => {
      const haystack = `${item.title} ${item.description ?? ""} ${item.notebook_id}`.toLowerCase();
      return haystack.includes(normalized);
    });
  }, [notebooks, keyword]);

  const isAllFilteredSelected =
    filteredNotebooks.length > 0 &&
    filteredNotebooks.every((item) => selectedNotebookIds.has(item.notebook_id));

  const toggleNotebook = useCallback((notebookId: string) => {
    setSelectedNotebookIds((prev) => {
      const next = new Set(prev);
      if (next.has(notebookId)) {
        next.delete(notebookId);
      } else {
        next.add(notebookId);
      }
      return next;
    });
  }, []);

  const toggleSelectAllFiltered = useCallback(() => {
    setSelectedNotebookIds((prev) => {
      const next = new Set(prev);
      if (isAllFilteredSelected) {
        filteredNotebooks.forEach((item) => next.delete(item.notebook_id));
      } else {
        filteredNotebooks.forEach((item) => next.add(item.notebook_id));
      }
      return next;
    });
  }, [filteredNotebooks, isAllFilteredSelected]);

  const toggleType = useCallback((type: ExportType) => {
    setSelectedTypes((prev) => {
      const next = new Set(prev);
      if (next.has(type)) {
        next.delete(type);
      } else {
        next.add(type);
      }
      return next;
    });
  }, []);

  const exportTypeList = useMemo(
    () => EXPORT_TYPE_OPTIONS.map((option) => option.key).filter((key) => selectedTypes.has(key)),
    [selectedTypes]
  );

  const exportDisabled =
    exporting || selectedNotebookIds.size === 0 || selectedTypes.size === 0;

  const handleExportSelected = useCallback(async () => {
    if (exportDisabled) return;

    const notebookIds = Array.from(selectedNotebookIds);
    setExporting(true);
    setFailedExports([]);
    setLastExportSuccessCount(0);
    setExportProgress({ done: 0, total: notebookIds.length });

    const failures: FailedExportItem[] = [];
    let successCount = 0;

    for (let index = 0; index < notebookIds.length; index += 1) {
      const notebookId = notebookIds[index];
      const notebook = notebookMap.get(notebookId);

      try {
        const result = await exportNotebook(notebookId, exportTypeList);
        const fallbackTitle = sanitizeFilename(notebook?.title ?? notebookId);
        const fallbackFilename = `${fallbackTitle}-export-${new Date().toISOString().slice(0, 10)}.zip`;
        saveAs(result.blob, result.filename || fallbackFilename);
        successCount += 1;
      } catch (error) {
        failures.push({
          notebookId,
          title: notebook?.title ?? notebookId,
          reason: formatErrorMessage(error),
        });
      } finally {
        setExportProgress({ done: index + 1, total: notebookIds.length });
      }
    }

    setFailedExports(failures);
    setLastExportSuccessCount(successCount);
    setExporting(false);
  }, [exportDisabled, selectedNotebookIds, notebookMap, exportTypeList]);

  return (
    <div className="control-panel-stack">
      <div className="control-panel-card">
        <div className="control-panel-card-title">
          {t(uiStrings.dataPanel.notebookExport)}
        </div>
        <div className="control-panel-card-hint">
          {t(uiStrings.dataPanel.notebookExportDesc)}
        </div>

        <div className="control-panel-card-body" style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          <input
            className="input"
            placeholder={t(uiStrings.dataPanel.searchNotebook)}
            value={keyword}
            onChange={(event) => setKeyword(event.target.value)}
            aria-label={t(uiStrings.dataPanel.searchNotebook)}
          />

          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8 }}>
            <span className="muted" style={{ fontSize: 12 }}>
              {ti(uiStrings.dataPanel.selectedNotebookCount, { n: selectedNotebookIds.size })}
            </span>
            <button
              className="btn btn-ghost btn-sm"
              type="button"
              onClick={toggleSelectAllFiltered}
              disabled={filteredNotebooks.length === 0}
            >
              {isAllFilteredSelected
                ? t(uiStrings.dataPanel.deselectAll)
                : t(uiStrings.dataPanel.selectAll)}
            </button>
          </div>

          <div
            style={{
              maxHeight: 220,
              overflowY: "auto",
              border: "1px solid hsl(var(--border) / 0.7)",
              borderRadius: 8,
              padding: 4,
              background: "hsl(var(--card))",
            }}
          >
            {notebooksQuery.isLoading ? (
              <div style={{ padding: 12 }}>
                <span className="muted">{t(uiStrings.common.loading)}</span>
              </div>
            ) : filteredNotebooks.length === 0 ? (
              <div style={{ padding: 12 }}>
                <span className="muted">{t(uiStrings.dataPanel.noNotebooks)}</span>
              </div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
                {filteredNotebooks.map((notebook) => {
                  const checked = selectedNotebookIds.has(notebook.notebook_id);
                  const isCurrent = notebook.notebook_id === currentNotebookId;
                  return (
                    <label
                      key={notebook.notebook_id}
                      style={{
                        display: "flex",
                        gap: 10,
                        alignItems: "flex-start",
                        padding: "8px 10px",
                        borderRadius: 8,
                        cursor: "pointer",
                        background: checked ? "hsl(var(--accent))" : "transparent",
                      }}
                    >
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={() => toggleNotebook(notebook.notebook_id)}
                        aria-label={notebook.title}
                        style={{ marginTop: 2, accentColor: "hsl(var(--ring))" }}
                      />
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                          <span style={{ fontSize: 13, fontWeight: 600, lineHeight: 1.4 }}>
                            {notebook.title}
                          </span>
                          {isCurrent && (
                            <span className="chip" style={{ fontSize: 10 }}>
                              {t(uiStrings.dataPanel.currentNotebook)}
                            </span>
                          )}
                        </div>
                        {notebook.description ? (
                          <div className="muted" style={{ fontSize: 11, marginTop: 2 }}>
                            {notebook.description}
                          </div>
                        ) : null}
                      </div>
                    </label>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="control-panel-card">
        <div className="control-panel-card-title">{t(uiStrings.dataPanel.contentTypes)}</div>
        <div className="control-panel-card-body" style={{ marginTop: 10, display: "flex", flexDirection: "column", gap: 8 }}>
          {EXPORT_TYPE_OPTIONS.map((option) => (
            <label key={option.key} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12 }}>
              <input
                type="checkbox"
                checked={selectedTypes.has(option.key)}
                onChange={() => toggleType(option.key)}
                aria-label={t(uiStrings.dataPanel[option.labelKey])}
                style={{ accentColor: "hsl(var(--ring))" }}
              />
              <span>{t(uiStrings.dataPanel[option.labelKey])}</span>
            </label>
          ))}
          <div
            style={{
              marginTop: 4,
              paddingTop: 10,
              borderTop: "1px solid hsl(var(--border) / 0.7)",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              gap: 8,
            }}
          >
            <button
              className="btn btn-sm"
              type="button"
              disabled={exportDisabled}
              onClick={() => void handleExportSelected()}
            >
              {exporting ? t(uiStrings.dataPanel.exportArchiveLoading) : t(uiStrings.dataPanel.exportArchive)}
            </button>
            {exporting ? (
              <span className="muted" style={{ fontSize: 11 }}>
                {ti(uiStrings.dataPanel.exportProgress, {
                  done: exportProgress.done,
                  total: exportProgress.total,
                })}
              </span>
            ) : null}
          </div>
        </div>

        {!exporting && lastExportSuccessCount > 0 ? (
          <div className="control-panel-success" style={{ marginTop: 10 }}>
            {ti(uiStrings.dataPanel.exportSuccessCount, { n: lastExportSuccessCount })}
          </div>
        ) : null}

        {failedExports.length > 0 ? (
          <div className="control-panel-error" style={{ marginTop: 10 }}>
            <div style={{ fontWeight: 600, marginBottom: 6 }}>
              {t(uiStrings.dataPanel.exportFailedList)}
            </div>
            <ul style={{ margin: 0, paddingLeft: 16 }}>
              {failedExports.map((item) => (
                <li key={item.notebookId}>
                  {item.title}: {item.reason}
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </div>
    </div>
  );
}
