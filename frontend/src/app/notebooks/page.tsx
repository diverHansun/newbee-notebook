"use client";

import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { createNotebook, deleteNotebook, listNotebooks, updateNotebook } from "@/lib/api/notebooks";
import { NotebookContextMenu } from "@/components/notebooks/notebook-context-menu";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { useLang } from "@/lib/hooks/useLang";
import { uiStrings } from "@/lib/i18n/strings";

const PAGE_SIZE = 12;

function formatRelativeTime(
  dateString: string,
  lang: "zh" | "en",
  t: ReturnType<typeof useLang>["t"],
  ti: ReturnType<typeof useLang>["ti"]
): string {
  const now = Date.now();
  const then = new Date(dateString).getTime();
  const diff = now - then;
  const minutes = Math.floor(diff / 60000);
  if (minutes < 1) return t(uiStrings.notebooksPage.justNow);
  if (minutes < 60) return ti(uiStrings.notebooksPage.minutesAgo, { n: minutes });
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return ti(uiStrings.notebooksPage.hoursAgo, { n: hours });
  const days = Math.floor(hours / 24);
  if (days < 30) {
    return ti(days === 1 ? uiStrings.notebooksPage.daysAgo : uiStrings.notebooksPage.daysAgoPlural, {
      n: days,
    });
  }
  return new Date(dateString).toLocaleDateString(lang === "en" ? "en-US" : "zh-CN");
}

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

