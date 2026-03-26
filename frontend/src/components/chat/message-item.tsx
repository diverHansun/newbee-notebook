"use client";

import { ConfirmationCard } from "@/components/chat/confirmation-card";
import { MarkdownViewer } from "@/components/reader/markdown-viewer";
import { DocumentReferencesCard } from "@/components/chat/sources-card";
import { useLang } from "@/lib/hooks/useLang";
import { uiStrings, type LocalizedString } from "@/lib/i18n/strings";
import { ChatMessage, ToolStep } from "@/stores/chat-store";

type MessageItemProps = {
  message: ChatMessage;
  onOpenDocument: (documentId: string) => void;
  onResolveConfirmation?: (requestId: string, approved: boolean) => void;
};

type TranslateFn = (text: LocalizedString) => string;

function modeBadgeClass(mode: string): string {
  const map: Record<string, string> = {
    agent: "badge-chat",
    chat: "badge-chat",
    ask: "badge-ask",
    explain: "badge-explain",
    conclude: "badge-conclude",
  };
  return map[mode] || "badge-default";
}

function modeLabel(mode: string): string {
  const map: Record<string, string> = {
    agent: "Agent",
    chat: "Agent",
    ask: "Ask",
    explain: "Explain",
    conclude: "Conclude",
  };
  return map[mode] || mode;
}

function thinkingStageLabel(t: TranslateFn, stage?: string | null): string {
  if (stage === "retrieving") return t(uiStrings.thinking.retrieving);
  if (stage === "searching") return t(uiStrings.thinking.searching);
  if (stage === "generating") return t(uiStrings.thinking.generating);
  return t(uiStrings.thinking.default);
}

function toolDisplayLabel(toolName: string, t: TranslateFn): string {
  const known: Record<string, LocalizedString> = {
    knowledge_base: uiStrings.tools.knowledgeBase,
    tavily_search: uiStrings.tools.webSearch,
    tavily_crawl: uiStrings.tools.webCrawl,
    zhipu_web_search: uiStrings.tools.webSearch,
    zhipu_web_crawl: uiStrings.tools.webCrawl,
    time: uiStrings.tools.getTime,
    list_notes: uiStrings.tools.listNotes,
    read_note: uiStrings.tools.readNote,
    create_note: uiStrings.tools.createNote,
    update_note: uiStrings.tools.updateNote,
    delete_note: uiStrings.tools.deleteNote,
    list_marks: uiStrings.tools.listMarks,
    associate_note_document: uiStrings.tools.associateDoc,
    disassociate_note_document: uiStrings.tools.disassociateDoc,
    list_diagrams: uiStrings.tools.listDiagrams,
    read_diagram: uiStrings.tools.readDiagram,
    confirm_diagram_type: uiStrings.tools.confirmDiagramType,
    create_diagram: uiStrings.tools.createDiagram,
    update_diagram: uiStrings.tools.updateDiagram,
    delete_diagram: uiStrings.tools.deleteDiagram,
    update_diagram_positions: uiStrings.tools.updateDiagramPositions,
  };
  if (known[toolName]) return t(known[toolName]);
  return toolName.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());
}

function messageStatusLabel(t: TranslateFn, status?: ChatMessage["status"]): string {
  if (!status) return "";
  if (status === "streaming") return t(uiStrings.messageStatus.streaming);
  if (status === "cancelled") return t(uiStrings.messageStatus.cancelled);
  if (status === "error") return t(uiStrings.messageStatus.error);
  return status;
}

function ThinkingIndicator({
  stage,
  t,
}: {
  stage?: string | null;
  t: TranslateFn;
}) {
  return (
    <div className="thinking-indicator" role="status" aria-live="polite">
      <div className="thinking-indicator-header">
        <span className="thinking-indicator-ring" aria-hidden="true" />
        <span className="thinking-indicator-label">{thinkingStageLabel(t, stage)}</span>
      </div>
      <div className="thinking-indicator-progress" aria-hidden="true">
        <span className="thinking-indicator-progress-bar" />
      </div>
    </div>
  );
}

function ToolStepsIndicator({
  steps,
  thinkingStage,
  t,
}: {
  steps: ToolStep[];
  thinkingStage?: string | null;
  t: TranslateFn;
}) {
  const isSynthesizing = thinkingStage === "synthesizing";

  return (
    <div className="tool-steps-indicator" role="status" aria-live="polite">
      <div className="tool-steps-list">
        {steps.map((step) => (
          <div key={step.id} className={`tool-step tool-step--${step.status}`}>
            <span className="tool-step-icon" aria-hidden="true" />
            <span className="tool-step-label">
              {toolDisplayLabel(step.toolName, t)}
              {step.status === "running" ? "..." : ""}
            </span>
          </div>
        ))}
        {isSynthesizing ? (
          <div className="tool-step tool-step--running">
            <span className="tool-step-icon" aria-hidden="true" />
            <span className="tool-step-label">
              {t(uiStrings.thinking.generating)}
            </span>
          </div>
        ) : null}
      </div>
      <div className="tool-steps-progress" aria-hidden="true">
        <span className="tool-steps-progress-bar" />
      </div>
    </div>
  );
}

export function MessageItem({
  message,
  onOpenDocument: _onOpenDocument,
  onResolveConfirmation,
}: MessageItemProps) {
  const { t } = useLang();
  const isUser = message.role === "user";
  const hasToolSteps =
    !isUser &&
    message.status === "streaming" &&
    !message.content &&
    message.toolSteps &&
    message.toolSteps.length > 0;
  const showThinkingIndicator =
    !isUser && message.status === "streaming" && !message.content && !hasToolSteps;

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
          {message.status && message.status !== "done" && !showThinkingIndicator && !hasToolSteps && (
            <span className="muted" style={{ fontSize: 11 }}>
              {messageStatusLabel(t, message.status)}
            </span>
          )}
        </div>

        {/* Message bubble */}
        {showThinkingIndicator ? (
          <ThinkingIndicator stage={message.thinkingStage} t={t} />
        ) : hasToolSteps ? (
          <ToolStepsIndicator
            steps={message.toolSteps!}
            thinkingStage={message.thinkingStage}
            t={t}
          />
        ) : (
          <div
            className={`card${isUser ? "" : " message-bubble-assistant"}`}
            style={{
              padding: isUser ? "12px 16px" : "12px 16px 12px 14px",
              background: isUser ? "hsl(var(--user-bubble-bg))" : "hsl(var(--card))",
              color: isUser ? "hsl(var(--user-bubble-fg))" : "hsl(var(--card-foreground))",
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
            <DocumentReferencesCard sources={message.sources} />
          </div>
        )}
        {!isUser && message.pendingConfirmation ? (
          <ConfirmationCard
            confirmation={message.pendingConfirmation}
            onConfirm={() => onResolveConfirmation?.(message.pendingConfirmation!.requestId, true)}
            onReject={() => onResolveConfirmation?.(message.pendingConfirmation!.requestId, false)}
          />
        ) : null}
      </div>
    </div>
  );
}
