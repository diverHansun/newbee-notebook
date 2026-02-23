"use client";

import { FormEvent, useCallback, useMemo, useState } from "react";

import { SourceSelector } from "@/components/chat/source-selector";
import { SegmentedControl } from "@/components/ui/segmented-control";
import type { NotebookDocumentItem } from "@/lib/api/types";
import { useLang } from "@/lib/hooks/useLang";
import { uiStrings } from "@/lib/i18n/strings";

type ChatInputProps = {
  notebookId: string;
  mode: "chat" | "ask";
  isStreaming: boolean;
  askBlocked: boolean;
  sourceDocIds: string[] | null;
  onSourceDocIdsChange: (ids: string[] | null) => void;
  onModeChange: (mode: "chat" | "ask") => void;
  onSend: (text: string, mode: "chat" | "ask") => void;
  onCancel: () => void;
};

const MODE_OPTIONS = [
  { value: "chat", label: "Chat" },
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
  mode,
  isStreaming,
  askBlocked,
  sourceDocIds,
  onSourceDocIdsChange,
  onModeChange,
  onSend,
  onCancel,
}: ChatInputProps) {
  const { t, ti } = useLang();
  const [input, setInput] = useState("");
  const [sourceDocs, setSourceDocs] = useState<NotebookDocumentItem[]>([]);
  const [sourceDocsTotal, setSourceDocsTotal] = useState(0);

  const submitCurrentInput = () => {
    const content = input.trim();
    if (!content || isStreaming) return;
    if (mode === "ask" && askBlocked) return;
    onSend(content, mode);
    setInput("");
  };
  const sendDisabled = !input.trim() || (mode === "ask" && askBlocked);
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

        <textarea
          className="textarea chat-input-textarea"
          placeholder={
            mode === "ask"
              ? t(uiStrings.chat.inputPlaceholderAsk)
              : t(uiStrings.chat.inputPlaceholderChat)
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

        <div className="chat-input-toolbar">
          <div className="chat-input-toolbar-left">
            <SegmentedControl
              value={mode}
              options={MODE_OPTIONS.map((item) => ({ ...item }))}
              onChange={(next) => onModeChange(next as "chat" | "ask")}
              disabled={isStreaming}
            />
            <SourceSelector
              notebookId={notebookId}
              selectedIds={sourceDocIds}
              onChange={onSourceDocIdsChange}
              disabled={isStreaming}
              onDocsChange={handleSourceDocsChange}
            />
            {mode === "ask" && askBlocked && (
              <span className="badge badge-failed" style={{ fontSize: 10 }}>
                {t(uiStrings.chat.ragUnavailable)}
              </span>
            )}
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
