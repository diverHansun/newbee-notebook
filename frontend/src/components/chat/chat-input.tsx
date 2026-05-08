"use client";

import { ChangeEvent, FormEvent, useCallback, useMemo, useRef, useState } from "react";

import { ChatImageAttachmentBar } from "@/components/chat/chat-image-attachment-bar";
import { PolicySelector } from "@/components/chat/policy-selector";
import { SlashCommandHint, shouldShowSlashCommandHint } from "@/components/chat/slash-command-hint";
import { SourceSelector } from "@/components/chat/source-selector";
import { SegmentedControl } from "@/components/ui/segmented-control";
import type {
  EffectivePolicy,
  NotebookDocumentItem,
  PolicyPreferenceUpdate,
} from "@/lib/api/types";
import { useChatImageUpload } from "@/lib/hooks/useChatImageUpload";
import { useLang } from "@/lib/hooks/useLang";
import { uiStrings } from "@/lib/i18n/strings";

type ChatInputProps = {
  notebookId: string;
  currentSessionId: string | null;
  mode: "agent" | "ask";
  isStreaming: boolean;
  sourceDocIds: string[] | null;
  policy?: EffectivePolicy;
  onSourceDocIdsChange: (ids: string[] | null) => void;
  onPolicyChange?: (update: PolicyPreferenceUpdate) => Promise<void> | void;
  onModeChange: (mode: "agent" | "ask") => void;
  onEnsureSession: (titleHint?: string) => Promise<string | null>;
  onSend: (text: string, mode: "agent" | "ask", imageIds?: string[]) => void;
  onCancel: () => void;
};

const MODE_OPTIONS = [
  { value: "agent", label: "Agent" },
  { value: "ask", label: "Ask" },
] as const;

function SendIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <path
        d="M8 14V3M8 3L3 8M8 3L13 8"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function StopIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="currentColor" aria-hidden="true">
      <rect x="2" y="2" width="10" height="10" rx="1.5" />
    </svg>
  );
}

