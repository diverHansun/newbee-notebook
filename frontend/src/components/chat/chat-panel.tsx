"use client";

import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";

import { ChatInput } from "@/components/chat/chat-input";
import { MessageItem } from "@/components/chat/message-item";
import { SessionSelect } from "@/components/chat/session-select";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import {
  buildSessionDisplayTitleMap,
  getSessionDisplayTitle,
} from "@/lib/chat/session-labels";
import type { Session } from "@/lib/api/types";
import { useLang } from "@/lib/hooks/useLang";
import { uiStrings } from "@/lib/i18n/strings";
import type { ChatMessage } from "@/stores/chat-store";

type ScrollMode = "session-settle" | "send-anchor" | "stream-follow" | "free-browse";

type ChatPanelProps = {
  notebookId: string;
  sessions: Session[];
  currentSessionId: string | null;
  messages: ChatMessage[];
  mode: "agent" | "ask";
  isStreaming: boolean;
  onModeChange: (mode: "agent" | "ask") => void;
  onSendMessage: (text: string, mode: "agent" | "ask", sourceDocIds?: string[] | null) => void;
  onCancel: () => void;
  onSwitchSession: (sessionId: string) => void;
  onCreateSession: (title?: string) => void;
  onDeleteSession: (sessionId: string) => void;
  onOpenDocument: (documentId: string) => void;
  onResolveConfirmation?: (requestId: string, approved: boolean) => void;
};

