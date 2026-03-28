"use client";

import { create } from "zustand";

import { MessageMode, MessageRole } from "@/lib/api/types";
import { NormalizedSource } from "@/lib/utils/sources";

export type ConfirmationActionType = "create" | "update" | "delete" | "confirm";
export type ConfirmationTargetType = "note" | "diagram" | "document" | "video";
export type PendingConfirmationStatus =
  | "pending"
  | "confirmed"
  | "rejected"
  | "timeout"
  | "collapsed";

export type PendingConfirmation = {
  requestId: string;
  toolName: string;
  actionType: ConfirmationActionType;
  targetType: ConfirmationTargetType;
  argsSummary: Record<string, unknown>;
  description: string;
  status: PendingConfirmationStatus;
  expiresAt: number;
  resolvedFrom?: "confirmed" | "rejected" | "timeout";
};

export type ToolStep = {
  id: string;
  toolName: string;
  status: "running" | "done" | "error";
};

export type ChatMessage = {
  id: string;
  role: MessageRole;
  mode: MessageMode;
  content: string;
  thinkingStage?: string | null;
  messageId?: number;
  sources?: NormalizedSource[];
  sourcesType?: "document_retrieval" | "tool_results" | "none";
  status?: "streaming" | "done" | "cancelled" | "error";
  createdAt: string;
  pendingConfirmation?: PendingConfirmation;
  toolSteps?: ToolStep[];
};

export type ExplainCardState = {
  visible: boolean;
  mode: "explain" | "conclude";
  selectedText: string;
  content: string;
  isStreaming: boolean;
};

type ChatState = {
  currentSessionId: string | null;
  messages: ChatMessage[];
  isStreaming: boolean;
  currentMode: "agent" | "ask";
  streamingMessageId: number | null;
  explainCard: ExplainCardState | null;
  setCurrentSessionId: (sessionId: string | null) => void;
  setMessages: (messages: ChatMessage[]) => void;
  addMessage: (message: ChatMessage) => void;
  removeMessage: (id: string) => void;
  updateMessage: (id: string, updates: Partial<ChatMessage>) => void;
  updateThinkingStage: (id: string, stage: string | null) => void;
  appendMessageContent: (id: string, delta: string) => void;
  addToolStep: (id: string, step: ToolStep) => void;
  updateToolStep: (id: string, toolCallId: string, status: ToolStep["status"]) => void;
  setStreaming: (isStreaming: boolean, messageId?: number | null) => void;
  setMode: (mode: "agent" | "ask") => void;
  clearMessages: () => void;
  setExplainCard: (
    state: ExplainCardState | null | ((prev: ExplainCardState | null) => ExplainCardState | null)
  ) => void;
  appendExplainContent: (delta: string) => void;
};

export const useChatStore = create<ChatState>((set) => ({
  currentSessionId: null,
  messages: [],
  isStreaming: false,
  currentMode: "agent",
  streamingMessageId: null,
  explainCard: null,
  setCurrentSessionId: (sessionId) => set({ currentSessionId: sessionId }),
  setMessages: (messages) => set({ messages }),
  addMessage: (message) => set((state) => ({ messages: [...state.messages, message] })),
  removeMessage: (id) =>
    set((state) => ({
      messages: state.messages.filter((msg) => msg.id !== id),
    })),
  updateMessage: (id, updates) =>
    set((state) => ({
      messages: state.messages.map((msg) => (msg.id === id ? { ...msg, ...updates } : msg)),
    })),
  updateThinkingStage: (id, stage) =>
    set((state) => ({
      messages: state.messages.map((msg) =>
        msg.id === id ? { ...msg, thinkingStage: stage } : msg
      ),
    })),
  appendMessageContent: (id, delta) =>
    set((state) => ({
      messages: state.messages.map((msg) =>
        msg.id === id ? { ...msg, content: `${msg.content}${delta}`, thinkingStage: null } : msg
      ),
    })),
  addToolStep: (id, step) =>
    set((state) => ({
      messages: state.messages.map((msg) =>
        msg.id === id
          ? { ...msg, toolSteps: [...(msg.toolSteps || []), step] }
          : msg
      ),
    })),
  updateToolStep: (id, toolCallId, status) =>
    set((state) => ({
      messages: state.messages.map((msg) =>
        msg.id === id
          ? {
              ...msg,
              toolSteps: (msg.toolSteps || []).map((s) =>
                s.id === toolCallId ? { ...s, status } : s
              ),
            }
          : msg
      ),
    })),
  setStreaming: (isStreaming, messageId = null) =>
    set({
      isStreaming,
      streamingMessageId: isStreaming ? messageId : null,
    }),
  setMode: (mode) => set({ currentMode: mode }),
  clearMessages: () => set({ messages: [] }),
  setExplainCard: (next) =>
    set((state) => ({
      explainCard: typeof next === "function" ? next(state.explainCard) : next,
    })),
  appendExplainContent: (delta) =>
    set((state) => {
      if (!state.explainCard) return {};
      return {
        explainCard: {
          ...state.explainCard,
          content: `${state.explainCard.content}${delta}`,
        },
      };
    }),
}));