export function ChatInput({
  notebookId,
  currentSessionId,
  mode,
  isStreaming,
  sourceDocIds,
  policy,
  onSourceDocIdsChange,
  onPolicyChange,
  onModeChange,
  onEnsureSession,
  onSend,
  onCancel,
}: ChatInputProps) {
  const { t, ti } = useLang();
  const [input, setInput] = useState("");
  const [sourceDocs, setSourceDocs] = useState<NotebookDocumentItem[]>([]);
  const [sourceDocsTotal, setSourceDocsTotal] = useState(0);
  const [policyError, setPolicyError] = useState<string | null>(null);
  const [policyChanging, setPolicyChanging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const imageUpload = useChatImageUpload({
    sessionId: currentSessionId,
    ensureSession: () => onEnsureSession(input.trim().slice(0, 30) || undefined),
  });
  const showSlashCommandHint = shouldShowSlashCommandHint(input);
  const effectivePolicy =
    policy ??
    ({
      notebook_id: notebookId,
      session_id: currentSessionId,
      policy: "default",
      source: "default",
    } as EffectivePolicy);

  const submitCurrentInput = () => {
    const content = input.trim();
    if (!content || isStreaming || !imageUpload.allReady) return;
    const imageIds = imageUpload.imageIds;
    onSend(content, mode, imageIds.length > 0 ? imageIds : undefined);
    setInput("");
    imageUpload.reset();
  };
  const sendDisabled = !input.trim() || !imageUpload.allReady;
  const actionClassName = `chat-action-btn${
    isStreaming ? " is-stop" : !sendDisabled ? " is-ready" : ""
  }`;

  const submit = (event: FormEvent) => {
    event.preventDefault();
    submitCurrentInput();
  };

  const sourceDocMap = useMemo(
    () => new Map(sourceDocs.map((item) => [item.document_id, item])),
    [sourceDocs]
  );
  const selectedSourceDocs = useMemo(() => {
    if (sourceDocIds === null) return [];
    return sourceDocIds
      .map((id) => sourceDocMap.get(id))
      .filter((item): item is NotebookDocumentItem => Boolean(item));
  }, [sourceDocIds, sourceDocMap]);
  const visibleChipDocs = selectedSourceDocs.slice(0, 3);
  const hiddenChipCount = Math.max(0, selectedSourceDocs.length - visibleChipDocs.length);
  const handleSourceDocsChange = useCallback((items: NotebookDocumentItem[], total: number) => {
    setSourceDocs(items);
    setSourceDocsTotal(total);
  }, []);
  const handleSlashCommandSelect = useCallback(
    (command: string) => {
      setInput(`${command} `);
      if (mode !== "agent") {
        onModeChange("agent");
      }
    },
    [mode, onModeChange]
  );
  const handleImageInputChange = useCallback(
    async (event: ChangeEvent<HTMLInputElement>) => {
      const file = event.currentTarget.files?.[0];
      event.currentTarget.value = "";
      if (!file) return;
      await imageUpload.add(file);
    },
    [imageUpload]
  );
  const handlePolicyChange = useCallback(
    async (update: PolicyPreferenceUpdate) => {
      if (!onPolicyChange) return;
      setPolicyError(null);
      setPolicyChanging(true);
      try {
        await onPolicyChange(update);
      } catch {
        setPolicyError(t(uiStrings.policyPermission.updateFailed));
      } finally {
        setPolicyChanging(false);
      }
    },
    [onPolicyChange, t]
  );
  const policySelectorDisabled =
    isStreaming ||
    policyChanging ||
    !onPolicyChange ||
    (!effectivePolicy.session_id && effectivePolicy.source !== "notebook");
  const policyDisabledReason =
    !effectivePolicy.session_id && effectivePolicy.source !== "notebook"
      ? t(uiStrings.policyPermission.createSessionFirst)
      : undefined;

  return (
    <form onSubmit={submit} className="chat-input-shell">
      <div className="chat-input-container">
        {sourceDocIds !== null && (
          <div className="chat-input-source-chips">
            {sourceDocIds.length === 0 ? (
              <span className="chip">{t(uiStrings.sourceSelector.noSourcesChip)}</span>
            ) : (
              <>
                {visibleChipDocs.map((doc) => (
                  <span key={doc.document_id} className="chip chat-input-source-chip">
                    <span className="chat-input-source-chip-label" title={doc.title}>
                      {doc.title}
                    </span>
                    <button
                      type="button"
                      className="chat-input-source-chip-remove"
                      aria-label={ti(uiStrings.chat.removeDoc, { title: doc.title })}
                      onClick={() => {
                        if (sourceDocIds === null) return;
                        const next = sourceDocIds.filter((id) => id !== doc.document_id);
                        onSourceDocIdsChange(next.length > 0 ? next : []);
                      }}
                    >
                      ×
                    </button>
                  </span>
                ))}
                {hiddenChipCount > 0 && (
                  <span className="chip">{`+${hiddenChipCount} ${t(uiStrings.sourceSelector.more)}`}</span>
                )}
              </>
            )}
          </div>
        )}

        <ChatImageAttachmentBar
          attachments={imageUpload.attachments}
          lastError={imageUpload.lastError}
          onRemove={imageUpload.remove}
          onRetry={(id) => {
            void imageUpload.retry(id);
          }}
        />

        <textarea
          className="textarea chat-input-textarea"
          placeholder={
            mode === "ask"
              ? t(uiStrings.chat.inputPlaceholderAsk)
              : t(uiStrings.chat.inputPlaceholderAgent)
          }
          value={input}
          onChange={(event) => setInput(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              submitCurrentInput();
            }
          }}
        />
        {showSlashCommandHint ? (
          <SlashCommandHint input={input} onSelect={handleSlashCommandSelect} />
        ) : null}

        <div className="chat-input-toolbar">
          <div className="chat-input-toolbar-left">
            <input
              ref={fileInputRef}
              type="file"
              accept="image/png,image/jpeg,image/webp"
              aria-hidden="true"
              tabIndex={-1}
              className="chat-image-file-input"
              onChange={handleImageInputChange}
            />
            <button
              type="button"
              className="chat-attachment-add-btn"
              aria-label={t(uiStrings.chat.addImage)}
              title={t(uiStrings.chat.addImage)}
              disabled={isStreaming || !imageUpload.canAddMore}
              onClick={() => fileInputRef.current?.click()}
            >
              <span aria-hidden="true">+</span>
              <span>{t(uiStrings.chat.addImage)}</span>
            </button>
            <SegmentedControl
              value={mode}
              options={MODE_OPTIONS.map((item) => ({ ...item }))}
              onChange={(next) => onModeChange(next as "agent" | "ask")}
              disabled={isStreaming}
            />
            <PolicySelector
              policy={effectivePolicy}
              disabled={policySelectorDisabled}
              disabledReason={policyDisabledReason}
              onChange={handlePolicyChange}
            />
            {policyError ? <span className="policy-selector-error">{policyError}</span> : null}
            <SourceSelector
              notebookId={notebookId}
              selectedIds={sourceDocIds}
              onChange={onSourceDocIdsChange}
              disabled={isStreaming}
              onDocsChange={handleSourceDocsChange}
            />
            {sourceDocsTotal > 0 && sourceDocIds !== null && sourceDocIds.length > 0 && (
              <span className="muted" style={{ fontSize: 11 }}>
                {ti(uiStrings.chat.docCount, { selected: sourceDocIds.length, total: sourceDocsTotal })}
              </span>
            )}
          </div>

          <div className="chat-input-toolbar-right">
            <button
              className={actionClassName}
              type={isStreaming ? "button" : "submit"}
              onClick={isStreaming ? onCancel : undefined}
              disabled={!isStreaming && sendDisabled}
              aria-label={isStreaming ? t(uiStrings.chat.stopGenerate) : t(uiStrings.chat.sendMessage)}
              title={isStreaming ? t(uiStrings.chat.stopGenerate) : t(uiStrings.chat.sendMessage)}
            >
              {isStreaming ? <StopIcon /> : <SendIcon />}
            </button>
          </div>
        </div>
      </div>
    </form>
  );
}
