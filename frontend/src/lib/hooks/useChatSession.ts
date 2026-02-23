"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useRef } from "react";

import { ApiError } from "@/lib/api/client";
import { chatOnce } from "@/lib/api/chat";
import { ApiListResponse, ChatContext, MessageMode, Session, SessionMessage } from "@/lib/api/types";
import { createSession, deleteSession, listSessionMessages, listSessions } from "@/lib/api/sessions";
import { useChatStream } from "@/lib/hooks/useChatStream";
import { normalizeSources } from "@/lib/utils/sources";
import { ChatMessage, useChatStore } from "@/stores/chat-store";

const SESSION_QUERY_KEY = (notebookId: string) => ["sessions", notebookId] as const;
const MESSAGE_QUERY_KEY = (sessionId: string | null) => ["messages", sessionId] as const;
const STREAM_FALLBACK_RECENT_WINDOW_MS = 30_000;
const THINKING_STAGE_TIMEOUT_MS = 30_000;

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

function isAbortLikeError(error: unknown): boolean {
  if (!error) return false;
  if (error instanceof DOMException) {
    return error.name === "AbortError";
  }
  return error instanceof Error && error.name === "AbortError";
}

function shouldAttemptStreamFallback(error: unknown): boolean {
  if (isAbortLikeError(error)) return false;

  if (error instanceof ApiError) {
    // Backend HTTP errors are already explicit responses and usually indicate
    // business/provider failures. Fallback should target transport/protocol
    // failures after a stream request starts, not retry every server error.
    return error.errorCode === "E_STREAM_BODY";
  }

  if (error instanceof SyntaxError) {
    return true;
  }

  return true;
}

async function findRecentPersistedAssistantReply(
  sessionId: string,
  mode: MessageMode,
  userContent: string,
  startedAtMs: number
): Promise<SessionMessage | null> {
  const response = await listSessionMessages(sessionId, {
    mode,
    limit: 20,
    offset: 0,
  });
  const messages = response.data;
  const normalizedUserContent = userContent.trim();

  for (let idx = messages.length - 1; idx >= 1; idx -= 1) {
    const assistant = messages[idx];
    const user = messages[idx - 1];
    if (!assistant || !user) continue;
    if (assistant.role !== "assistant" || user.role !== "user") continue;
    if (assistant.mode !== mode || user.mode !== mode) continue;
    if (user.content.trim() !== normalizedUserContent) continue;

    const assistantMs = Date.parse(assistant.created_at);
    if (Number.isFinite(assistantMs)) {
      if (assistantMs + STREAM_FALLBACK_RECENT_WINDOW_MS < startedAtMs) {
        continue;
      }
    }
    return assistant;
  }

  return null;
}