export function ChatPanel({
  notebookId,
  sessions,
  currentSessionId,
  messages,
  mode,
  isStreaming,
  onModeChange,
  onSendMessage,
  onCancel,
  onSwitchSession,
  onCreateSession,
  onDeleteSession,
  onOpenDocument,
  onResolveConfirmation,
}: ChatPanelProps) {
  const { t, ti } = useLang();
  const [pendingDeleteSession, setPendingDeleteSession] = useState<Session | null>(null);
  const [sourceDocIds, setSourceDocIds] = useState<string[] | null>(null);
  const [bottomPadding, setBottomPadding] = useState(0);
  const [scrollMode, setScrollMode] = useState<ScrollMode>("stream-follow");
  const bottomSpacerRef = useRef<HTMLDivElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const messageListRef = useRef<HTMLDivElement>(null);
  const isNearBottomRef = useRef(true);
  const pendingSessionScrollRef = useRef<string | null>(null);
  const scrollModeRef = useRef<ScrollMode>("stream-follow");
  const anchoredUserMessageIdRef = useRef<string | null>(null);
  const suppressScrollEventRef = useRef(false);
  const scrollSuppressionTimeoutRef = useRef<number | null>(null);
  const userScrollIntentRef = useRef(false);
  const sessionTitleMap = useMemo(
    () => buildSessionDisplayTitleMap(sessions, t(uiStrings.chat.defaultSessionTitle)),
    [sessions, t]
  );

  const currentSession = useMemo(
    () => sessions.find((item) => item.session_id === currentSessionId) || null,
    [currentSessionId, sessions]
  );

  useLayoutEffect(() => {
    setSourceDocIds(null);
    setBottomPadding(0);
    anchoredUserMessageIdRef.current = null;
    userScrollIntentRef.current = false;
    pendingSessionScrollRef.current = currentSessionId;
    const nextScrollMode = currentSessionId ? "session-settle" : "stream-follow";
    scrollModeRef.current = nextScrollMode;
    setScrollMode(nextScrollMode);
    isNearBottomRef.current = true;
  }, [currentSessionId]);

  const getMessageListTopInset = () => {
    const container = messageListRef.current;
    if (!container) return 0;
    const topInset = Number.parseFloat(window.getComputedStyle(container).paddingTop || "0");
    return Number.isFinite(topInset) ? topInset : 0;
  };

  const findMessageRow = (messageId: string) => {
    const container = messageListRef.current;
    if (!container) return null;
    const rows = container.querySelectorAll<HTMLElement>('[data-testid="message-row"]');
    return Array.from(rows).find((row) => row.dataset.messageId === messageId) ?? null;
  };

  const beginProgrammaticScroll = () => {
    suppressScrollEventRef.current = true;
    if (scrollSuppressionTimeoutRef.current !== null) {
      window.clearTimeout(scrollSuppressionTimeoutRef.current);
    }
    scrollSuppressionTimeoutRef.current = window.setTimeout(() => {
      suppressScrollEventRef.current = false;
      scrollSuppressionTimeoutRef.current = null;
    }, 150);
  };

  const cancelScheduledFrame = (handle: number) => {
    if (typeof window.cancelAnimationFrame === "function") {
      window.cancelAnimationFrame(handle);
      return;
    }
    window.clearTimeout(handle);
  };

  useEffect(() => {
    return () => {
      if (scrollSuppressionTimeoutRef.current !== null) {
        window.clearTimeout(scrollSuppressionTimeoutRef.current);
      }
    };
  }, []);

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
        scrollModeRef.current = "stream-follow";
        setScrollMode("stream-follow");
        isNearBottomRef.current = true;
        return;
      }

      rafId = window.requestAnimationFrame(settleScrollToBottom);
    };

    rafId = window.requestAnimationFrame(settleScrollToBottom);
    return () => cancelScheduledFrame(rafId);
  }, [currentSessionId, messages.length]);

  useLayoutEffect(() => {
    if (messages.length === 0) return;
    if (pendingSessionScrollRef.current) return;

    const lastMsg = messages[messages.length - 1];
    const secondToLast = messages[messages.length - 2];

    // 检测用户刚发送消息：
    // 1. lastMsg 本身是 user（理论路径）
    // 2. lastMsg 是 assistant 且 secondToLast 是 user（实际路径）
    //    这里不能要求 assistant.content 为空，因为首个 chunk 可能在同一批更新里已到达。
    const userJustSent =
      lastMsg.role === "user" ||
      (lastMsg.role === "assistant" && secondToLast?.role === "user");

    if (userJustSent) {
      anchoredUserMessageIdRef.current = lastMsg.role === "user" ? lastMsg.id : (secondToLast?.id ?? null);
      userScrollIntentRef.current = false;
      scrollModeRef.current = "send-anchor";
      setScrollMode("send-anchor");
      isNearBottomRef.current = false;
    }
  }, [messages.length]);

  useEffect(() => {
    if (scrollMode !== "send-anchor") return;
    const anchoredMessageId = anchoredUserMessageIdRef.current;
    const container = messageListRef.current;
    const spacer = bottomSpacerRef.current;
    if (!anchoredMessageId || !container || !spacer) return;

    const target = findMessageRow(anchoredMessageId);
    if (!target) return;

    const topInset = getMessageListTopInset();
    const targetOffsetTop = target.offsetTop;
    const targetHeight = target.offsetHeight;
    const realBelowHeight = Math.max(
      0,
      spacer.offsetTop - (targetOffsetTop + targetHeight)
    );
    const legacyBottomPadding = Math.max(
      0,
      container.clientHeight - topInset - targetHeight - realBelowHeight
    );

    const containerRect = container.getBoundingClientRect();
    const targetRect = target.getBoundingClientRect();
    const hasStableRectMeasurement =
      targetRect.height > 0 ||
      containerRect.height > 0 ||
      targetRect.top !== containerRect.top;
    const targetTopWithinScroll = hasStableRectMeasurement
      ? container.scrollTop + (targetRect.top - containerRect.top)
      : targetOffsetTop;
    const desiredScrollTop = Math.max(0, targetTopWithinScroll - topInset);
    const baseScrollHeight = Math.max(
      container.clientHeight,
      container.scrollHeight - bottomPadding
    );
    const maxBaseScrollTop = Math.max(0, baseScrollHeight - container.clientHeight);
    const requiredBottomPadding = Math.max(0, desiredScrollTop - maxBaseScrollTop);
    const nextBottomPadding = Math.max(legacyBottomPadding, requiredBottomPadding);
    const stabilizedBottomPadding = Math.max(bottomPadding, nextBottomPadding);

    if (Math.abs(bottomPadding - stabilizedBottomPadding) > 1) {
      setBottomPadding(stabilizedBottomPadding);
      return;
    }

    if (Math.abs(container.scrollTop - desiredScrollTop) > 1) {
      beginProgrammaticScroll();
      container.scrollTo({
        top: desiredScrollTop,
        behavior: "auto",
      });
    }
  }, [messages, bottomPadding, scrollMode]);

  useEffect(() => {
    const hasActiveAnchor = anchoredUserMessageIdRef.current !== null;
    if (!isStreaming || scrollModeRef.current !== "stream-follow" || hasActiveAnchor) return;

    let rafId = 0;
    const tick = () => {
      if (
        scrollModeRef.current === "stream-follow" &&
        anchoredUserMessageIdRef.current === null &&
        isNearBottomRef.current
      ) {
        messagesEndRef.current?.scrollIntoView({ behavior: "auto", block: "end" });
      }
      rafId = window.requestAnimationFrame(tick);
    };

    rafId = window.requestAnimationFrame(tick);
    return () => cancelScheduledFrame(rafId);
  }, [isStreaming, scrollMode]);

  const handleMessageListScroll = () => {
    const el = messageListRef.current;
    if (!el) return;
    const distanceToBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
    const isNearBottom = distanceToBottom <= 100;
    isNearBottomRef.current = isNearBottom;

    if (suppressScrollEventRef.current || pendingSessionScrollRef.current) {
      return;
    }

    if (scrollModeRef.current === "send-anchor") {
      if (userScrollIntentRef.current) {
        userScrollIntentRef.current = false;
        anchoredUserMessageIdRef.current = null;
        setBottomPadding(0);
        const nextScrollMode = isNearBottom ? "stream-follow" : "free-browse";
        scrollModeRef.current = nextScrollMode;
        setScrollMode(nextScrollMode);
      }
      return;
    }

    const nextScrollMode = isNearBottom ? "stream-follow" : "free-browse";
    scrollModeRef.current = nextScrollMode;
    setScrollMode(nextScrollMode);
  };

  const handleUserScrollIntent = () => {
    if (scrollModeRef.current !== "send-anchor") return;
    userScrollIntentRef.current = true;
  };

  const clearUserScrollIntent = () => {
    userScrollIntentRef.current = false;
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", gap: 0 }}>
      {/* Session bar */}
      <div
        className="row-between"
        style={{
          padding: "8px 16px",
          borderBottom: "1px solid hsl(var(--border))",
          flexShrink: 0,
          gap: 8,
        }}
      >
        <div className="row" style={{ flex: 1, minWidth: 0, gap: 8 }}>
          <SessionSelect
            sessions={sessions}
            currentSessionId={currentSessionId}
            onChange={onSwitchSession}
          />
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
        <button
          className="btn btn-sm"
          type="button"
          onClick={() => onCreateSession()}
        >
          + {t(uiStrings.chat.newSession)}
        </button>
        <span className="muted" style={{ fontSize: 11, flexShrink: 0 }}>
          {ti(uiStrings.chat.sessionCount, { n: sessions.length })}
        </span>
      </div>

      {/* Message list */}
      <div
        ref={messageListRef}
        className="chat-message-list"
        onScroll={handleMessageListScroll}
        onWheel={handleUserScrollIntent}
        onTouchMove={handleUserScrollIntent}
        onPointerDown={handleUserScrollIntent}
        onPointerUp={clearUserScrollIntent}
        onPointerCancel={clearUserScrollIntent}
      >
        {messages.length === 0 ? (
          <div className="empty-state" style={{ flex: 1 }}>
            <span>{t(uiStrings.chat.emptyMessages)}</span>
          </div>
        ) : (
          messages.map((message, index) => {
            const prev = messages[index - 1];
            const roleTransition = prev !== undefined && prev.role !== message.role;
            return (
              <MessageItem
                key={message.id}
                message={message}
                roleTransition={roleTransition}
                onOpenDocument={onOpenDocument}
                onResolveConfirmation={onResolveConfirmation}
              />
            );
          })
        )}
        <div
          ref={bottomSpacerRef}
          data-testid="chat-bottom-spacer"
          style={{ minHeight: bottomPadding, flexShrink: 0 }}
          aria-hidden
        />
        <div
          ref={messagesEndRef}
          data-testid="chat-end-sentinel"
          style={{ height: 0, flexShrink: 0 }}
          aria-hidden
        />
      </div>

      {/* Chat input */}
      <div style={{ flexShrink: 0, borderTop: "1px solid hsl(var(--border))" }}>
        <ChatInput
          notebookId={notebookId}
          mode={mode}
          isStreaming={isStreaming}
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
                name: getSessionDisplayTitle(
                  pendingDeleteSession,
                  sessionTitleMap,
                  t(uiStrings.chat.sessionSelect)
                ),
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
