"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useMemo, useState } from "react";

import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { uploadDocumentsToLibrary } from "@/lib/api/documents";
import { deleteLibraryDocument, listLibraryDocuments } from "@/lib/api/library";
import { DocumentStatus } from "@/lib/api/types";

type StatusFilter = "all" | DocumentStatus;
type PendingDeleteAction =
  | { kind: "soft"; documentId: string; title: string }
  | { kind: "hard"; documentId: string; title: string }
  | { kind: "batch"; documentIds: string[]; count: number };

const STATUS_TABS: Array<{ value: StatusFilter; label: string }> = [
  { value: "all", label: "全部" },
  { value: "uploaded", label: "已上传" },
  { value: "processing", label: "处理中" },
  { value: "completed", label: "已完成" },
  { value: "failed", label: "失败" },
];

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

function statusLabel(status: string, stage?: string | null): string {
  const map: Record<string, string> = {
    uploaded: "已上传",
    pending: "等待处理",
    processing: stage ? stageLabel(stage) : "处理中...",
    converted: "已转换",
    completed: "已完成",
    failed: "处理失败",
  };
  return map[status] || status;
}

function stageLabel(stage: string): string {
  const map: Record<string, string> = {
    converting: "转换文档中...",
    splitting: "文本分块中...",
    indexing_pg: "构建向量索引...",
    indexing_es: "构建全文索引...",
    finalizing: "完成处理中...",
  };
  return map[stage] || stage;
}

function formatDate(dateString: string): string {
  return new Date(dateString).toLocaleDateString("zh-CN", {
    month: "short",
    day: "numeric",
  });
}

export default function LibraryPage() {
  const queryClient = useQueryClient();
  const [status, setStatus] = useState<StatusFilter>("all");
  const [pickedFiles, setPickedFiles] = useState<File[]>([]);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [pendingDeleteAction, setPendingDeleteAction] = useState<PendingDeleteAction | null>(null);

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
      ? "彻底删除文档"
      : pendingDeleteAction?.kind === "batch"
        ? "批量删除文档"
        : "删除文档";

  const confirmMessage = (() => {
    if (!pendingDeleteAction) return "";
    if (pendingDeleteAction.kind === "hard") {
      return `确定要彻底删除「${pendingDeleteAction.title}」吗？\n原始文件与索引数据都会被永久删除，此操作不可撤销。`;
    }
    if (pendingDeleteAction.kind === "batch") {
      return `确定要删除选中的 ${pendingDeleteAction.count} 个文档吗？\n本次执行的是软删除（保留原始文件）。`;
    }
    return `确定要删除「${pendingDeleteAction.title}」吗？\n将清除索引与数据库记录，但保留原始文件。`;
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
          <span className="muted">Library</span>
        </div>
        <Link href="/notebooks" className="btn btn-ghost">
          返回 Notebooks
        </Link>
      </header>

      <main className="page-main stack-md">
        {/* Title + Upload */}
        <div className="row-between">
          <h1 className="text-xl font-semibold tracking-tight" style={{ margin: 0 }}>
            Library 文档管理
          </h1>
          <label className="btn btn-primary" style={{ cursor: "pointer" }}>
            上传文档
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
            上传中...
          </div>
        )}

        {/* Tab filter */}
        <div className="tab-bar">
          {STATUS_TABS.map((tab) => (
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
              <span>暂无文档</span>
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
                  <th>文档标题</th>
                  <th style={{ width: 140 }}>状态</th>
                  <th style={{ width: 100 }}>上传时间</th>
                  <th style={{ width: 120 }}>操作</th>
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
                        {statusLabel(row.status, row.processing_stage)}
                      </span>
                    </td>
                    <td>
                      <span className="muted" style={{ fontSize: 12 }}>
                        {formatDate(row.created_at)}
                      </span>
                    </td>
                    <td>
                      <div className="row">
                        <button
                          className="btn btn-ghost btn-sm"
                          type="button"
                          style={{ color: "hsl(var(--destructive))" }}
                          onClick={() => {
                            setPendingDeleteAction({
                              kind: "soft",
                              documentId: row.document_id,
                              title: row.title,
                            });
                          }}
                        >
                          删除
                        </button>
                        <button
                          className="btn btn-ghost btn-sm"
                          type="button"
                          style={{ color: "hsl(var(--destructive))" }}
                          onClick={() => {
                            setPendingDeleteAction({
                              kind: "hard",
                              documentId: row.document_id,
                              title: row.title,
                            });
                          }}
                        >
                          彻底删除
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
              已选 {selectedIds.size} 个
            </span>
            <button
              className="btn btn-sm"
              type="button"
              style={{ color: "hsl(var(--destructive))" }}
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
              批量删除
            </button>
          </div>
        )}

        <ConfirmDialog
          open={Boolean(pendingDeleteAction)}
          title={confirmTitle}
          message={confirmMessage}
          variant={confirmVariant}
          confirmLabel={pendingDeleteAction?.kind === "hard" ? "确认彻底删除" : "确认删除"}
          confirmDisabled={deleteMutation.isPending}
          onCancel={() => setPendingDeleteAction(null)}
          onConfirm={handleConfirmDelete}
        />
      </main>
    </div>
  );
}
