"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import { listDocumentsInNotebook } from "@/lib/api/documents";
import type { NotebookDocumentItem } from "@/lib/api/types";
import { zh, uiStrings } from "@/lib/i18n/strings";

type SourceSelectorProps = {
  notebookId: string;
  selectedIds: string[] | null;
  onChange: (ids: string[] | null) => void;
  disabled?: boolean;
  onDocsChange?: (items: NotebookDocumentItem[], total: number) => void;
};

function SourceIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <path
        d="M3.5 2.5H9.5L12.5 5.5V13.5H3.5V2.5Z"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinejoin="round"
      />
      <path d="M9.5 2.5V5.5H12.5" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round" />
      <path d="M5.5 8H10.5M5.5 10.5H9.5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
    </svg>
  );
}

export function SourceSelector({
  notebookId,
  selectedIds,
  onChange,
  disabled = false,
  onDocsChange,
}: SourceSelectorProps) {
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<NotebookDocumentItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const hasLoadedRef = useRef(false);
  const requestSeqRef = useRef(0);
  const rootRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    onDocsChange?.(items, total);
  }, [items, total, onDocsChange]);

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (event: PointerEvent) => {
      const target = event.target as Node | null;
      if (!target) return;
      if (rootRef.current?.contains(target)) return;
      setOpen(false);
    };
    window.addEventListener("pointerdown", onPointerDown);
    return () => window.removeEventListener("pointerdown", onPointerDown);
  }, [open]);

  const loadDocuments = async () => {
    const reqId = ++requestSeqRef.current;
    setLoading(true);
    setError(null);
    try {
      const res = await listDocumentsInNotebook(notebookId, {
        status: "completed",
        limit: 100,
        offset: 0,
      });
      if (requestSeqRef.current !== reqId) return;
      setItems(res.data);
      setTotal(res.pagination.total);
      hasLoadedRef.current = true;
    } catch (err) {
      if (requestSeqRef.current !== reqId) return;
      setError(err instanceof Error ? err.message : zh(uiStrings.sourceSelector.loadFailed));
    } finally {
      if (requestSeqRef.current === reqId) {
        setLoading(false);
      }
    }
  };

  const visibleIds = useMemo(() => items.map((item) => item.document_id), [items]);
  const visibleIdSet = useMemo(() => new Set(visibleIds), [visibleIds]);
  const selectedVisibleIds = useMemo(() => {
    if (selectedIds === null) return visibleIds;
    return visibleIds.filter((id) => selectedIds.includes(id));
  }, [selectedIds, visibleIds]);

  const onToggleAll = () => {
    onChange(selectedIds === null ? [] : null);
  };

  const onToggleOne = (documentId: string) => {
    const nextSet = new Set(selectedIds === null ? visibleIds : selectedIds.filter((id) => visibleIdSet.has(id)));
    if (nextSet.has(documentId)) {
      nextSet.delete(documentId);
    } else {
      nextSet.add(documentId);
    }
    const ordered = visibleIds.filter((id) => nextSet.has(id));
    if (ordered.length === 0) {
      onChange([]);
      return;
    }
    if (total > 0 && total <= items.length && ordered.length === total) {
      onChange(null);
      return;
    }
    onChange(ordered);
  };

  const triggerLooksDisabled = disabled || (hasLoadedRef.current && !loading && !error && items.length === 0);

  return (
    <div className="source-selector" ref={rootRef}>
      <button
        type="button"
        className={`source-selector-trigger${triggerLooksDisabled ? " is-disabled" : ""}`}
        aria-label={zh(uiStrings.sourceSelector.open)}
        title={zh(uiStrings.sourceSelector.open)}
        aria-expanded={open}
        onClick={async () => {
          if (disabled) return;
          const nextOpen = !open;
          setOpen(nextOpen);
          if (nextOpen && !hasLoadedRef.current && !loading) {
            await loadDocuments();
          }
        }}
      >
        <SourceIcon />
      </button>

      <div className={`source-selector-panel${open ? " is-open" : ""}`} aria-hidden={!open}>
        <div className="source-selector-panel-header">
          <strong>{zh(uiStrings.sourceSelector.open)}</strong>
          <button className="btn btn-sm btn-ghost" type="button" onClick={() => setOpen(false)}>
            {zh(uiStrings.sourceSelector.done)}
          </button>
        </div>

        <div className="source-selector-panel-body">
          <button
            type="button"
            className="source-selector-row source-selector-row-all"
            onClick={onToggleAll}
            disabled={loading}
          >
            <input type="checkbox" readOnly checked={selectedIds === null} tabIndex={-1} />
            <span>{zh(uiStrings.sourceSelector.allDocuments)}</span>
          </button>

          <div className="source-selector-divider" />

          {loading ? (
            <div className="source-selector-empty">{zh(uiStrings.sourceSelector.loading)}</div>
          ) : error ? (
            <div className="source-selector-empty">
              <span>{zh(uiStrings.sourceSelector.loadFailed)}</span>
              <button className="btn btn-sm" type="button" onClick={() => void loadDocuments()}>
                {zh(uiStrings.sourceSelector.retry)}
              </button>
            </div>
          ) : items.length === 0 ? (
            <div className="source-selector-empty">{zh(uiStrings.sourceSelector.noDocuments)}</div>
          ) : (
            <>
              <div className="source-selector-list">
                {items.map((item) => {
                  const checked = selectedIds === null || selectedVisibleIds.includes(item.document_id);
                  return (
                    <button
                      key={item.document_id}
                      type="button"
                      className="source-selector-row"
                      onClick={() => onToggleOne(item.document_id)}
                    >
                      <input type="checkbox" readOnly checked={checked} tabIndex={-1} />
                      <span className="source-selector-row-title" title={item.title}>
                        {item.title}
                      </span>
                    </button>
                  );
                })}
              </div>
              {total > items.length && (
                <div className="source-selector-footer-hint">
                  {`共 ${total} 个文档，${zh(uiStrings.sourceSelector.firstNHint)} ${items.length} 个`}
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
