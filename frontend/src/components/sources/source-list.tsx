"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";

import {
  addDocumentsToNotebook,
  listDocumentsInNotebook,
  removeDocumentFromNotebook,
} from "@/lib/api/documents";
import { listLibraryDocuments } from "@/lib/api/library";
import { NotebookDocumentItem } from "@/lib/api/types";
import { SourceCard } from "@/components/sources/source-card";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";

type SourceListProps = {
  notebookId: string;
  onOpenDocument: (documentId: string) => void;
  onDocumentsUpdate?: (documents: NotebookDocumentItem[]) => void;
};

function isNonTerminalStatus(status: string) {
  return status === "uploaded" || status === "pending" || status === "processing" || status === "converted";
}

export function SourceList({ notebookId, onOpenDocument, onDocumentsUpdate }: SourceListProps) {
  const queryClient = useQueryClient();
  const [selectedLibraryIds, setSelectedLibraryIds] = useState<string[]>([]);
  const [showLibrary, setShowLibrary] = useState(false);
  const [pendingRemoveDocument, setPendingRemoveDocument] = useState<NotebookDocumentItem | null>(null);

  const notebookDocumentsQuery = useQuery({
    queryKey: ["notebook-documents", notebookId],
    queryFn: () => listDocumentsInNotebook(notebookId, { limit: 100, offset: 0 }),
    refetchInterval: (query) => {
      const rows = query.state.data?.data || [];
      return rows.some((row) => isNonTerminalStatus(row.status)) ? 3000 : false;
    },
  });

  const libraryDocumentsQuery = useQuery({
    queryKey: ["library-documents"],
    queryFn: () => listLibraryDocuments({ limit: 100, offset: 0 }),
    enabled: showLibrary,
  });

  const documentRows = useMemo(
    () => notebookDocumentsQuery.data?.data ?? [],
    [notebookDocumentsQuery.data?.data]
  );

  const onDocumentsUpdateRef = useRef(onDocumentsUpdate);
  onDocumentsUpdateRef.current = onDocumentsUpdate;

  useEffect(() => {
    onDocumentsUpdateRef.current?.(documentRows);
  }, [documentRows]);

  const notebookDocumentIdSet = useMemo(
    () => new Set(documentRows.map((item) => item.document_id)),
    [documentRows]
  );

  const addMutation = useMutation({
    mutationFn: (documentIds: string[]) => addDocumentsToNotebook(notebookId, documentIds),
    onSuccess: () => {
      setSelectedLibraryIds([]);
      setShowLibrary(false);
      queryClient.invalidateQueries({ queryKey: ["notebook-documents", notebookId] });
      queryClient.invalidateQueries({ queryKey: ["library-documents"] });
    },
  });

  const removeMutation = useMutation({
    mutationFn: (documentId: string) => removeDocumentFromNotebook(notebookId, documentId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["notebook-documents", notebookId] });
    },
  });

  return (
    <div className="stack-md" style={{ height: "100%" }}>
      {/* Header row */}
      <div className="row-between">
        <span style={{ fontSize: 13, fontWeight: 600 }}>
          Notebook Sources
          {documentRows.length > 0 && (
            <span className="muted" style={{ fontWeight: 400, marginLeft: 6 }}>
              ({documentRows.length})
            </span>
          )}
        </span>
        <div className="row" style={{ gap: 4 }}>
          <button
            className="btn btn-sm"
            type="button"
            onClick={() => setShowLibrary(!showLibrary)}
          >
            + 添加
          </button>
          <button
            className="btn btn-ghost btn-sm"
            type="button"
            onClick={() => notebookDocumentsQuery.refetch()}
          >
            刷新
          </button>
        </div>
      </div>

      {/* Library selector (collapsible) */}
      {showLibrary && (
        <div
          className="card"
          style={{ padding: 12 }}
        >
          <div className="stack-sm">
            <div className="row-between">
              <span style={{ fontSize: 12, fontWeight: 600 }}>从 Library 添加</span>
              <div className="row" style={{ gap: 4 }}>
                <button
                  className="btn btn-primary btn-sm"
                  type="button"
                  disabled={selectedLibraryIds.length === 0 || addMutation.isPending}
                  onClick={() => addMutation.mutate(selectedLibraryIds)}
                >
                  添加 ({selectedLibraryIds.length})
                </button>
                <button
                  className="btn btn-ghost btn-sm"
                  type="button"
                  onClick={() => {
                    setShowLibrary(false);
                    setSelectedLibraryIds([]);
                  }}
                >
                  取消
                </button>
              </div>
            </div>
            <ul className="list stack-sm" style={{ maxHeight: 200, overflow: "auto" }}>
              {(libraryDocumentsQuery.data?.data || []).map((row) => {
                const disabled = notebookDocumentIdSet.has(row.document_id);
                const checked = selectedLibraryIds.includes(row.document_id);
                return (
                  <li key={row.document_id} className="list-item" style={{ padding: 8 }}>
                    <label
                      className="row"
                      style={{
                        cursor: disabled ? "not-allowed" : "pointer",
                        opacity: disabled ? 0.5 : 1,
                        justifyContent: "space-between",
                      }}
                    >
                      <span className="row" style={{ gap: 8, minWidth: 0 }}>
                        <input
                          type="checkbox"
                          disabled={disabled}
                          checked={checked}
                          onChange={(event) => {
                            if (event.target.checked) {
                              setSelectedLibraryIds((prev) => [...prev, row.document_id]);
                            } else {
                              setSelectedLibraryIds((prev) => prev.filter((item) => item !== row.document_id));
                            }
                          }}
                        />
                        <span
                          style={{
                            fontSize: 13,
                            overflow: "hidden",
                            textOverflow: "ellipsis",
                            whiteSpace: "nowrap",
                          }}
                        >
                          {row.title}
                        </span>
                      </span>
                      <span className="badge badge-default" style={{ flexShrink: 0 }}>
                        {row.status}
                      </span>
                    </label>
                  </li>
                );
              })}
            </ul>
          </div>
        </div>
      )}

      {/* Document list */}
      {notebookDocumentsQuery.isLoading ? (
        <div className="stack-sm">
          {[1, 2].map((i) => (
            <div key={i} className="skeleton" style={{ height: 60 }} />
          ))}
        </div>
      ) : documentRows.length === 0 ? (
        <div className="empty-state" style={{ padding: "32px 16px" }}>
          <span>当前 Notebook 还没有文档</span>
          <button className="btn btn-sm" type="button" onClick={() => setShowLibrary(true)}>
            + 从 Library 添加
          </button>
        </div>
      ) : (
        <ul className="list stack-sm" style={{ flex: 1, overflow: "auto" }}>
          {documentRows.map((document) => (
            <SourceCard
              key={document.document_id}
              document={document}
              onView={onOpenDocument}
              onRemove={(doc) => setPendingRemoveDocument(doc)}
            />
          ))}
        </ul>
      )}

      <ConfirmDialog
        open={Boolean(pendingRemoveDocument)}
        title="移除文档"
        message={
          pendingRemoveDocument
            ? `确定要从当前 Notebook 中移除「${pendingRemoveDocument.title}」吗？\n文档本身不会被删除，可以稍后重新添加。`
            : ""
        }
        variant="warning"
        confirmLabel="确认移除"
        confirmDisabled={removeMutation.isPending}
        onCancel={() => setPendingRemoveDocument(null)}
        onConfirm={() => {
          if (!pendingRemoveDocument) return;
          removeMutation.mutate(pendingRemoveDocument.document_id);
          setPendingRemoveDocument(null);
        }}
      />
    </div>
  );
}
