"use client";

import { PermissionRequestCard, PermissionStatusTag } from "@/components/chat/permission-request-card";
import { ImageCardList } from "@/components/chat/image-card-list";
import { MarkdownViewer } from "@/components/reader/markdown-viewer";
import { DocumentReferencesCard } from "@/components/chat/sources-card";
import { getChatImageDataUrl, getChatImageThumbnailUrl } from "@/lib/api/chat-images";
import type { PermissionResponseChoice } from "@/lib/api/types";
import { toolLabel } from "@/lib/chat/tool-presentation";
import { useLang } from "@/lib/hooks/useLang";
import { uiStrings, type LocalizedString } from "@/lib/i18n/strings";
import { ChatMessage, ToolStep } from "@/stores/chat-store";

type MessageItemProps = {
  message: ChatMessage;
  roleTransition?: boolean;
  onOpenDocument: (documentId: string) => void;
  onResolvePermissionRequest?: (requestId: string, response: PermissionResponseChoice) => void;
  /**
   * Enable inline ECharts rendering for this message. Set to true only by the
   * chat panel when the immediately preceding user message starts with
   * `/diagram` (see goals-duty.md Design Goal #5).
   */
  enableInlineCharts?: boolean;
  /** Notebook id required by InlineChartCard for the "save to Studio" action. */
  notebookId?: string;
};

type TranslateFn = (text: LocalizedString) => string;
const GENERATED_MARKDOWN_IMAGE_PATTERN = /!\[[^\]]*]\([^)]+\)/g;
const GENERATED_HTML_IMAGE_PATTERN = /<img\b[^>]*>/gi;

function thinkingStageLabel(t: TranslateFn, stage?: string | null): string {
  if (stage === "retrieving") return t(uiStrings.thinking.retrieving);
  if (stage === "searching") return t(uiStrings.thinking.searching);
  if (stage === "generating") return t(uiStrings.thinking.generating);
  return t(uiStrings.thinking.default);
}

function toolDisplayLabel(toolName: string, t: TranslateFn): string {
  return t(toolLabel(toolName));
}

function toolStepDisplayLabel(step: ToolStep, t: TranslateFn): string {
  if (
    step.toolName === "bash" &&
    step.status === "warning" &&
    step.errorCode === "nonzero_exit"
  ) {
    return `${t(uiStrings.tools.shellExited)} ${step.exitCode ?? "?"}`;
  }
  return `${toolDisplayLabel(step.toolName, t)}${step.status === "running" ? "..." : ""}`;
}

function messageStatusLabel(t: TranslateFn, status?: ChatMessage["status"]): string {
  if (!status) return "";
  if (status === "streaming") return t(uiStrings.messageStatus.streaming);
  if (status === "cancelled") return t(uiStrings.messageStatus.cancelled);
  if (status === "error") return t(uiStrings.messageStatus.error);
  return status;
}

function sanitizeAssistantContent(content: string, hasGeneratedImages: boolean): string {
  if (!hasGeneratedImages) return content;
  return content
    .replace(GENERATED_MARKDOWN_IMAGE_PATTERN, "")
    .replace(GENERATED_HTML_IMAGE_PATTERN, "")
    .replace(/[ \t]+\n/g, "\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
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
          {toolStepDisplayLabel(latestStep, t)}
        </span>
      </div>
    </div>
  );
}

function UploadedImageList({ imageIds }: { imageIds: string[] }) {
  const { t } = useLang();
  if (imageIds.length === 0) return null;

  return (
    <div className="uploaded-message-image-list" data-testid="uploaded-message-image-list">
      {imageIds.map((imageId) => (
        <a
          className="uploaded-message-image-link"
          href={getChatImageDataUrl(imageId)}
          target="_blank"
          rel="noreferrer"
          key={imageId}
        >
          <img
            className="uploaded-message-image-thumb"
            src={getChatImageThumbnailUrl(imageId)}
            alt={t(uiStrings.chat.uploadedImageThumbnail)}
            loading="lazy"
          />
        </a>
      ))}
    </div>
  );
}

export function MessageItem({
  message,
  roleTransition,
  onOpenDocument: _onOpenDocument,
  onResolvePermissionRequest,
  enableInlineCharts = false,
  notebookId,
}: MessageItemProps) {
  const { t } = useLang();
  const isUser = message.role === "user";
  const uploadedImageIds = message.imageIds || [];
  const sanitizedAssistantContent = !isUser
    ? sanitizeAssistantContent(message.content, Boolean(message.images && message.images.length > 0))
    : message.content;
  const hasVisibleAssistantContent =
    !isUser && sanitizedAssistantContent.trim().length > 0;
  const hasFinalPhaseStarted =
    !isUser && Boolean(message.finalContentStarted || hasVisibleAssistantContent);
  const canShowProgressIndicators =
    !isUser && message.status === "streaming" && !hasVisibleAssistantContent;
  const showFinalContent = !isUser && hasFinalPhaseStarted;
  const showIntermediateBlock =
    !isUser &&
    message.status === "streaming" &&
    !hasFinalPhaseStarted &&
    !!message.intermediateContent;
  const showExitingIntermediateBlock =
    !isUser &&
    message.status === "streaming" &&
    !!message.exitingIntermediateContent;
  const hasToolSteps =
    canShowProgressIndicators &&
    !message.pendingPermissionRequest &&
    message.toolSteps &&
    message.toolSteps.length > 0;
  const isSynthesizing =
    canShowProgressIndicators &&
    message.thinkingStage === "synthesizing";
  const showToolSteps = hasToolSteps && !isSynthesizing;
  const showThinkingIndicator =
    canShowProgressIndicators && !showToolSteps && !message.pendingPermissionRequest;
  const hasRunningImageTool =
    !isUser &&
    message.status === "streaming" &&
    Boolean(message.toolSteps?.some((step) => step.toolName === "image_generate" && step.status === "running"));
  const pendingImageCardCount =
    hasRunningImageTool && (!message.images || message.images.length === 0) ? 1 : 0;
  const showStatusRow = Boolean(
    message.status &&
      message.status !== "done" &&
      message.status !== "streaming" &&
      !showThinkingIndicator &&
      !hasToolSteps
  );

  return (
    <div
      data-testid="message-row"
      data-role={isUser ? "user" : "assistant"}
      data-message-id={message.id}
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
            <UploadedImageList imageIds={uploadedImageIds} />
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
                <UploadedImageList imageIds={uploadedImageIds} />
                <MarkdownViewer
                  content={sanitizedAssistantContent}
                  enableInlineCharts={enableInlineCharts}
                  inlineChartsNotebookId={notebookId}
                />
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

        {!isUser && ((message.images && message.images.length > 0) || pendingImageCardCount > 0) ? (
          <div style={{ marginTop: 8 }}>
            <ImageCardList images={message.images ?? []} pendingCount={pendingImageCardCount} />
          </div>
        ) : null}

        {/* Sources */}
        {message.sources && message.sources.length > 0 && (
          <div style={{ marginTop: 8 }}>
            <DocumentReferencesCard sources={message.sources} />
          </div>
        )}
        {!isUser && message.pendingPermissionRequest ? (
          message.pendingPermissionRequest.status === "collapsed" ? (
            <PermissionStatusTag request={message.pendingPermissionRequest} />
          ) : (
            <PermissionRequestCard
              request={message.pendingPermissionRequest}
              onResolve={(response) =>
                onResolvePermissionRequest?.(message.pendingPermissionRequest!.requestId, response)
              }
            />
          )
        ) : null}
      </div>
    </div>
  );
}
