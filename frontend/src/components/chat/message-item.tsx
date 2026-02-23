"use client";

import { zh, uiStrings } from "@/lib/i18n/strings";
import { MarkdownViewer } from "@/components/reader/markdown-viewer";
import { ChatMessage } from "@/stores/chat-store";
import { SourcesCard } from "@/components/chat/sources-card";

type MessageItemProps = {
  message: ChatMessage;
  onOpenDocument: (documentId: string) => void;
};

function modeBadgeClass(mode: string): string {
  const map: Record<string, string> = {
    chat: "badge-chat",
    ask: "badge-ask",
    explain: "badge-explain",
    conclude: "badge-conclude",
  };
  return map[mode] || "badge-default";
}

function modeLabel(mode: string): string {
  const map: Record<string, string> = {
    chat: "Chat",
    ask: "Ask",
    explain: "Explain",
    conclude: "Conclude",
  };
  return map[mode] || mode;
}

function thinkingStageLabel(stage?: string | null): string {
  if (stage === "retrieving") return zh(uiStrings.thinking.retrieving);
  if (stage === "searching") return zh(uiStrings.thinking.searching);
  if (stage === "generating") return zh(uiStrings.thinking.generating);
  return zh(uiStrings.thinking.default);
}

function messageStatusLabel(status?: ChatMessage["status"]): string {
  if (!status) return "";
  if (status === "streaming") return "生成中...";
  if (status === "cancelled") return "已取消";
  if (status === "error") return "错误";
  return status;
}

function ThinkingIndicator({ stage }: { stage?: string | null }) {
  return (
    <div className="thinking-indicator" role="status" aria-live="polite">
      <div className="thinking-indicator-header">
        <span className="thinking-indicator-ring" aria-hidden="true" />
        <span className="thinking-indicator-label">{thinkingStageLabel(stage)}</span>
      </div>
      <div className="thinking-indicator-progress" aria-hidden="true">
        <span className="thinking-indicator-progress-bar" />
      </div>
    </div>
  );
}

export function MessageItem({ message, onOpenDocument }: MessageItemProps) {
  const isUser = message.role === "user";
  const showThinkingIndicator =
    !isUser && message.status === "streaming" && !message.content;

  return (
    <div style={{ display: "flex", gap: 12, flexDirection: isUser ? "row-reverse" : "row" }}>
      {/* Avatar */}
      <div
        style={{
          width: 32,
          height: 32,
          borderRadius: "50%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontSize: 14,
          flexShrink: 0,
          background: isUser ? "hsl(var(--primary))" : "hsl(var(--muted))",
          color: isUser ? "hsl(var(--primary-foreground))" : "hsl(var(--foreground))",
        }}
      >
        {isUser ? "U" : "AI"}
      </div>

      {/* Content */}
      <div style={{ flex: 1, maxWidth: "85%", minWidth: 0 }}>
        {/* Mode badge + status */}
        <div
          className="row"
          style={{
            marginBottom: 6,
            justifyContent: isUser ? "flex-end" : "flex-start",
            gap: 6,
          }}
        >
          <span className={`badge ${modeBadgeClass(message.mode)}`}>
            {modeLabel(message.mode)}
          </span>
          {message.status && message.status !== "done" && !showThinkingIndicator && (
            <span className="muted" style={{ fontSize: 11 }}>
              {messageStatusLabel(message.status)}
            </span>
          )}
        </div>

        {/* Message bubble */}
        {showThinkingIndicator ? (
          <ThinkingIndicator stage={message.thinkingStage} />
        ) : (
          <div
            className={`card${isUser ? "" : " message-bubble-assistant"}`}
            style={{
              padding: isUser ? "12px 16px" : "12px 16px 12px 14px",
              background: isUser ? "hsl(var(--primary))" : "hsl(var(--card))",
              color: isUser ? "hsl(var(--primary-foreground))" : "hsl(var(--card-foreground))",
            }}
          >
            {isUser ? (
              <p style={{ margin: 0, fontSize: 14, lineHeight: 1.6, whiteSpace: "pre-wrap" }}>
                {message.content}
              </p>
            ) : (
              <MarkdownViewer content={message.content} />
            )}
          </div>
        )}

        {/* Sources */}
        {message.sources && message.sources.length > 0 && (
          <div style={{ marginTop: 8 }}>
            <SourcesCard sources={message.sources} onOpenDocument={onOpenDocument} />
          </div>
        )}
      </div>
    </div>
  );
}
