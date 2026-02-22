"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useRef } from "react";

import { ApiError } from "@/lib/api/client";
import { ApiListResponse, ChatContext, MessageMode, Session, SessionMessage } from "@/lib/api/types";
import { createSession, deleteSession, listSessionMessages, listSessions } from "@/lib/api/sessions";
import { useChatStream } from "@/lib/hooks/useChatStream";
import { normalizeSources } from "@/lib/utils/sources";
import { ChatMessage, useChatStore } from "@/stores/chat-store";

const SESSION_QUERY_KEY = (notebookId: string) => ["sessions", notebookId] as const;
const MESSAGE_QUERY_KEY = (sessionId: string | null) => ["messages", sessionId] as const;

function mapMessages(messages: SessionMessage[]): ChatMessage[] {
  return messages.map((msg) => ({
    id: `msg-${msg.message_id}`,
    messageId: msg.message_id,
    role: msg.role,
    mode: msg.mode,
    content: msg.content,
    status: "done",
    createdAt: msg.created_at,
  }));
}

function generateDefaultSessionTitle(sessions: Session[]): string {
  const existingTitles = new Set(
    sessions.map((session) => session.title?.trim()).filter((title): title is string => Boolean(title))
  );

  let nextIndex = sessions.length + 1;
  while (existingTitles.has(`会话 ${nextIndex}`)) {
    nextIndex += 1;
  }

  return `会话 ${nextIndex}`;
}

