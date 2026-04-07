"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useRef } from "react";

import { ApiError } from "@/lib/api/client";
import { chatOnce, confirmChatAction } from "@/lib/api/chat";
import {
  ApiListResponse,
  ChatContext,
  MessageMode,
  Session,
  SessionMessage,
  SseEventConfirmation,
} from "@/lib/api/types";
import { useLang } from "@/lib/hooks/useLang";
import { DIAGRAMS_QUERY_KEY } from "@/lib/hooks/use-diagrams";
import { ALL_VIDEO_SUMMARIES_QUERY_KEY } from "@/lib/hooks/use-videos";
import { uiStrings } from "@/lib/i18n/strings";
import { createSession, deleteSession, listSessionMessages, listSessions } from "@/lib/api/sessions";
import { useChatStream } from "@/lib/hooks/useChatStream";
import { normalizeSources } from "@/lib/utils/sources";
import { ChatMessage, ToolStep, useChatStore } from "@/stores/chat-store";

const SESSION_QUERY_KEY = (notebookId: string) => ["sessions", notebookId] as const;
const MESSAGE_QUERY_KEY = (sessionId: string | null) => ["messages", sessionId] as const;
const SESSION_PICKER_LIMIT = 50;
const STREAM_FALLBACK_RECENT_WINDOW_MS = 30_000;
const THINKING_STAGE_TIMEOUT_MS = 30_000;
const CONFIRMATION_TIMEOUT_MS = 180_000;
const LOCAL_MESSAGE_MATCH_WINDOW_MS = 120_000;

function isDiagramCommandMessage(message: string, mode: MessageMode): boolean {
  if (mode !== "agent") return false;
  return message.trim().toLowerCase().startsWith("/diagram");
}

function isNoteCommandMessage(message: string, mode: MessageMode): boolean {
  if (mode !== "agent") return false;
  return message.trim().toLowerCase().startsWith("/note");
}

function isVideoCommandMessage(message: string, mode: MessageMode): boolean {
  if (mode !== "agent") return false;
  return message.trim().toLowerCase().startsWith("/video");
}

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

function isLocalMessage(message: ChatMessage): boolean {
  return message.id.startsWith("local-");
}

function compareChatMessageOrder(left: ChatMessage, right: ChatMessage): number {
  const leftMs = Date.parse(left.createdAt);
  const rightMs = Date.parse(right.createdAt);

  if (Number.isFinite(leftMs) && Number.isFinite(rightMs) && leftMs !== rightMs) {
    return leftMs - rightMs;
  }

  if (typeof left.messageId === "number" && typeof right.messageId === "number" && left.messageId !== right.messageId) {
    return left.messageId - right.messageId;
  }

  if (left.createdAt === right.createdAt && (isLocalMessage(left) || isLocalMessage(right))) {
    if (left.role === "user" && right.role === "assistant") {
      return -1;
    }
    if (left.role === "assistant" && right.role === "user") {
      return 1;
    }
  }

  return left.createdAt.localeCompare(right.createdAt) || left.id.localeCompare(right.id);
}

function isSameRecentUserMessage(remote: ChatMessage, local: ChatMessage): boolean {
  if (remote.role !== "user" || local.role !== "user") return false;
  if (remote.mode !== local.mode) return false;
  if (remote.content.trim() !== local.content.trim()) return false;

  const remoteMs = Date.parse(remote.createdAt);
  const localMs = Date.parse(local.createdAt);
  if (!Number.isFinite(remoteMs) || !Number.isFinite(localMs)) return true;

  return Math.abs(remoteMs - localMs) <= LOCAL_MESSAGE_MATCH_WINDOW_MS;
}

function mergeFetchedWithLocalMessages(
  fetched: ChatMessage[],
  cached: ChatMessage[]
): ChatMessage[] {
  const remoteIds = new Set(fetched.map((message) => message.id));
  const remoteMessageIds = new Set(
    fetched
      .map((message) => message.messageId)
      .filter((value): value is number => typeof value === "number")
  );

  const preservedLocal = cached.filter((message) => {
    if (!isLocalMessage(message)) {
      return false;
    }
    if (remoteIds.has(message.id)) {
      return false;
    }
    if (typeof message.messageId === "number" && remoteMessageIds.has(message.messageId)) {
      return false;
    }
    if (
      message.role === "user" &&
      fetched.some((remote) => isSameRecentUserMessage(remote, message))
    ) {
      return false;
    }

    return true;
  });

  return [...fetched, ...preservedLocal].sort(compareChatMessageOrder);
}