export function useChatSession(notebookId: string) {
  const queryClient = useQueryClient();
  const stream = useChatStream();
  const activeAssistantIdRef = useRef<string | null>(null);
  const thinkingTimeoutRef = useRef<number | null>(null);

  const {
    currentSessionId,
    setCurrentSessionId,
    messages,
    setMessages,
    addMessage,
    removeMessage,
    updateMessage,
    updateThinkingStage,
    appendMessageContent,
    setStreaming,
    currentMode,
    setMode,
    clearMessages,
    explainCard,
    setExplainCard,
    appendExplainContent,
  } = useChatStore();

  const clearThinkingTimeout = useCallback(() => {
    if (thinkingTimeoutRef.current !== null) {
      window.clearTimeout(thinkingTimeoutRef.current);
      thinkingTimeoutRef.current = null;
    }
  }, []);

  const scheduleThinkingTimeout = useCallback(
    (assistantLocalId: string | null) => {
      clearThinkingTimeout();
      if (!assistantLocalId) return;
      thinkingTimeoutRef.current = window.setTimeout(() => {
        updateThinkingStage(assistantLocalId, null);
        thinkingTimeoutRef.current = null;
      }, THINKING_STAGE_TIMEOUT_MS);
    },
    [clearThinkingTimeout, updateThinkingStage]
  );

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
    async (
      message: string,
      mode: MessageMode,
      context?: ChatContext,
      sourceDocumentIds?: string[] | null
    ) => {
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
      const streamStartedAtMs = Date.now();
      let streamReceivedDone = false;
      let streamReceivedErrorEvent = false;

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
          thinkingStage: "retrieving",
          status: "streaming",
          createdAt: new Date().toISOString(),
        });
        scheduleThinkingTimeout(assistantLocalId);
        let streamFallbackStarted = false;
        const startChatStreamFallback = (localAssistantId: string) => {
          if (streamFallbackStarted) return;
          streamFallbackStarted = true;
          setStreaming(true, null);
          void (async () => {
            try {
              const persistedReply = await findRecentPersistedAssistantReply(
                sessionId,
                mode,
                message,
                streamStartedAtMs
              );

              if (persistedReply) {
                updateThinkingStage(localAssistantId, null);
                updateMessage(localAssistantId, {
                  content: persistedReply.content,
                  status: "done",
                  messageId: persistedReply.message_id,
                });
                return;
              }

              const fallback = await chatOnce(notebookId, {
                message,
                mode,
                session_id: sessionId,
                context: context || null,
                source_document_ids: sourceDocumentIds ?? null,
              });

              updateThinkingStage(localAssistantId, null);
              updateMessage(localAssistantId, {
                content: fallback.content,
                status: "done",
                messageId: fallback.message_id,
                sources: normalizeSources(fallback.sources),
              });
            } catch (fallbackError) {
              const fallbackApiError = fallbackError as ApiError;
              updateThinkingStage(localAssistantId, null);
              updateMessage(localAssistantId, {
                status: "error",
                content: `[${fallbackApiError.errorCode || "E_FALLBACK"}] ${
                  fallbackApiError.message || "Fallback error"
                }`,
              });
            } finally {
              clearThinkingTimeout();
              setStreaming(false, null);
              activeAssistantIdRef.current = null;
              queryClient.invalidateQueries({ queryKey: SESSION_QUERY_KEY(notebookId) });
            }
          })();
        };

        setStreaming(true, null);
        await stream.startStream(
          notebookId,
          {
            message,
            mode,
            session_id: sessionId,
            context: context || null,
            source_document_ids: sourceDocumentIds ?? null,
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
                clearThinkingTimeout();
                if (activeAssistantIdRef.current) {
                  appendMessageContent(activeAssistantIdRef.current, event.delta);
                }
                return;
              }
              if (event.type === "thinking") {
                if (activeAssistantIdRef.current) {
                  updateThinkingStage(activeAssistantIdRef.current, event.stage || null);
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
                streamReceivedDone = true;
                clearThinkingTimeout();
                if (activeAssistantIdRef.current) {
                  updateThinkingStage(activeAssistantIdRef.current, null);
                  updateMessage(activeAssistantIdRef.current, { status: "done" });
                }
                setStreaming(false, null);
                activeAssistantIdRef.current = null;
                return;
              }
              if (event.type === "error") {
                if (event.error_code === "timeout" && activeAssistantIdRef.current) {
                  streamReceivedErrorEvent = true;
                  clearThinkingTimeout();
                  startChatStreamFallback(activeAssistantIdRef.current);
                  return;
                }
                streamReceivedErrorEvent = true;
                clearThinkingTimeout();
                if (activeAssistantIdRef.current) {
                  updateThinkingStage(activeAssistantIdRef.current, null);
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
              clearThinkingTimeout();
              if (streamReceivedDone || streamReceivedErrorEvent) {
                setStreaming(false, null);
                return;
              }

              const assistantLocalId = activeAssistantIdRef.current;
              const err = error as ApiError;
              if (!assistantLocalId || !shouldAttemptStreamFallback(error)) {
                if (assistantLocalId) {
                  updateThinkingStage(assistantLocalId, null);
                  updateMessage(assistantLocalId, {
                    status: "error",
                    content: `[${err.errorCode || "E_STREAM"}] ${err.message || "Stream error"}`,
                  });
                }
                setStreaming(false, null);
                activeAssistantIdRef.current = null;
                return;
              }

              startChatStreamFallback(assistantLocalId);
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
          source_document_ids: sourceDocumentIds ?? null,
        },
        {
          onEvent: (event) => {
            if (event.type === "content") {
              appendExplainContent(event.delta);
              return;
            }
            if (event.type === "done") {
              streamReceivedDone = true;
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
              streamReceivedErrorEvent = true;
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
            if (streamReceivedDone || streamReceivedErrorEvent) {
              setStreaming(false, null);
              setExplainCard((prev) => (prev ? { ...prev, isStreaming: false } : prev));
              return;
            }

            const err = error as ApiError;
            if (!shouldAttemptStreamFallback(error)) {
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
              return;
            }

            setStreaming(true, null);
            void (async () => {
              try {
                const persistedReply = await findRecentPersistedAssistantReply(
                  sessionId,
                  mode,
                  message,
                  streamStartedAtMs
                );

                if (persistedReply) {
                  setExplainCard((prev) =>
                    prev
                      ? {
                          ...prev,
                          content: persistedReply.content,
                          isStreaming: false,
                        }
                      : {
                          visible: true,
                          mode: explainMode,
                          selectedText: context?.selected_text || "",
                          content: persistedReply.content,
                          isStreaming: false,
                        }
                  );
                  return;
                }

                const fallback = await chatOnce(notebookId, {
                  message,
                  mode,
                  session_id: sessionId,
                  context: context || null,
                  source_document_ids: sourceDocumentIds ?? null,
                });

                setExplainCard((prev) =>
                  prev
                    ? {
                        ...prev,
                        content: fallback.content,
                        isStreaming: false,
                      }
                    : {
                        visible: true,
                        mode: explainMode,
                        selectedText: context?.selected_text || "",
                        content: fallback.content,
                        isStreaming: false,
                      }
                );
              } catch (fallbackError) {
                const fallbackApiError = fallbackError as ApiError;
                appendExplainContent(
                  `\n\n[${fallbackApiError.errorCode || "E_FALLBACK"}] ${
                    fallbackApiError.message || "Fallback error"
                  }`
                );
                setExplainCard((prev) =>
                  prev
                    ? {
                        ...prev,
                        isStreaming: false,
                      }
                    : prev
                );
              } finally {
                setStreaming(false, null);
                queryClient.invalidateQueries({ queryKey: SESSION_QUERY_KEY(notebookId) });
              }
            })();
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
      clearThinkingTimeout,
      currentSessionId,
      ensureSession,
      notebookId,
      queryClient,
      sessions,
      updateThinkingStage,
      setExplainCard,
      setCurrentSessionId,
      setStreaming,
      scheduleThinkingTimeout,
      stream,
      updateMessage,
    ]
  );

  const cancelStream = useCallback(async () => {
    await stream.cancelStream();
    clearThinkingTimeout();
    if (activeAssistantIdRef.current) {
      const assistantLocalId = activeAssistantIdRef.current;
      const activeAssistantMessage = messages.find((msg) => msg.id === assistantLocalId);
      updateThinkingStage(assistantLocalId, null);
      if (!activeAssistantMessage?.content?.trim()) {
        removeMessage(assistantLocalId);
      } else {
        updateMessage(assistantLocalId, {
          status: "cancelled",
        });
      }
      activeAssistantIdRef.current = null;
    }
    if (explainCard?.isStreaming) {
      setExplainCard((prev) => (prev ? { ...prev, isStreaming: false } : prev));
    }
    setStreaming(false, null);
  }, [
    clearThinkingTimeout,
    explainCard,
    messages,
    removeMessage,
    setExplainCard,
    setStreaming,
    stream,
    updateMessage,
    updateThinkingStage,
  ]);

  const switchSession = useCallback(
    (sessionId: string) => {
      clearThinkingTimeout();
      setCurrentSessionId(sessionId);
      clearMessages();
    },
    [clearMessages, clearThinkingTimeout, setCurrentSessionId]
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
