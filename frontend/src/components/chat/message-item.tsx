"use client";

import { ConfirmationCard, ConfirmationInlineTag } from "@/components/chat/confirmation-card";
import { MarkdownViewer } from "@/components/reader/markdown-viewer";
import { DocumentReferencesCard } from "@/components/chat/sources-card";
import { useLang } from "@/lib/hooks/useLang";
import { uiStrings, type LocalizedString } from "@/lib/i18n/strings";
import { ChatMessage, ToolStep } from "@/stores/chat-store";

type MessageItemProps = {
  message: ChatMessage;
  roleTransition?: boolean;
  onOpenDocument: (documentId: string) => void;
  onResolveConfirmation?: (requestId: string, approved: boolean) => void;
};

type TranslateFn = (text: LocalizedString) => string;

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

const ORBIT_DOTS = 8;

function ThinkingIndicator({
  stage,
  t,
}: {
  stage?: string | null;
  t: TranslateFn;
}) {
  return (
    <div className="thinking-indicator" role="status" aria-live="polite">
      <span className="thinking-indicator-orbit" aria-hidden="true">
        {Array.from({ length: ORBIT_DOTS }, (_, i) => (
          <span
            key={i}
            className="orbit-dot"
            style={{ "--i": i } as React.CSSProperties}
          />
        ))}
      </span>
      <span className="thinking-indicator-label">{thinkingStageLabel(t, stage)}</span>
    </div>
  );
}

function ToolStepsIndicator({
  steps,
  t,
}: {
  steps: ToolStep[];
  t: TranslateFn;
}) {
  const latestStep = steps[steps.length - 1];
  if (!latestStep) return null;

  return (
    <div
      className="tool-steps-indicator"
      role="status"
      aria-live="polite"
      key={latestStep.id}
    >
      <div className={`tool-step tool-step--${latestStep.status}`}>
        <span className="tool-step-icon" aria-hidden="true" />
        <span className="tool-step-label">
          {toolDisplayLabel(latestStep.toolName, t)}
          {latestStep.status === "running" ? "..." : ""}
        </span>
      </div>
    </div>
  );
}

export function MessageItem({
  message,
  roleTransition,
  onOpenDocument: _onOpenDocument,
  onResolveConfirmation,
}: MessageItemProps) {
  const { t } = useLang();
  const isUser = message.role === "user";
  const showFinalContent = !isUser && !!message.content;
  const showIntermediateBlock =
    !isUser &&
    message.status === "streaming" &&
    !message.content &&
    !!message.intermediateContent;
  const showExitingIntermediateBlock =
    !isUser &&
    message.status === "streaming" &&
    !!message.exitingIntermediateContent;
  const hasToolSteps =
    !isUser &&
    message.status === "streaming" &&
    !message.content &&
    message.toolSteps &&
    message.toolSteps.length > 0;
  const isSynthesizing =
    !isUser &&
    message.status === "streaming" &&
    !message.content &&
    message.thinkingStage === "synthesizing";
  const showToolSteps = hasToolSteps && !isSynthesizing;
  const showThinkingIndicator =
    !isUser && message.status === "streaming" && !message.content && !showToolSteps;
  const showStatusRow = Boolean(
    message.status && message.status !== "done" && !showThinkingIndicator && !hasToolSteps
  );

  return (
    <div
      data-testid="message-row"
      data-role={isUser ? "user" : "assistant"}
      style={{ display: "flex", justifyContent: isUser ? "flex-end" : "center", width: "100%", marginTop: roleTransition ? 20 : undefined }}
    >
      <div
        style={{
          width: isUser ? "auto" : "100%",
          maxWidth: isUser ? "85%" : "min(88ch, 100%)",
          minWidth: 0,
        }}
      >
        {showStatusRow ? (
          <div
            className="row"
            style={{
              marginBottom: 6,
              justifyContent: isUser ? "flex-end" : "center",
              gap: 6,
            }}
          >
            <span className="muted" style={{ fontSize: 11 }}>
              {messageStatusLabel(t, message.status)}
            </span>
          </div>
        ) : null}

        {isUser ? (
          <div
            className="card"
            data-testid="user-message-bubble"
            style={{
              padding: "8px 16px",
              borderRadius: 16,
              background: "hsl(var(--user-bubble-bg))",
              color: "hsl(var(--user-bubble-fg))",
            }}
          >
            <p style={{ margin: 0, fontSize: 15, lineHeight: 1.6, whiteSpace: "pre-wrap" }}>
              {message.content}
            </p>
          </div>
        ) : (
          <div className="assistant-lane" data-testid="assistant-lane">
            {showExitingIntermediateBlock ? (
              <div
                className="assistant-intermediate assistant-intermediate--exiting"
                data-testid="assistant-intermediate-exiting"
              >
                <p className="assistant-intermediate-text">{message.exitingIntermediateContent}</p>
              </div>
            ) : null}

            {showIntermediateBlock ? (
              <div
                key={message.intermediateGeneration ?? 0}
                className="assistant-intermediate assistant-intermediate--entering"
                data-testid="assistant-intermediate-current"
              >
                <p className="assistant-intermediate-text">{message.intermediateContent}</p>
              </div>
            ) : null}

            {showFinalContent ? (
              <div className="assistant-message-body" data-testid="assistant-message-body">
                <MarkdownViewer content={message.content} />
              </div>
            ) : null}

            {showThinkingIndicator ? (
              <ThinkingIndicator stage={message.thinkingStage} t={t} />
            ) : showToolSteps ? (
              <ToolStepsIndicator
                steps={message.toolSteps!}
                t={t}
              />
            ) : null}
          </div>
        )}

        {/* Sources */}
        {message.sources && message.sources.length > 0 && (
          <div style={{ marginTop: 8 }}>
            <DocumentReferencesCard sources={message.sources} />
          </div>
        )}
        {!isUser && message.pendingConfirmation ? (
          message.pendingConfirmation.status === "collapsed" ? (
            <ConfirmationInlineTag confirmation={message.pendingConfirmation} />
          ) : (
            <ConfirmationCard
              confirmation={message.pendingConfirmation}
              onConfirm={() => onResolveConfirmation?.(message.pendingConfirmation!.requestId, true)}
              onReject={() => onResolveConfirmation?.(message.pendingConfirmation!.requestId, false)}
            />
          )
        ) : null}
      </div>
    </div>
  );
}