export function useChatSession(notebookId: string) {
  const queryClient = useQueryClient();
  const stream = useChatStream();
  const activeAssistantIdRef = useRef<string | null>(null);

  const {
    currentSessionId,
    setCurrentSessionId,
    messages,
    setMessages,
    addMessage,
    updateMessage,
    appendMessageContent,
    setStreaming,
    currentMode,
    setMode,
    clearMessages,
    explainCard,
    setExplainCard,
    appendExplainContent,
  } = useChatStore();

  const sessionQuery = useQuery({
    queryKey: SESSION_QUERY_KEY(notebookId),
    queryFn: () => listSessions(notebookId),
  });

  const sessions: Session[] = useMemo(() => sessionQuery.data?.data ?? [], [sessionQuery.data?.data]);

  useEffect(() => {
    if (sessions.length === 0) {
      if (currentSessionId) {
        setCurrentSessionId(null);
        clearMessages();
      }
      return;
    }

    if (!currentSessionId) {
      setCurrentSessionId(sessions[0].session_id);
      return;
    }

    const belongsToCurrentNotebook = sessions.some(
      (session) => session.session_id === currentSessionId
    );
    if (!belongsToCurrentNotebook) {
      setCurrentSessionId(sessions[0].session_id);
      clearMessages();
    }
  }, [clearMessages, currentSessionId, sessions, setCurrentSessionId]);

  const messageQuery = useQuery({
    queryKey: MESSAGE_QUERY_KEY(currentSessionId),
    queryFn: async () => {
      if (!currentSessionId) return [];
      const response = await listSessionMessages(currentSessionId, {
        mode: "chat,ask",
        limit: 100,
        offset: 0,
      });
      return response.data;
    },
    enabled: Boolean(currentSessionId),
  });

  useEffect(() => {
    if (!messageQuery.data) return;
    setMessages(mapMessages(messageQuery.data));
  }, [messageQuery.data, setMessages]);

  const createSessionMutation = useMutation({
    mutationFn: (title?: string) =>
      createSession(notebookId, {
        title,
      }),
    onSuccess: (newSession) => {
      queryClient.setQueryData<ApiListResponse<Session> | undefined>(
        SESSION_QUERY_KEY(notebookId),
        (prev) => {
          if (!prev) {
            return {
              data: [newSession],
              pagination: {
                total: 1,
                limit: 20,
                offset: 0,
                has_next: false,
                has_prev: false,
              },
            };
          }

          if (prev.data.some((session) => session.session_id === newSession.session_id)) {
            return prev;
          }

          const nextTotal = prev.pagination.total + 1;
          const nextData = [newSession, ...prev.data].slice(0, prev.pagination.limit);

          return {
            ...prev,
            data: nextData,
            pagination: {
              ...prev.pagination,
              total: nextTotal,
              has_next: prev.pagination.offset + prev.pagination.limit < nextTotal,
            },
          };
        }
      );
      setCurrentSessionId(newSession.session_id);
      clearMessages();
      queryClient.invalidateQueries({ queryKey: SESSION_QUERY_KEY(notebookId) });
    },
  });

  const deleteSessionMutation = useMutation({
    mutationFn: (sessionId: string) => deleteSession(sessionId),
    onSuccess: (_, deletedSessionId) => {
      queryClient.invalidateQueries({ queryKey: SESSION_QUERY_KEY(notebookId) });
      if (currentSessionId === deletedSessionId) {
        setCurrentSessionId(null);
        clearMessages();
      }
    },
  });

  const ensureSession = useCallback(
    async (titleHint?: string) => {
      if (currentSessionId) return currentSessionId;
      if (sessions.length > 0) {
        const recent = sessions[0].session_id;
        setCurrentSessionId(recent);
        return recent;
      }
      const created = await createSessionMutation.mutateAsync(titleHint);
      return created.session_id;
    },
    [createSessionMutation, currentSessionId, sessions, setCurrentSessionId]
  );

  const sendMessage = useCallback(
    async (message: string, mode: MessageMode, context?: ChatContext) => {
      const isExplainOrConclude = mode === "explain" || mode === "conclude";
      const explainMode = mode as "explain" | "conclude";
      const hasCurrentSession =
        !!currentSessionId && sessions.some((session) => session.session_id === currentSessionId);
      let resolvedSessionId = hasCurrentSession ? currentSessionId : null;

      if (isExplainOrConclude && !resolvedSessionId && sessions.length > 0) {
        resolvedSessionId = sessions[0].session_id;
        setCurrentSessionId(resolvedSessionId);
      }

      if (isExplainOrConclude && !resolvedSessionId) {
        setExplainCard({
          visible: true,
          mode: explainMode,
          selectedText: context?.selected_text || "",
          content: "\u8bf7\u5148\u521b\u5efa\u4f1a\u8bdd",
          isStreaming: false,
        });
        setStreaming(false, null);
        return;
      }

      const sessionId = isExplainOrConclude
        ? resolvedSessionId
        : await ensureSession(message.slice(0, 30));

      if (!sessionId) {
        return;
      }
      const createdAt = new Date().toISOString();
      const userMessageId = `local-user-${Date.now()}`;

      if (mode === "chat" || mode === "ask") {
        addMessage({
          id: userMessageId,
          role: "user",
          mode,
          content: message,
          status: "done",
          createdAt,
        });

        const assistantLocalId = `local-assistant-${Date.now()}`;
        activeAssistantIdRef.current = assistantLocalId;
        addMessage({
          id: assistantLocalId,
          role: "assistant",
          mode,
          content: "",
          status: "streaming",
          createdAt: new Date().toISOString(),
        });

        setStreaming(true, null);
        await stream.startStream(
          notebookId,
          {
            message,
            mode,
            session_id: sessionId,
            context: context || null,
          },
          {
            onEvent: (event) => {
              if (event.type === "start") {
                setStreaming(true, event.message_id);
                if (activeAssistantIdRef.current) {
                  updateMessage(activeAssistantIdRef.current, { messageId: event.message_id });
                }
                return;
              }
              if (event.type === "content") {
                if (activeAssistantIdRef.current) {
                  appendMessageContent(activeAssistantIdRef.current, event.delta);
                }
                return;
              }
              if (event.type === "sources") {
                if (activeAssistantIdRef.current) {
                  updateMessage(activeAssistantIdRef.current, {
                    sources: normalizeSources(event.sources),
                  });
                }
                return;
              }
              if (event.type === "done") {
                if (activeAssistantIdRef.current) {
                  updateMessage(activeAssistantIdRef.current, { status: "done" });
                }
                setStreaming(false, null);
                activeAssistantIdRef.current = null;
                return;
              }
              if (event.type === "error") {
                if (activeAssistantIdRef.current) {
                  updateMessage(activeAssistantIdRef.current, {
                    status: "error",
                    content: `${message}\n\n[${event.error_code}] ${event.message}`,
                  });
                }
                setStreaming(false, null);
                activeAssistantIdRef.current = null;
              }
            },
            onError: (error) => {
              const err = error as ApiError;
              if (activeAssistantIdRef.current) {
                updateMessage(activeAssistantIdRef.current, {
                  status: "error",
                  content: `[${err.errorCode || "E_STREAM"}] ${err.message || "Stream error"}`,
                });
              }
              setStreaming(false, null);
              activeAssistantIdRef.current = null;
            },
            onDone: () => {
              queryClient.invalidateQueries({ queryKey: SESSION_QUERY_KEY(notebookId) });
            },
          }
        );
        return;
      }

      setExplainCard({
        visible: true,
        mode: explainMode,
        selectedText: context?.selected_text || "",
        content: "",
        isStreaming: true,
      });
      setStreaming(true, null);

      await stream.startStream(
        notebookId,
        {
          message,
          mode,
          session_id: sessionId,
          context: context || null,
        },
        {
          onEvent: (event) => {
            if (event.type === "content") {
              appendExplainContent(event.delta);
              return;
            }
            if (event.type === "done") {
              setExplainCard((prev) =>
                prev
                  ? {
                      ...prev,
                      isStreaming: false,
                    }
                  : {
                      visible: true,
                      mode: explainMode,
                      selectedText: context?.selected_text || "",
                      content: "",
                      isStreaming: false,
                    }
              );
              setStreaming(false, null);
              return;
            }
            if (event.type === "error") {
              appendExplainContent(`\n\n[${event.error_code}] ${event.message}`);
              setExplainCard((prev) =>
                prev
                  ? {
                      ...prev,
                      isStreaming: false,
                    }
                  : prev
              );
              setStreaming(false, null);
            }
          },
          onError: (error) => {
            const err = error as ApiError;
            appendExplainContent(`\n\n[${err.errorCode || "E_STREAM"}] ${err.message || "Stream error"}`);
            setExplainCard((prev) =>
              prev
                ? {
                    ...prev,
                    isStreaming: false,
                  }
                : prev
            );
            setStreaming(false, null);
          },
          onDone: () => {
            queryClient.invalidateQueries({ queryKey: SESSION_QUERY_KEY(notebookId) });
          },
        }
      );
    },
    [
      addMessage,
      appendExplainContent,
      appendMessageContent,
      currentSessionId,
      ensureSession,
      notebookId,
      queryClient,
      sessions,
      setExplainCard,
      setCurrentSessionId,
      setStreaming,
      stream,
      updateMessage,
    ]
  );

  const cancelStream = useCallback(async () => {
    await stream.cancelStream();
    if (activeAssistantIdRef.current) {
      updateMessage(activeAssistantIdRef.current, {
        status: "cancelled",
      });
      activeAssistantIdRef.current = null;
    }
    if (explainCard?.isStreaming) {
      setExplainCard((prev) => (prev ? { ...prev, isStreaming: false } : prev));
    }
    setStreaming(false, null);
  }, [explainCard, setExplainCard, setStreaming, stream, updateMessage]);

  const switchSession = useCallback(
    (sessionId: string) => {
      setCurrentSessionId(sessionId);
      clearMessages();
    },
    [clearMessages, setCurrentSessionId]
  );

  const createNewSession = useCallback(
    async (title?: string) => {
      const normalizedTitle = title?.trim();
      const resolvedTitle = normalizedTitle || generateDefaultSessionTitle(sessions);
      await createSessionMutation.mutateAsync(resolvedTitle);
    },
    [createSessionMutation, sessions]
  );

  const removeSession = useCallback(
    async (sessionId: string) => {
      await deleteSessionMutation.mutateAsync(sessionId);
    },
    [deleteSessionMutation]
  );

  return {
    sessions,
    currentSessionId,
    messages,
    currentMode,
    isStreaming: stream.isStreaming,
    explainCard,
    setMode,
    sendMessage,
    cancelStream,
    switchSession,
    createSession: createNewSession,
    deleteSession: removeSession,
    closeExplainCard: () => setExplainCard(null),
    refreshSessions: () => queryClient.invalidateQueries({ queryKey: SESSION_QUERY_KEY(notebookId) }),
  };
}
