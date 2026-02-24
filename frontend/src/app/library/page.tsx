"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useMemo, useState } from "react";

import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { uploadDocumentsToLibrary } from "@/lib/api/documents";
import { deleteLibraryDocument, listLibraryDocuments } from "@/lib/api/library";
import { useLang } from "@/lib/hooks/useLang";
import { uiStrings } from "@/lib/i18n/strings";
import { DocumentStatus } from "@/lib/api/types";

type StatusFilter = "all" | DocumentStatus;
type PendingDeleteAction =
  | { kind: "soft"; documentId: string; title: string }
  | { kind: "hard"; documentId: string; title: string }
  | { kind: "batch"; documentIds: string[]; count: number };

function statusBadgeClass(status: string): string {
  const map: Record<string, string> = {
    uploaded: "badge-default",
    pending: "badge-default",
    processing: "badge-processing",
    converted: "badge-converted",
    completed: "badge-completed",
    failed: "badge-failed",
  };
  return map[status] || "badge-default";
}

function statusLabel(
  status: string,
  stage: string | null | undefined,
  t: ReturnType<typeof useLang>["t"]
): string {
  const map: Record<string, string> = {
    uploaded: t(uiStrings.libraryPage.statusUploaded),
    pending: t(uiStrings.libraryPage.statusWaiting),
    processing: stage ? stageLabel(stage, t) : t(uiStrings.libraryPage.statusProcessing),
    converted: t(uiStrings.libraryPage.statusConverted),
    completed: t(uiStrings.libraryPage.statusCompleted),
    failed: t(uiStrings.libraryPage.statusFailed),
  };
  return map[status] || status;
}

function stageLabel(stage: string, t: ReturnType<typeof useLang>["t"]): string {
  const map: Record<string, string> = {
    converting: t(uiStrings.sourceCard.converting),
    splitting: t(uiStrings.sourceCard.splitting),
    indexing_pg: t(uiStrings.sourceCard.indexingPg),
    indexing_es: t(uiStrings.sourceCard.indexingEs),
    finalizing: t(uiStrings.sourceCard.finalizing),
  };
  return map[stage] || stage;
}

function formatDate(dateString: string, lang: "zh" | "en"): string {
  return new Date(dateString).toLocaleDateString(lang === "en" ? "en-US" : "zh-CN", {
    month: "short",
    day: "numeric",
  });
}

