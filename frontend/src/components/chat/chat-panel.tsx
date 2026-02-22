"use client";

import { useMemo, useRef, useState } from "react";

import { ChatInput } from "@/components/chat/chat-input";
import { MessageItem } from "@/components/chat/message-item";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import type { Session } from "@/lib/api/types";
import type { ChatMessage } from "@/stores/chat-store";

type ChatPanelProps = {
  sessions: Session[];
  currentSessionId: string | null;
  messages: ChatMessage[];
  mode: "chat" | "ask";
  isStreaming: boolean;
  askBlocked: boolean;
  ragHint?: string;
  onModeChange: (mode: "chat" | "ask") => void;
  onSendMessage: (text: string, mode: "chat" | "ask") => void;
  onCancel: () => void;
  onSwitchSession: (sessionId: string) => void;
  onCreateSession: (title?: string) => void;
  onDeleteSession: (sessionId: string) => void;
  onOpenDocument: (documentId: string) => void;
};

export function ChatPanel({
  sessions,
  currentSessionId,
  messages,
  mode,
  isStreaming,
  askBlocked,
  ragHint,
  onModeChange,
  onSendMessage,
  onCancel,
  onSwitchSession,
  onCreateSession,
  onDeleteSession,
  onOpenDocument,
}: ChatPanelProps) {
  const [sessionTitle, setSessionTitle] = useState("");
  const [pendingDeleteSession, setPendingDeleteSession] = useState<Session | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const currentSession = useMemo(
    () => sessions.find((item) => item.session_id === currentSessionId) || null,
    [currentSessionId, sessions]
  );

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", gap: 0 }}>
      {/* Session bar */}
      <div
        className="row-between"
        style={{
          padding: "10px 16px",
          borderBottom: "1px solid hsl(var(--border))",
          flexShrink: 0,
          flexWrap: "wrap",
          gap: 8,
        }}
      >
        <div className="row">
          <select
            className="select"
            style={{ minWidth: 160, maxWidth: 220 }}
            value={currentSessionId || ""}
            onChange={(event) => onSwitchSession(event.target.value)}
          >
            <option value="" disabled>
              选择会话
            </option>
            {sessions.map((session) => (
              <option key={session.session_id} value={session.session_id}>
                {session.title || session.session_id.slice(0, 8)}
              </option>
            ))}
          </select>
          {currentSession && (
            <button
              className="btn btn-ghost btn-sm"
              type="button"
              style={{ color: "hsl(var(--destructive))" }}
              onClick={() => setPendingDeleteSession(currentSession)}
            >
              删除
            </button>
          )}
        </div>
        <div className="row">
          <input
            className="input"
            style={{ width: 150 }}
            value={sessionTitle}
            placeholder="新会话标题（可选）"
            onChange={(event) => setSessionTitle(event.target.value)}
          />
          <button
            className="btn btn-sm"
            type="button"
            onClick={() => {
              onCreateSession(sessionTitle.trim() || undefined);
              setSessionTitle("");
            }}
          >
            + 新建会话
          </button>
        </div>
        <div className="muted" style={{ fontSize: 11, width: "100%" }}>
          {sessions.length} / 20 个会话
        </div>
      </div>

      {/* RAG hint banner */}
      {askBlocked && ragHint && (
        <div
          style={{
            margin: "12px 16px 0",
            padding: "10px 14px",
            background: "hsl(var(--bee-yellow-light))",
            border: "1px solid hsl(var(--bee-yellow) / 0.4)",
            borderLeft: "3px solid hsl(var(--bee-yellow))",
            borderRadius: "calc(var(--radius) - 2px)",
            fontSize: 13,
            color: "#92400E",
            lineHeight: 1.5,
          }}
        >
          {ragHint}
        </div>
      )}

      {/* Message list */}
      <div
        style={{
          flex: 1,
          overflow: "auto",
          padding: 16,
          display: "flex",
          flexDirection: "column",
          gap: 12,
        }}
      >
        {messages.length === 0 ? (
          <div className="empty-state" style={{ flex: 1 }}>
            <span>还没有消息，先发第一条。</span>
          </div>
        ) : (
          messages.map((message) => (
            <MessageItem key={message.id} message={message} onOpenDocument={onOpenDocument} />
          ))
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Chat input */}
      <div style={{ flexShrink: 0, borderTop: "1px solid hsl(var(--border))" }}>
        <ChatInput
          mode={mode}
          isStreaming={isStreaming}
          askBlocked={askBlocked}
          onModeChange={onModeChange}
          onSend={(text, selectedMode) => onSendMessage(text, selectedMode)}
          onCancel={onCancel}
        />
      </div>

      <ConfirmDialog
        open={Boolean(pendingDeleteSession)}
        title="删除会话"
        message={
          pendingDeleteSession
            ? `确定要删除会话「${pendingDeleteSession.title || pendingDeleteSession.session_id.slice(0, 8)}」吗？\n该会话中的聊天记录将被删除。`
            : ""
        }
        variant="danger"
        confirmLabel="确认删除"
        onCancel={() => setPendingDeleteSession(null)}
        onConfirm={() => {
          if (!pendingDeleteSession) return;
          onDeleteSession(pendingDeleteSession.session_id);
          setPendingDeleteSession(null);
        }}
      />
    </div>
  );
}