function generateDefaultSessionTitle(sessions: Session[], pattern: string): string {
  const existingTitles = new Set(
    sessions.map((session) => session.title?.trim()).filter((title): title is string => Boolean(title))
  );

  let nextIndex = sessions.length + 1;
  let nextTitle = pattern.replace("{n}", String(nextIndex));
  while (existingTitles.has(nextTitle)) {
    nextIndex += 1;
    nextTitle = pattern.replace("{n}", String(nextIndex));
  }

  return nextTitle;
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
  const { t } = useLang();
  const queryClient = useQueryClient();
  const stream = useChatStream();
  const activeAssistantIdRef = useRef<string | null>(null);
  const activeStreamSessionIdRef = useRef<string | null>(null);
  const currentSessionIdRef = useRef<string | null>(null);
  const sessionMessagesRef = useRef<Record<string, ChatMessage[]>>({});
  const thinkingTimeoutRef = useRef<number | null>(null);
  const confirmationTimersRef = useRef<Map<string, number>>(new Map());
  const pendingIntermediatePhaseRef = useRef(false);

  const {
    currentSessionId,
    setCurrentSessionId,
    messages,
    setMessages,
    setStreaming,
    currentMode,
    setMode,
    clearMessages,
    explainCard,
    setExplainCard,
    appendExplainContent,
  } = useChatStore();

  const replaceSessionMessages = useCallback(
    (sessionId: string, nextMessages: ChatMessage[]) => {
      sessionMessagesRef.current[sessionId] = nextMessages;
      if (currentSessionIdRef.current === sessionId) {
        setMessages(nextMessages);
      }
    },
    [setMessages]
  );

  const mutateSessionMessages = useCallback(
    (sessionId: string, updater: (messages: ChatMessage[]) => ChatMessage[]) => {
      const currentMessages = sessionMessagesRef.current[sessionId] ?? [];
      replaceSessionMessages(sessionId, updater(currentMessages));
    },
    [replaceSessionMessages]
  );

  const addMessageToSession = useCallback(
    (sessionId: string, message: ChatMessage) => {
      mutateSessionMessages(sessionId, (items) => [...items, message].sort(compareChatMessageOrder));
    },
    [mutateSessionMessages]
  );

  const removeMessageFromSession = useCallback(
    (sessionId: string, id: string) => {
      mutateSessionMessages(sessionId, (items) => items.filter((item) => item.id !== id));
    },
    [mutateSessionMessages]
  );

  const updateMessageInSession = useCallback(
    (sessionId: string, id: string, updates: Partial<ChatMessage>) => {
      mutateSessionMessages(sessionId, (items) =>
        items.map((item) => (item.id === id ? { ...item, ...updates } : item))
      );
    },
    [mutateSessionMessages]
  );

  const updateThinkingStageInSession = useCallback(
    (sessionId: string, id: string, stage: string | null) => {
      mutateSessionMessages(sessionId, (items) =>
        items.map((item) => (item.id === id ? { ...item, thinkingStage: stage } : item))
      );
    },
    [mutateSessionMessages]
  );

  const getSessionMessage = useCallback((sessionId: string, id: string) => {
    return (sessionMessagesRef.current[sessionId] ?? []).find((item) => item.id === id) ?? null;
  }, []);

  const rotateIntermediateContentInSession = useCallback(
    (sessionId: string, id: string) => {
      mutateSessionMessages(sessionId, (items) =>
        items.map((item) => {
          if (item.id !== id) return item;

          return {
            ...item,
            intermediateContent: undefined,
            exitingIntermediateContent:
              item.intermediateContent || item.exitingIntermediateContent || null,
            intermediateGeneration: (item.intermediateGeneration ?? 0) + 1,
          };
        })
      );
    },
    [mutateSessionMessages]
  );

  const appendIntermediateContentInSession = useCallback(
    (sessionId: string, id: string, delta: string) => {
      mutateSessionMessages(sessionId, (items) =>
        items.map((item) =>
          item.id === id
            ? {
                ...item,
                intermediateContent: `${item.intermediateContent || ""}${delta}`,
              }
            : item
        )
      );
    },
    [mutateSessionMessages]
  );

  const beginFinalContentInSession = useCallback(
    (sessionId: string, id: string, firstDelta: string) => {
      mutateSessionMessages(sessionId, (items) =>
        items.map((item) => {
          if (item.id !== id) return item;

          return {
            ...item,
            content: firstDelta,
            thinkingStage: null,
            intermediateContent: undefined,
            exitingIntermediateContent:
              item.intermediateContent || item.exitingIntermediateContent || null,
          };
        })
      );
    },
    [mutateSessionMessages]
  );

  const clearIntermediateVisualStateInSession = useCallback(
    (sessionId: string, id: string) => {
      mutateSessionMessages(sessionId, (items) =>
        items.map((item) =>
          item.id === id
            ? {
                ...item,
                intermediateContent: undefined,
                exitingIntermediateContent: null,
              }
            : item
        )
      );
    },
    [mutateSessionMessages]
  );

  const appendMessageContentInSession = useCallback(
    (sessionId: string, id: string, delta: string) => {
      mutateSessionMessages(sessionId, (items) =>
        items.map((item) =>
          item.id === id
            ? { ...item, content: `${item.content}${delta}`, thinkingStage: null }
            : item
        )
      );
    },
    [mutateSessionMessages]
  );

  const addToolStepInSession = useCallback(
    (sessionId: string, id: string, step: ToolStep) => {
      mutateSessionMessages(sessionId, (items) =>
        items.map((item) =>
          item.id === id
            ? { ...item, toolSteps: [...(item.toolSteps || []), step] }
            : item
        )
      );
    },
    [mutateSessionMessages]
  );

  const updateToolStepInSession = useCallback(
    (sessionId: string, id: string, toolCallId: string, status: "running" | "done" | "error") => {
      mutateSessionMessages(sessionId, (items) =>
        items.map((item) =>
          item.id === id
            ? {
                ...item,
                toolSteps: (item.toolSteps || []).map((step) =>
                  step.id === toolCallId ? { ...step, status } : step
                ),
              }
            : item
        )
      );
    },
    [mutateSessionMessages]
  );

  const clearThinkingTimeout = useCallback(() => {
    if (thinkingTimeoutRef.current !== null) {
      window.clearTimeout(thinkingTimeoutRef.current);
      thinkingTimeoutRef.current = null;
    }
  }, []);

  const clearConfirmationTimer = useCallback((requestId: string) => {
    const timerId = confirmationTimersRef.current.get(requestId);
    if (typeof timerId === "number") {
      window.clearTimeout(timerId);
      confirmationTimersRef.current.delete(requestId);
    }
  }, []);

  const clearAllConfirmationTimers = useCallback(() => {
    confirmationTimersRef.current.forEach((timerId) => {
      window.clearTimeout(timerId);
    });
    confirmationTimersRef.current.clear();
  }, []);

  useEffect(() => {
    currentSessionIdRef.current = currentSessionId;
    if (!currentSessionId) {
      setMessages([]);
      return;
    }
    setMessages(sessionMessagesRef.current[currentSessionId] ?? []);
  }, [currentSessionId, setMessages]);

  useEffect(() => {
    sessionMessagesRef.current = {};
    activeAssistantIdRef.current = null;
    activeStreamSessionIdRef.current = null;
    currentSessionIdRef.current = null;
    pendingIntermediatePhaseRef.current = false;
  }, [notebookId]);

  const findMessageByConfirmationRequest = useCallback((requestId: string) => {
    for (const [sessionId, items] of Object.entries(sessionMessagesRef.current)) {
      const message = items.find((item) => item.pendingConfirmation?.requestId === requestId);
      if (message) {
        return { sessionId, message };
      }
    }
    return null;
  }, []);

  const trackPendingConfirmation = useCallback(
    (sessionId: string, assistantLocalId: string, event: SseEventConfirmation) => {
      const pendingConfirmation = {
        requestId: event.request_id,
        toolName: event.tool_name,
        actionType: event.action_type,
        targetType: event.target_type,
        argsSummary: event.args_summary,
        description: event.description,
        status: "pending" as const,
        expiresAt: Date.now() + CONFIRMATION_TIMEOUT_MS,
      };

      updateMessageInSession(sessionId, assistantLocalId, {
        pendingConfirmation,
      });

      clearConfirmationTimer(event.request_id);
      const timerId = window.setTimeout(() => {
        const resolved = findMessageByConfirmationRequest(event.request_id);
        if (!resolved?.message.pendingConfirmation || resolved.message.pendingConfirmation.status !== "pending") {
          confirmationTimersRef.current.delete(event.request_id);
          return;
        }

        updateMessageInSession(resolved.sessionId, resolved.message.id, {
          pendingConfirmation: {
            ...resolved.message.pendingConfirmation,
            status: "timeout",
          },
        });
        confirmationTimersRef.current.delete(event.request_id);

        // Auto-collapse after 1.5s
        window.setTimeout(() => {
          const resolvedMessage = findMessageByConfirmationRequest(event.request_id);
          if (resolvedMessage?.message.pendingConfirmation && resolvedMessage.message.pendingConfirmation.status === "timeout") {
            updateMessageInSession(resolvedMessage.sessionId, resolvedMessage.message.id, {
              pendingConfirmation: {
                ...resolvedMessage.message.pendingConfirmation,
                status: "collapsed",
                resolvedFrom: "timeout",
              },
            });
          }
        }, 1500);
      }, CONFIRMATION_TIMEOUT_MS);
      confirmationTimersRef.current.set(event.request_id, timerId);
    },
    [clearConfirmationTimer, findMessageByConfirmationRequest, updateMessageInSession]
  );

  const clearConfirmationForMessage = useCallback(
    (sessionId: string | null, assistantLocalId: string | null) => {
      if (!sessionId || !assistantLocalId) return;
      const message = (sessionMessagesRef.current[sessionId] ?? []).find((item) => item.id === assistantLocalId);
      const requestId = message?.pendingConfirmation?.requestId;
      if (requestId) {
        clearConfirmationTimer(requestId);
      }
    },
    [clearConfirmationTimer]
  );

  const scheduleThinkingTimeout = useCallback(
    (sessionId: string, assistantLocalId: string | null) => {
      clearThinkingTimeout();
      if (!assistantLocalId) return;
      thinkingTimeoutRef.current = window.setTimeout(() => {
        updateThinkingStageInSession(sessionId, assistantLocalId, null);
        thinkingTimeoutRef.current = null;
      }, THINKING_STAGE_TIMEOUT_MS);
    },
    [clearThinkingTimeout, updateThinkingStageInSession]
  );

  const sessionQuery = useQuery({
    queryKey: SESSION_QUERY_KEY(notebookId),
    queryFn: () => listSessions(notebookId, SESSION_PICKER_LIMIT, 0),
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
        mode: "agent,ask",
        limit: 100,
        offset: 0,
      });
      return response.data;
    },
    enabled: Boolean(currentSessionId),
  });

  useEffect(() => {
    if (!messageQuery.data) return;
    if (!currentSessionId) return;

    const merged = mergeFetchedWithLocalMessages(
      mapMessages(messageQuery.data),
      sessionMessagesRef.current[currentSessionId] ?? []
    );
    replaceSessionMessages(currentSessionId, merged);
  }, [currentSessionId, messageQuery.data, replaceSessionMessages]);

  useEffect(() => {
    return () => {
      clearThinkingTimeout();
      clearAllConfirmationTimers();
    };
  }, [clearAllConfirmationTimers, clearThinkingTimeout]);

  const createSessionMutation = useMutation({
    mutationFn: (title?: string) =>
      createSession(notebookId, {
        title,
      }),
    onSuccess: (newSession) => {
      sessionMessagesRef.current[newSession.session_id] = [];
      queryClient.setQueryData<ApiListResponse<Session> | undefined>(
        SESSION_QUERY_KEY(notebookId),
        (prev) => {
          if (!prev) {
            return {
              data: [newSession],
              pagination: {
                total: 1,
                limit: SESSION_PICKER_LIMIT,
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
      setMessages([]);
      queryClient.invalidateQueries({ queryKey: SESSION_QUERY_KEY(notebookId) });
    },
  });

  const deleteSessionMutation = useMutation({
    mutationFn: (sessionId: string) => deleteSession(sessionId),
    onSuccess: (_, deletedSessionId) => {
      delete sessionMessagesRef.current[deletedSessionId];
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
        resolvedSessionId = await ensureSession();
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
      const isDiagramRequest = isDiagramCommandMessage(message, mode);
      const isNoteRequest = isNoteCommandMessage(message, mode);
      const isVideoRequest = isVideoCommandMessage(message, mode);
      let streamReceivedDone = false;
      let streamReceivedErrorEvent = false;

      if (mode === "agent" || mode === "ask") {
        addMessageToSession(sessionId, {
          id: userMessageId,
          role: "user",
          mode,
          content: message,
          status: "done",
          createdAt,
        });

        const assistantLocalId = `local-assistant-${Date.now()}`;
        activeAssistantIdRef.current = assistantLocalId;
        activeStreamSessionIdRef.current = sessionId;
        addMessageToSession(sessionId, {
          id: assistantLocalId,
          role: "assistant",
          mode,
          content: "",
          thinkingStage: "retrieving",
          status: "streaming",
          createdAt: new Date().toISOString(),
        });
        pendingIntermediatePhaseRef.current = false;
        scheduleThinkingTimeout(sessionId, assistantLocalId);
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
                pendingIntermediatePhaseRef.current = false;
                updateThinkingStageInSession(sessionId, localAssistantId, null);
                updateMessageInSession(sessionId, localAssistantId, {
                  content: persistedReply.content,
                  status: "done",
                  messageId: persistedReply.message_id,
                  intermediateContent: undefined,
                  exitingIntermediateContent: null,
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

              pendingIntermediatePhaseRef.current = false;
              updateThinkingStageInSession(sessionId, localAssistantId, null);
              updateMessageInSession(sessionId, localAssistantId, {
                content: fallback.content,
                status: "done",
                messageId: fallback.message_id,
                sources: normalizeSources(fallback.sources),
                sourcesType: "document_retrieval",
                intermediateContent: undefined,
                exitingIntermediateContent: null,
              });
            } catch (fallbackError) {
              const fallbackApiError = fallbackError as ApiError;
              pendingIntermediatePhaseRef.current = false;
              updateThinkingStageInSession(sessionId, localAssistantId, null);
              updateMessageInSession(sessionId, localAssistantId, {
                status: "error",
                content: `[${fallbackApiError.errorCode || "E_FALLBACK"}] ${
                  fallbackApiError.message || "Fallback error"
                }`,
                intermediateContent: undefined,
                exitingIntermediateContent: null,
              });
            } finally {
              clearThinkingTimeout();
              setStreaming(false, null);
              activeAssistantIdRef.current = null;
              activeStreamSessionIdRef.current = null;
              if (isDiagramRequest) {
                queryClient.invalidateQueries({
                  queryKey: DIAGRAMS_QUERY_KEY(notebookId, null),
                });
              }
              if (isNoteRequest) {
                queryClient.invalidateQueries({ queryKey: ["notes", notebookId] });
              }
              if (isVideoRequest) {
                queryClient.invalidateQueries({ queryKey: ALL_VIDEO_SUMMARIES_QUERY_KEY });
              }
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
                  updateMessageInSession(sessionId, activeAssistantIdRef.current, { messageId: event.message_id });
                }
                return;
              }
              if (event.type === "phase") {
                if (event.stage === "reasoning") {
                  pendingIntermediatePhaseRef.current = true;
                }
                return;
              }
              if (event.type === "intermediate_content") {
                if (activeAssistantIdRef.current) {
                  if (pendingIntermediatePhaseRef.current) {
                    rotateIntermediateContentInSession(sessionId, activeAssistantIdRef.current);
                    pendingIntermediatePhaseRef.current = false;
                  }
                  appendIntermediateContentInSession(
                    sessionId,
                    activeAssistantIdRef.current,
                    event.delta,
                  );
                }
                return;
              }
              if (event.type === "content") {
                clearThinkingTimeout();
                if (activeAssistantIdRef.current) {
                  const activeMessage = getSessionMessage(sessionId, activeAssistantIdRef.current);
                  if (!activeMessage?.content) {
                    beginFinalContentInSession(
                      sessionId,
                      activeAssistantIdRef.current,
                      event.delta,
                    );
                  } else {
                    appendMessageContentInSession(sessionId, activeAssistantIdRef.current, event.delta);
                  }
                }
                pendingIntermediatePhaseRef.current = false;
                return;
              }
              if (event.type === "thinking") {
                if (activeAssistantIdRef.current) {
                  updateThinkingStageInSession(sessionId, activeAssistantIdRef.current, event.stage || null);
                }
                return;
              }
              if (event.type === "tool_call") {
                if (activeAssistantIdRef.current) {
                  addToolStepInSession(sessionId, activeAssistantIdRef.current, {
                    id: event.tool_call_id,
                    toolName: event.tool_name,
                    status: "running",
                  });
                }
                return;
              }
              if (event.type === "tool_result") {
                if (activeAssistantIdRef.current) {
                  updateToolStepInSession(
                    sessionId,
                    activeAssistantIdRef.current,
                    event.tool_call_id,
                    event.success ? "done" : "error",
                  );
                }
                return;
              }
              if (event.type === "sources") {
                if (activeAssistantIdRef.current) {
                  updateMessageInSession(sessionId, activeAssistantIdRef.current, {
                    sources: normalizeSources(event.sources),
                    sourcesType: event.sources_type || "document_retrieval",
                  });
                }
                return;
              }
              if (event.type === "confirmation_request") {
                if (activeAssistantIdRef.current) {
                  trackPendingConfirmation(sessionId, activeAssistantIdRef.current, event);
                }
                return;
              }
              if (event.type === "done") {
                streamReceivedDone = true;
                clearThinkingTimeout();
                clearConfirmationForMessage(sessionId, activeAssistantIdRef.current);
                if (activeAssistantIdRef.current) {
                  updateThinkingStageInSession(sessionId, activeAssistantIdRef.current, null);
                  clearIntermediateVisualStateInSession(sessionId, activeAssistantIdRef.current);
                  updateMessageInSession(sessionId, activeAssistantIdRef.current, { status: "done" });
                }
                pendingIntermediatePhaseRef.current = false;
                setStreaming(false, null);
                activeAssistantIdRef.current = null;
                activeStreamSessionIdRef.current = null;
                if (isDiagramRequest) {
                  queryClient.invalidateQueries({
                    queryKey: DIAGRAMS_QUERY_KEY(notebookId, null),
                  });
                }
                if (isNoteRequest) {
                  queryClient.invalidateQueries({ queryKey: ["notes", notebookId] });
                }
                if (isVideoRequest) {
                  queryClient.invalidateQueries({ queryKey: ALL_VIDEO_SUMMARIES_QUERY_KEY });
                }
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
                clearConfirmationForMessage(sessionId, activeAssistantIdRef.current);
                if (activeAssistantIdRef.current) {
                  updateThinkingStageInSession(sessionId, activeAssistantIdRef.current, null);
                  updateMessageInSession(sessionId, activeAssistantIdRef.current, {
                    status: "error",
                    content: `${message}\n\n[${event.error_code}] ${event.message}`,
                    intermediateContent: undefined,
                    exitingIntermediateContent: null,
                  });
                }
                pendingIntermediatePhaseRef.current = false;
                setStreaming(false, null);
                activeAssistantIdRef.current = null;
                activeStreamSessionIdRef.current = null;
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
                  clearConfirmationForMessage(sessionId, assistantLocalId);
                  updateThinkingStageInSession(sessionId, assistantLocalId, null);
                  updateMessageInSession(sessionId, assistantLocalId, {
                    status: "error",
                    content: `[${err.errorCode || "E_STREAM"}] ${err.message || "Stream error"}`,
                    intermediateContent: undefined,
                    exitingIntermediateContent: null,
                  });
                }
                pendingIntermediatePhaseRef.current = false;
                setStreaming(false, null);
                activeAssistantIdRef.current = null;
                activeStreamSessionIdRef.current = null;
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
            if (isDiagramRequest) {
              queryClient.invalidateQueries({
                queryKey: DIAGRAMS_QUERY_KEY(notebookId, null),
              });
            }
            if (isNoteRequest) {
              queryClient.invalidateQueries({ queryKey: ["notes", notebookId] });
            }
            if (isVideoRequest) {
              queryClient.invalidateQueries({ queryKey: ALL_VIDEO_SUMMARIES_QUERY_KEY });
            }
            queryClient.invalidateQueries({ queryKey: SESSION_QUERY_KEY(notebookId) });
          },
        }
      );
    },
    [
      addMessageToSession,
      addToolStepInSession,
      appendExplainContent,
      appendMessageContentInSession,
      clearConfirmationForMessage,
      clearThinkingTimeout,
      currentSessionId,
      ensureSession,
      notebookId,
      queryClient,
      sessions,
      updateThinkingStageInSession,
      updateToolStepInSession,
      setExplainCard,
      setCurrentSessionId,
      setStreaming,
      scheduleThinkingTimeout,
      stream,
      trackPendingConfirmation,
      updateMessageInSession,
      t,
    ]
  );

  const resolveConfirmation = useCallback(
    async (requestId: string, approved: boolean) => {
      const sessionId = currentSessionId;
      if (!sessionId) return;

      const resolved = findMessageByConfirmationRequest(requestId);
      if (!resolved?.message.pendingConfirmation) return;

      clearConfirmationTimer(requestId);
      const resolvedStatus = approved ? "confirmed" : "rejected";
      updateMessageInSession(resolved.sessionId, resolved.message.id, {
        pendingConfirmation: {
          ...resolved.message.pendingConfirmation,
          status: resolvedStatus,
        },
      });

      // Auto-collapse after 1.5s
      window.setTimeout(() => {
        const nextResolved = findMessageByConfirmationRequest(requestId);
        if (nextResolved?.message.pendingConfirmation && nextResolved.message.pendingConfirmation.status !== "pending") {
          updateMessageInSession(nextResolved.sessionId, nextResolved.message.id, {
            pendingConfirmation: {
              ...nextResolved.message.pendingConfirmation,
              status: "collapsed",
              resolvedFrom: nextResolved.message.pendingConfirmation.status as "confirmed" | "rejected" | "timeout",
            },
          });
        }
      }, 1500);

      await confirmChatAction(sessionId, {
        request_id: requestId,
        approved,
      });
    },
    [clearConfirmationTimer, currentSessionId, findMessageByConfirmationRequest, updateMessageInSession]
  );

  const cancelStream = useCallback(async () => {
    await stream.cancelStream();
    clearThinkingTimeout();
    if (activeAssistantIdRef.current && activeStreamSessionIdRef.current) {
      const assistantLocalId = activeAssistantIdRef.current;
      const sessionId = activeStreamSessionIdRef.current;
      clearConfirmationForMessage(sessionId, assistantLocalId);
      const activeAssistantMessage = (sessionMessagesRef.current[sessionId] ?? []).find((msg) => msg.id === assistantLocalId);
      updateThinkingStageInSession(sessionId, assistantLocalId, null);
      if (!activeAssistantMessage?.content?.trim()) {
        removeMessageFromSession(sessionId, assistantLocalId);
      } else {
        updateMessageInSession(sessionId, assistantLocalId, {
          status: "cancelled",
          intermediateContent: undefined,
          exitingIntermediateContent: null,
        });
      }
      pendingIntermediatePhaseRef.current = false;
      activeAssistantIdRef.current = null;
      activeStreamSessionIdRef.current = null;
    }
    if (explainCard?.isStreaming) {
      setExplainCard((prev) => (prev ? { ...prev, isStreaming: false } : prev));
    }
    setStreaming(false, null);
  }, [
    clearConfirmationForMessage,
    clearThinkingTimeout,
    explainCard,
    removeMessageFromSession,
    setExplainCard,
    setStreaming,
    stream,
    updateMessageInSession,
    updateThinkingStageInSession,
  ]);

  const switchSession = useCallback(
    (sessionId: string) => {
      clearThinkingTimeout();
      setCurrentSessionId(sessionId);
      setMessages(sessionMessagesRef.current[sessionId] ?? []);
    },
    [clearThinkingTimeout, setCurrentSessionId, setMessages]
  );

  const createNewSession = useCallback(
    async (title?: string) => {
      const normalizedTitle = title?.trim();
      const resolvedTitle =
        normalizedTitle || generateDefaultSessionTitle(sessions, t(uiStrings.chat.defaultSessionTitle));
      await createSessionMutation.mutateAsync(resolvedTitle);
    },
    [createSessionMutation, sessions, t]
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
    resolveConfirmation,
    refreshSessions: () => queryClient.invalidateQueries({ queryKey: SESSION_QUERY_KEY(notebookId) }),
  };
}
