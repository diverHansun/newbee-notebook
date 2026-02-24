"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import { ChatInput } from "@/components/chat/chat-input";
import { MessageItem } from "@/components/chat/message-item";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import type { Session } from "@/lib/api/types";
import { useLang } from "@/lib/hooks/useLang";
import { uiStrings } from "@/lib/i18n/strings";
import type { ChatMessage } from "@/stores/chat-store";

type ChatPanelProps = {
  notebookId: string;
  sessions: Session[];
  currentSessionId: string | null;
  messages: ChatMessage[];
  mode: "chat" | "ask";
  isStreaming: boolean;
  askBlocked: boolean;
  ragHint?: string;
  onModeChange: (mode: "chat" | "ask") => void;
  onSendMessage: (text: string, mode: "chat" | "ask", sourceDocIds?: string[] | null) => void;
  onCancel: () => void;
  onSwitchSession: (sessionId: string) => void;
  onCreateSession: (title?: string) => void;
  onDeleteSession: (sessionId: string) => void;
  onOpenDocument: (documentId: string) => void;
};

export function ChatPanel({
  notebookId,
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
  const { t, ti } = useLang();
  const [pendingDeleteSession, setPendingDeleteSession] = useState<Session | null>(null);
  const [sourceDocIds, setSourceDocIds] = useState<string[] | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const messageListRef = useRef<HTMLDivElement>(null);
  const isNearBottomRef = useRef(true);
  const pendingSessionScrollRef = useRef<string | null>(null);

  const currentSession = useMemo(
    () => sessions.find((item) => item.session_id === currentSessionId) || null,
    [currentSessionId, sessions]
  );

  useEffect(() => {
    setSourceDocIds(null);
    pendingSessionScrollRef.current = currentSessionId;
    isNearBottomRef.current = true;
  }, [currentSessionId]);

  useEffect(() => {
    if (!currentSessionId) return;
    if (pendingSessionScrollRef.current !== currentSessionId) return;
    if (messages.length === 0) return;

    let rafId = 0;
    const startedAt = window.performance.now();

    const settleScrollToBottom = () => {
      messagesEndRef.current?.scrollIntoView({ behavior: "auto", block: "end" });

      const el = messageListRef.current;
      const distanceToBottom = el
        ? el.scrollHeight - el.scrollTop - el.clientHeight
        : 0;

      // History content (markdown/tables) can expand across frames after the
      // first render. Keep nudging to bottom briefly until layout stabilizes.
      if (distanceToBottom <= 100 || window.performance.now() - startedAt > 600) {
        pendingSessionScrollRef.current = null;
        isNearBottomRef.current = true;
        return;
      }

      rafId = window.requestAnimationFrame(settleScrollToBottom);
    };

    rafId = window.requestAnimationFrame(settleScrollToBottom);
    return () => window.cancelAnimationFrame(rafId);
  }, [currentSessionId, messages.length]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages.length]);

  useEffect(() => {
    if (!isStreaming) return;

    let rafId = 0;
    const tick = () => {
      if (isNearBottomRef.current) {
        messagesEndRef.current?.scrollIntoView({ behavior: "auto", block: "end" });
      }
      rafId = window.requestAnimationFrame(tick);
    };

    rafId = window.requestAnimationFrame(tick);
    return () => window.cancelAnimationFrame(rafId);
  }, [isStreaming]);

  const handleMessageListScroll = () => {
    const el = messageListRef.current;
    if (!el) return;
    const distanceToBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
    isNearBottomRef.current = distanceToBottom <= 100;
  };

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
              {t(uiStrings.chat.sessionSelect)}
            </option>
            {sessions.map((session) => (
              <option key={session.session_id} value={session.session_id}>
                {session.title || session.session_id.slice(0, 8)}
              </option>
            ))}
          </select>
          {currentSession && (
            <button
              className="btn btn-ghost btn-danger-ghost btn-sm"
              type="button"
              onClick={() => setPendingDeleteSession(currentSession)}
            >
              {t(uiStrings.chat.deleteSession)}
            </button>
          )}
        </div>
        <div className="row">
          <button
            className="btn btn-sm"
            type="button"
            onClick={() => onCreateSession()}
          >
            + {t(uiStrings.chat.newSession)}
          </button>
        </div>
        <div className="muted" style={{ fontSize: 11, width: "100%" }}>
          {ti(uiStrings.chat.sessionCount, { n: sessions.length })}
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
      <div ref={messageListRef} className="chat-message-list" onScroll={handleMessageListScroll}>
        {messages.length === 0 ? (
          <div className="empty-state" style={{ flex: 1 }}>
            <span>{t(uiStrings.chat.emptyMessages)}</span>
          </div>
        ) : (
          messages.map((message) => (
            <MessageItem key={message.id} message={message} onOpenDocument={onOpenDocument} />
          ))
        )}
        <div ref={messagesEndRef} style={{ height: 0 }} aria-hidden />
      </div>

      {/* Chat input */}
      <div style={{ flexShrink: 0, borderTop: "1px solid hsl(var(--border))" }}>
        <ChatInput
          notebookId={notebookId}
          mode={mode}
          isStreaming={isStreaming}
          askBlocked={askBlocked}
          sourceDocIds={sourceDocIds}
          onSourceDocIdsChange={setSourceDocIds}
          onModeChange={onModeChange}
          onSend={(text, selectedMode) => onSendMessage(text, selectedMode, sourceDocIds)}
          onCancel={onCancel}
        />
      </div>

      <ConfirmDialog
        open={Boolean(pendingDeleteSession)}
        title={t(uiStrings.chat.deleteSession)}
        message={
          pendingDeleteSession
            ? `${ti(uiStrings.chat.confirmDelete, {
                name: pendingDeleteSession.title || pendingDeleteSession.session_id.slice(0, 8),
              })}\n${t(uiStrings.chat.confirmDeleteSessionDetail)}`
            : ""
        }
        variant="danger"
        confirmLabel={t(uiStrings.common.confirmDelete)}
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