export default function LibraryPage() {
  const { lang, t, ti } = useLang();
  const queryClient = useQueryClient();
  const [status, setStatus] = useState<StatusFilter>("all");
  const [pickedFiles, setPickedFiles] = useState<File[]>([]);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [pendingDeleteAction, setPendingDeleteAction] = useState<PendingDeleteAction | null>(null);

  const statusTabs: Array<{ value: StatusFilter; label: string }> = [
    { value: "all", label: t(uiStrings.libraryPage.tabsAll) },
    { value: "uploaded", label: t(uiStrings.libraryPage.tabsUploaded) },
    { value: "processing", label: t(uiStrings.libraryPage.tabsProcessing) },
    { value: "completed", label: t(uiStrings.libraryPage.tabsCompleted) },
    { value: "failed", label: t(uiStrings.libraryPage.tabsFailed) },
  ];

  const libraryQuery = useQuery({
    queryKey: ["library-documents", status],
    queryFn: () =>
      listLibraryDocuments({
        limit: 100,
        offset: 0,
        status: status === "all" ? undefined : status,
      }),
  });

  const uploadMutation = useMutation({
    mutationFn: (files: File[]) => uploadDocumentsToLibrary(files),
    onSuccess: () => {
      setPickedFiles([]);
      queryClient.invalidateQueries({ queryKey: ["library-documents"] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: ({ documentId, force }: { documentId: string; force: boolean }) =>
      deleteLibraryDocument(documentId, force),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["library-documents"] });
    },
  });

  const rows = useMemo(() => libraryQuery.data?.data || [], [libraryQuery.data]);

  const toggleSelect = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleAll = () => {
    if (selectedIds.size === rows.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(rows.map((r) => r.document_id)));
    }
  };

  const confirmTitle =
    pendingDeleteAction?.kind === "hard"
      ? t(uiStrings.libraryPage.hardDeleteTitle)
      : pendingDeleteAction?.kind === "batch"
        ? t(uiStrings.libraryPage.batchDeleteTitle)
        : t(uiStrings.libraryPage.softDeleteTitle);

  const confirmMessage = (() => {
    if (!pendingDeleteAction) return "";
    if (pendingDeleteAction.kind === "hard") {
      return ti(uiStrings.libraryPage.hardDeleteConfirm, { title: pendingDeleteAction.title });
    }
    if (pendingDeleteAction.kind === "batch") {
      return ti(uiStrings.libraryPage.batchDeleteConfirm, { n: pendingDeleteAction.count });
    }
    return ti(uiStrings.libraryPage.softDeleteConfirm, { title: pendingDeleteAction.title });
  })();

  const confirmVariant = pendingDeleteAction?.kind === "soft" ? "warning" : "danger";

  const handleConfirmDelete = async () => {
    if (!pendingDeleteAction) return;

    if (pendingDeleteAction.kind === "hard") {
      await deleteMutation.mutateAsync({
        documentId: pendingDeleteAction.documentId,
        force: true,
      });
      setPendingDeleteAction(null);
      return;
    }

    if (pendingDeleteAction.kind === "soft") {
      await deleteMutation.mutateAsync({
        documentId: pendingDeleteAction.documentId,
        force: false,
      });
      setPendingDeleteAction(null);
      return;
    }

    for (const documentId of pendingDeleteAction.documentIds) {
      await deleteMutation.mutateAsync({ documentId, force: false });
    }
    setSelectedIds(new Set());
    setPendingDeleteAction(null);
  };

  return (
    <div className="page-shell">
      {/* Header */}
      <header className="page-header">
        <div className="row">
          <strong className="text-base tracking-tight">Newbee Notebook</strong>
          <span className="muted">/</span>
          <span className="muted">{t(uiStrings.libraryPage.breadcrumbLibrary)}</span>
        </div>
        <Link href="/notebooks" className="btn btn-ghost">
          {t(uiStrings.libraryPage.backToNotebooks)}
        </Link>
      </header>

      <main className="page-main stack-md">
        {/* Title + Upload */}
        <div className="row-between">
          <h1 className="text-xl font-semibold tracking-tight" style={{ margin: 0 }}>
            {t(uiStrings.libraryPage.title)}
          </h1>
          <label className="btn btn-primary" style={{ cursor: "pointer" }}>
            {t(uiStrings.libraryPage.uploadDocuments)}
            <input
              type="file"
              multiple
              style={{ display: "none" }}
              onChange={(e) => {
                const files = Array.from(e.target.files || []);
                if (files.length > 0) {
                  uploadMutation.mutate(files);
                }
                e.target.value = "";
              }}
            />
          </label>
        </div>

        {/* Upload pending indicator */}
        {uploadMutation.isPending && (
          <div className="badge badge-processing" style={{ alignSelf: "flex-start" }}>
            {t(uiStrings.common.uploadInProgress)}
          </div>
        )}

        {/* Tab filter */}
        <div className="tab-bar">
          {statusTabs.map((tab) => (
            <button
              key={tab.value}
              className={`tab-item ${status === tab.value ? "active" : ""}`}
              type="button"
              onClick={() => setStatus(tab.value)}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Data table */}
        <div className="panel" style={{ overflow: "hidden" }}>
          {libraryQuery.isLoading ? (
            <div className="panel-body">
              <div className="stack-sm">
                {[1, 2, 3].map((i) => (
                  <div key={i} className="skeleton" style={{ height: 40 }} />
                ))}
              </div>
            </div>
          ) : rows.length === 0 ? (
            <div className="empty-state">
              <span>{t(uiStrings.common.noDocuments)}</span>
            </div>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th style={{ width: 40 }}>
                    <input
                      type="checkbox"
                      checked={selectedIds.size === rows.length && rows.length > 0}
                      onChange={toggleAll}
                    />
                  </th>
                  <th>{t(uiStrings.libraryPage.tableTitle)}</th>
                  <th style={{ width: 140 }}>{t(uiStrings.libraryPage.tableStatus)}</th>
                  <th style={{ width: 100 }}>{t(uiStrings.libraryPage.tableUploadedAt)}</th>
                  <th style={{ width: 120 }}>{t(uiStrings.libraryPage.tableActions)}</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.document_id}>
                    <td>
                      <input
                        type="checkbox"
                        checked={selectedIds.has(row.document_id)}
                        onChange={() => toggleSelect(row.document_id)}
                      />
                    </td>
                    <td>
                      <strong style={{ fontSize: 13, fontWeight: 500 }}>{row.title}</strong>
                    </td>
                    <td>
                      <span className={`badge ${statusBadgeClass(row.status)}`}>
                        {statusLabel(row.status, row.processing_stage, t)}
                      </span>
                    </td>
                    <td>
                      <span className="muted" style={{ fontSize: 12 }}>
                        {formatDate(row.created_at, lang)}
                      </span>
                    </td>
                    <td>
                      <div className="row">
                        <button
                          className="btn btn-ghost btn-danger-ghost btn-sm"
                          type="button"
                          onClick={() => {
                            setPendingDeleteAction({
                              kind: "soft",
                              documentId: row.document_id,
                              title: row.title,
                            });
                          }}
                        >
                          {t(uiStrings.common.delete)}
                        </button>
                        <button
                          className="btn btn-ghost btn-danger-ghost btn-sm"
                          type="button"
                          onClick={() => {
                            setPendingDeleteAction({
                              kind: "hard",
                              documentId: row.document_id,
                              title: row.title,
                            });
                          }}
                        >
                          {t(uiStrings.libraryPage.hardDeleteLabel)}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* Batch operations */}
        {selectedIds.size > 0 && (
          <div className="row">
            <span className="muted" style={{ fontSize: 13 }}>
              {ti(uiStrings.libraryPage.selectedCount, { n: selectedIds.size })}
            </span>
            <button
              className="btn btn-danger-ghost btn-sm"
              type="button"
              onClick={() => {
                const documentIds = Array.from(selectedIds);
                if (documentIds.length === 0) return;
                setPendingDeleteAction({
                  kind: "batch",
                  documentIds,
                  count: documentIds.length,
                });
              }}
            >
              {t(uiStrings.libraryPage.batchDelete)}
            </button>
          </div>
        )}

        <ConfirmDialog
          open={Boolean(pendingDeleteAction)}
          title={confirmTitle}
          message={confirmMessage}
          variant={confirmVariant}
          confirmLabel={
            pendingDeleteAction?.kind === "hard"
              ? t(uiStrings.libraryPage.confirmHardDelete)
              : t(uiStrings.common.confirmDelete)
          }
          confirmDisabled={deleteMutation.isPending}
          onCancel={() => setPendingDeleteAction(null)}
          onConfirm={handleConfirmDelete}
        />
      </main>
    </div>
  );
}