export default function NotebooksPage() {
  const { lang, t, ti } = useLang();
  const router = useRouter();
  const queryClient = useQueryClient();
  const [currentPage, setCurrentPage] = useState(1);
  const [showCreate, setShowCreate] = useState(false);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [pendingDeleteNotebook, setPendingDeleteNotebook] = useState<{
    notebookId: string;
    title: string;
  } | null>(null);
  const [contextMenu, setContextMenu] = useState<{
    notebookId: string;
    title: string;
    description: string | null;
    x: number;
    y: number;
  } | null>(null);
  const [editingNotebook, setEditingNotebook] = useState<{
    notebookId: string;
    title: string;
    description: string;
  } | null>(null);

  const notebooksQuery = useQuery({
    queryKey: ["notebooks", currentPage, PAGE_SIZE],
    queryFn: () => listNotebooks(PAGE_SIZE, (currentPage - 1) * PAGE_SIZE),
    placeholderData: keepPreviousData,
  });

  const createMutation = useMutation({
    mutationFn: () => createNotebook({ title, description }),
    onSuccess: (notebook) => {
      setTitle("");
      setDescription("");
      setShowCreate(false);
      queryClient.invalidateQueries({ queryKey: ["notebooks"] });
      router.push(`/notebooks/${notebook.notebook_id}`);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (notebookId: string) => deleteNotebook(notebookId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["notebooks"] });
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ notebookId, title: t, description: d }: { notebookId: string; title: string; description: string }) =>
      updateNotebook(notebookId, { title: t, description: d.trim() }),
    onSuccess: () => {
      setEditingNotebook(null);
      queryClient.invalidateQueries({ queryKey: ["notebooks"] });
    },
  });

  const notebooks = notebooksQuery.data?.data || [];
  const pagination = notebooksQuery.data?.pagination;
  const totalPages = pagination ? Math.max(1, Math.ceil(pagination.total / PAGE_SIZE)) : 0;

  useEffect(() => {
    if (currentPage <= 1) return;
    if (notebooksQuery.isLoading || notebooksQuery.isFetching) return;
    if (notebooks.length === 0) {
      setCurrentPage((prev) => Math.max(1, prev - 1));
    }
  }, [currentPage, notebooks.length, notebooksQuery.isFetching, notebooksQuery.isLoading]);

  return (
    <div className="page-shell">
      {/* Header */}
      <header className="page-header">
        <div className="row">
          <strong className="text-base tracking-tight">Newbee Notebook</strong>
        </div>
        <Link href="/library" className="btn btn-ghost">
          {t(uiStrings.notebooksPage.viewLibrary)}
        </Link>
      </header>

      {/* Main */}
      <main className="page-main stack-md">
        <div className="row-between">
          <h1 className="text-xl font-semibold tracking-tight" style={{ margin: 0 }}>
            {t(uiStrings.notebooksPage.title)}
          </h1>
        </div>

        {/* Loading */}
        {notebooksQuery.isLoading && (
          <div className="notebook-grid">
            {[1, 2, 3].map((i) => (
              <div key={i} className="card" style={{ padding: 20 }}>
                <div className="skeleton" style={{ height: 20, width: "60%", marginBottom: 12 }} />
                <div className="skeleton" style={{ height: 14, width: "40%", marginBottom: 8 }} />
                <div className="skeleton" style={{ height: 14, width: "30%" }} />
              </div>
            ))}
          </div>
        )}

        {/* Empty state */}
        {!notebooksQuery.isLoading && notebooks.length === 0 && (
          <div className="empty-state">
            <strong>{t(uiStrings.notebooksPage.emptyTitle)}</strong>
            <p style={{ maxWidth: 360 }}>
              {t(uiStrings.notebooksPage.emptyDesc)}
            </p>
            <div className="row">
              <button className="btn btn-primary" type="button" onClick={() => setShowCreate(true)}>
                {t(uiStrings.notebooksPage.createNotebook)}
              </button>
              <Link href="/library" className="btn">
                {t(uiStrings.notebooksPage.viewLibrary)}
              </Link>
            </div>
          </div>
        )}

        {/* Notebook grid */}
        {notebooks.length > 0 && (
          <div className="notebook-grid">
            {notebooks.map((notebook) => (
              <div
                key={notebook.notebook_id}
                className="card notebook-card"
                onContextMenu={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  setContextMenu({
                    notebookId: notebook.notebook_id,
                    title: notebook.title,
                    description: notebook.description,
                    x: e.clientX,
                    y: e.clientY,
                  });
                }}
              >
                <Link
                  href={`/notebooks/${notebook.notebook_id}`}
                  className="stack-sm notebook-card-link"
                  style={{ textDecoration: "none", color: "inherit" }}
                >
                  <span className="notebook-card-menu-hint" aria-hidden="true">···</span>
                  <strong className="text-base font-semibold" style={{ lineHeight: 1.4 }}>
                    {notebook.title}
                  </strong>
                  {notebook.description && (
                    <span
                      className="muted notebook-card-description"
                      style={{
                        fontSize: 13,
                        display: "-webkit-box",
                        WebkitLineClamp: 2,
                        WebkitBoxOrient: "vertical",
                        overflow: "hidden",
                      }}
                    >
                      {notebook.description}
                    </span>
                  )}
                  <div className="row notebook-card-stats" style={{ marginTop: "auto" }}>
                    <span className="badge badge-default">
                      {ti(uiStrings.notebooksPage.documentsCount, { n: notebook.document_count })}
                    </span>
                    <span className="badge badge-default">
                      {ti(uiStrings.notebooksPage.sessionsCount, { n: notebook.session_count })}
                    </span>
                  </div>
                  <span className="muted notebook-card-updated" style={{ fontSize: 11 }}>
                    {ti(uiStrings.notebooksPage.updatedAt, {
                      value: formatRelativeTime(notebook.updated_at, lang, t, ti),
                    })}
                  </span>
                </Link>
              </div>
            ))}
          </div>
        )}

        {!notebooksQuery.isLoading && totalPages > 1 && pagination && (
          <div className="notebook-pagination" role="navigation" aria-label={t(uiStrings.notebooksPage.pageInfo)}>
            <button
              className="btn btn-ghost btn-sm"
              type="button"
              disabled={!pagination.has_prev || notebooksQuery.isFetching}
              onClick={() => setCurrentPage((prev) => Math.max(1, prev - 1))}
            >
              ← {t(uiStrings.notebooksPage.prevPage)}
            </button>
            <span className="muted notebook-pagination-info">
              {ti(uiStrings.notebooksPage.pageInfo, { current: currentPage, total: totalPages })}
            </span>
            <button
              className="btn btn-ghost btn-sm"
              type="button"
              disabled={!pagination.has_next || notebooksQuery.isFetching}
              onClick={() => setCurrentPage((prev) => prev + 1)}
            >
              {t(uiStrings.notebooksPage.nextPage)} →
            </button>
          </div>
        )}

        {/* Create dialog */}
        {showCreate && (
          <div
            style={{
              position: "fixed",
              inset: 0,
              zIndex: 50,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              background: "rgba(0,0,0,0.4)",
              backdropFilter: "blur(4px)",
            }}
            onClick={() => setShowCreate(false)}
          >
            <div
              className="card"
              style={{ width: 440, padding: 24 }}
              onClick={(e) => e.stopPropagation()}
            >
              <div className="stack-md">
                <div className="row-between">
                  <strong className="text-base font-semibold">{t(uiStrings.notebooksPage.createNewNotebook)}</strong>
                  <button className="btn btn-ghost btn-icon" type="button" onClick={() => setShowCreate(false)}>
                    ✕
                  </button>
                </div>
                <div className="stack-sm">
                  <label className="muted" style={{ fontSize: 12 }}>{t(uiStrings.notebooksPage.titleLabel)}</label>
                  <input
                    className="input"
                    placeholder={t(uiStrings.notebooksPage.titlePlaceholder)}
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                    autoFocus
                  />
                </div>
                <div className="stack-sm">
                  <label className="muted" style={{ fontSize: 12 }}>{t(uiStrings.notebooksPage.descriptionLabel)}</label>
                  <textarea
                    className="textarea"
                    placeholder={t(uiStrings.notebooksPage.descriptionPlaceholder)}
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                  />
                </div>
                <div className="row" style={{ justifyContent: "flex-end" }}>
                  <button className="btn" type="button" onClick={() => setShowCreate(false)}>
                    {t(uiStrings.common.cancel)}
                  </button>
                  <button
                    className="btn btn-primary"
                    type="button"
                    disabled={!title.trim() || createMutation.isPending}
                    onClick={() => createMutation.mutate()}
                  >
                    {t(uiStrings.notebooksPage.create)}
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        <ConfirmDialog
          open={Boolean(pendingDeleteNotebook)}
          title={t(uiStrings.notebooksPage.deleteNotebookTitle)}
          message={
            pendingDeleteNotebook
              ? `${ti(uiStrings.notebooksPage.deleteNotebookConfirm, {
                  title: pendingDeleteNotebook.title,
                })}\n${t(uiStrings.notebooksPage.deleteNotebookConfirmDetail)}`
              : ""
          }
          variant="danger"
          confirmLabel={t(uiStrings.common.confirmDelete)}
          confirmDisabled={deleteMutation.isPending}
          onCancel={() => setPendingDeleteNotebook(null)}
          onConfirm={() => {
            if (!pendingDeleteNotebook) return;
            deleteMutation.mutate(pendingDeleteNotebook.notebookId);
            setPendingDeleteNotebook(null);
          }}
        />

        {/* Context menu */}
        {contextMenu && (
          <NotebookContextMenu
            x={contextMenu.x}
            y={contextMenu.y}
            onEdit={() => {
              setEditingNotebook({
                notebookId: contextMenu.notebookId,
                title: contextMenu.title,
                description: contextMenu.description ?? "",
              });
            }}
            onDelete={() => {
              setPendingDeleteNotebook({
                notebookId: contextMenu.notebookId,
                title: contextMenu.title,
              });
            }}
            onClose={() => setContextMenu(null)}
          />
        )}

        {/* Edit notebook modal */}
        {editingNotebook && (
          <div
            style={{
              position: "fixed",
              inset: 0,
              zIndex: 50,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              background: "rgba(0,0,0,0.4)",
              backdropFilter: "blur(4px)",
            }}
            onClick={() => setEditingNotebook(null)}
          >
            <div
              className="card"
              style={{ width: 440, padding: 24 }}
              onClick={(e) => e.stopPropagation()}
            >
              <div className="stack-md">
                <div className="row-between">
                  <strong className="text-base font-semibold">{t(uiStrings.notebooksPage.editNotebook)}</strong>
                  <button className="btn btn-ghost btn-icon" type="button" onClick={() => setEditingNotebook(null)}>
                    ✕
                  </button>
                </div>
                <div className="stack-sm">
                  <label className="muted" style={{ fontSize: 12 }}>{t(uiStrings.notebooksPage.titleLabel)}</label>
                  <input
                    className="input"
                    value={editingNotebook.title}
                    onChange={(e) => setEditingNotebook({ ...editingNotebook, title: e.target.value })}
                    autoFocus
                  />
                  {!editingNotebook.title.trim() && (
                    <span style={{ fontSize: 12, color: "hsl(var(--destructive))" }}>
                      {t(uiStrings.notebooksPage.titleRequired)}
                    </span>
                  )}
                </div>
                <div className="stack-sm">
                  <label className="muted" style={{ fontSize: 12 }}>{t(uiStrings.notebooksPage.descriptionLabel)}</label>
                  <textarea
                    className="textarea"
                    value={editingNotebook.description}
                    onChange={(e) => setEditingNotebook({ ...editingNotebook, description: e.target.value })}
                  />
                </div>
                <div className="row" style={{ justifyContent: "flex-end" }}>
                  <button className="btn" type="button" onClick={() => setEditingNotebook(null)}>
                    {t(uiStrings.common.cancel)}
                  </button>
                  <button
                    className="btn btn-primary"
                    type="button"
                    disabled={!editingNotebook.title.trim() || updateMutation.isPending}
                    onClick={() => updateMutation.mutate(editingNotebook)}
                  >
                    {t(uiStrings.notebooksPage.editSave)}
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}
      </main>

      {/* Bottom action bar */}
      <div className="bottom-bar">
        <button className="btn btn-primary" type="button" onClick={() => setShowCreate(true)}>
          {t(uiStrings.notebooksPage.createNotebookBottom)}
        </button>
        <Link href="/library" className="btn">
          {t(uiStrings.notebooksPage.viewLibrary)}
        </Link>
      </div>
    </div>
  );
}
