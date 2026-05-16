"use client";

import type { ChatImageAttachment, ChatImageUploadError } from "@/lib/hooks/useChatImageUpload";
import { useLang } from "@/lib/hooks/useLang";
import { uiStrings, type LocalizedString } from "@/lib/i18n/strings";

type ChatImageAttachmentBarProps = {
  attachments: ChatImageAttachment[];
  lastError: ChatImageUploadError | null;
  onRemove: (id: string) => void;
  onRetry: (id: string) => void;
};

function RetryIcon() {
  return (
    <svg width="12" height="12" viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <path
        d="M13 3.5v3h-3M3 12.5v-3h3M12.1 6A4.7 4.7 0 0 0 4.2 4.7L3 6M3.9 10A4.7 4.7 0 0 0 11.8 11.3L13 10"
        stroke="currentColor"
        strokeWidth="1.7"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function errorLabel(error: ChatImageUploadError, t: (text: LocalizedString) => string): string {
  if (error.code === "unsupported_mime") return t(uiStrings.chat.imageUnsupportedMime);
  if (error.code === "oversize") return t(uiStrings.chat.imageOversize);
  if (error.code === "count_exceeded") return t(uiStrings.chat.imageCountExceeded);
  if (error.code === "missing_session") return t(uiStrings.chat.imageMissingSession);
  if (error.code === "upload_failed") return t(uiStrings.chat.imageUploadFailedDetail);
  return error.message;
}

export function ChatImageAttachmentBar({
  attachments,
  lastError,
  onRemove,
  onRetry,
}: ChatImageAttachmentBarProps) {
  const { t } = useLang();
  if (attachments.length === 0 && !lastError) return null;

  return (
    <div className="chat-uploaded-attachment-region">
      {attachments.length > 0 ? (
        <div className="chat-uploaded-attachment-list" aria-label={t(uiStrings.chat.uploadedImages)}>
          {attachments.map((item) => (
            <div
              className={`chat-uploaded-attachment-card is-${item.status}`}
              key={item.id}
              data-testid="chat-uploaded-attachment-card"
            >
              <img
                className="chat-uploaded-attachment-preview"
                src={item.localUrl}
                alt={t(uiStrings.chat.uploadedImagePreview)}
              />
              {item.status !== "ready" ? (
                <span className="chat-uploaded-attachment-state">
                  {item.status === "uploading"
                    ? t(uiStrings.chat.imageUploading)
                    : t(uiStrings.chat.imageUploadFailed)}
                </span>
              ) : null}
              <div className="chat-uploaded-attachment-actions">
                {item.status === "failed" ? (
                  <button
                    type="button"
                    className="chat-uploaded-attachment-icon"
                    aria-label={t(uiStrings.chat.retryImageUpload)}
                    title={t(uiStrings.chat.retryImageUpload)}
                    onClick={() => onRetry(item.id)}
                  >
                    <RetryIcon />
                  </button>
                ) : null}
                <button
                  type="button"
                  className="chat-uploaded-attachment-icon"
                  aria-label={t(uiStrings.chat.removeUploadedImage)}
                  title={t(uiStrings.chat.removeUploadedImage)}
                  onClick={() => onRemove(item.id)}
                >
                  ×
                </button>
              </div>
            </div>
          ))}
        </div>
      ) : null}
      {lastError ? (
        <div className="chat-uploaded-attachment-error" role="alert">
          {errorLabel(lastError, t)}
        </div>
      ) : null}
    </div>
  );
}
