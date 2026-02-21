"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { createNotebook, deleteNotebook, listNotebooks } from "@/lib/api/notebooks";

function formatRelativeTime(dateString: string): string {
  const now = Date.now();
  const then = new Date(dateString).getTime();
  const diff = now - then;
  const minutes = Math.floor(diff / 60000);
  if (minutes < 1) return "刚刚";
  if (minutes < 60) return `${minutes} 分钟前`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} 小时前`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days} 天前`;
  return new Date(dateString).toLocaleDateString("zh-CN");
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
  const router = useRouter();
  const queryClient = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");

  const notebooksQuery = useQuery({
    queryKey: ["notebooks"],
    queryFn: () => listNotebooks(100, 0),
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

  const notebooks = notebooksQuery.data?.data || [];

  return (
    <div className="page-shell">
      {/* Header */}
      <header className="page-header">
        <div className="row">
          <strong className="text-base tracking-tight">Newbee Notebook</strong>
        </div>
        <Link href="/library" className="btn btn-ghost">
          查看 Library
        </Link>
      </header>

      {/* Main */}
      <main className="page-main stack-md">
        <div className="row-between">
          <h1 className="text-xl font-semibold tracking-tight" style={{ margin: 0 }}>
            我的 Notebooks
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
            <strong>还没有 Notebook</strong>
            <p style={{ maxWidth: 360 }}>
              Notebook 是你的 AI 知识助手工作区。先上传文档到 Library，再创建 Notebook 开始对话。
            </p>
            <div className="row">
              <button className="btn btn-primary" type="button" onClick={() => setShowCreate(true)}>
                创建 Notebook
              </button>
              <Link href="/library" className="btn">
                查看 Library
              </Link>
            </div>
          </div>
        )}

        {/* Notebook grid */}
        {notebooks.length > 0 && (
          <div className="notebook-grid">
            {notebooks.map((notebook) => (
              <div key={notebook.notebook_id} className="card card-interactive" style={{ padding: 0 }}>
                <Link
                  href={`/notebooks/${notebook.notebook_id}`}
                  className="stack-sm"
                  style={{ padding: 20, textDecoration: "none", color: "inherit", flex: 1 }}
                >
                  <strong className="text-sm font-medium" style={{ lineHeight: 1.4 }}>
                    {notebook.title}
                  </strong>
                  {notebook.description && (
                    <span
                      className="muted"
                      style={{
                        fontSize: 12,
                        display: "-webkit-box",
                        WebkitLineClamp: 2,
                        WebkitBoxOrient: "vertical",
                        overflow: "hidden",
                      }}
                    >
                      {notebook.description}
                    </span>
                  )}
                  <div className="row" style={{ marginTop: "auto" }}>
                    <span className="badge badge-default">{notebook.document_count} 文档</span>
                    <span className="badge badge-default">{notebook.session_count} 会话</span>
                  </div>
                  <span className="muted" style={{ fontSize: 11 }}>
                    更新于 {formatRelativeTime(notebook.updated_at)}
                  </span>
                </Link>
                <div
                  style={{
                    borderTop: "1px solid hsl(var(--border))",
                    padding: "8px 12px",
                    display: "flex",
                    justifyContent: "flex-end",
                  }}
                >
                  <button
                    className="btn btn-ghost btn-sm"
                    type="button"
                    style={{ color: "hsl(var(--destructive))" }}
                    onClick={(e) => {
                      e.stopPropagation();
                      deleteMutation.mutate(notebook.notebook_id);
                    }}
                  >
                    删除
                  </button>
                </div>
              </div>
            ))}
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
                  <strong className="text-base font-semibold">创建新 Notebook</strong>
                  <button className="btn btn-ghost btn-icon" type="button" onClick={() => setShowCreate(false)}>
                    ✕
                  </button>
                </div>
                <div className="stack-sm">
                  <label className="muted" style={{ fontSize: 12 }}>标题 *</label>
                  <input
                    className="input"
                    placeholder="输入 Notebook 标题..."
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                    autoFocus
                  />
                </div>
                <div className="stack-sm">
                  <label className="muted" style={{ fontSize: 12 }}>描述（可选）</label>
                  <textarea
                    className="textarea"
                    placeholder="简要描述这个 Notebook 的用途..."
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                  />
                </div>
                <div className="row" style={{ justifyContent: "flex-end" }}>
                  <button className="btn" type="button" onClick={() => setShowCreate(false)}>
                    取消
                  </button>
                  <button
                    className="btn btn-primary"
                    type="button"
                    disabled={!title.trim() || createMutation.isPending}
                    onClick={() => createMutation.mutate()}
                  >
                    创建
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
          + 创建 Notebook
        </button>
        <Link href="/library" className="btn">
          查看 Library
        </Link>
      </div>
    </div>
  );
}
