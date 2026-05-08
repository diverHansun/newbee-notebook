"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { uploadChatImage } from "@/lib/api/chat-images";

export const CHAT_IMAGE_MAX_COUNT = 10;
export const CHAT_IMAGE_MAX_BYTES = 10 * 1024 * 1024;
const ALLOWED_MIME_TYPES = new Set(["image/png", "image/jpeg", "image/webp"]);

export type ChatImageAttachmentStatus = "uploading" | "ready" | "failed";

export type ChatImageUploadErrorCode =
  | "unsupported_mime"
  | "oversize"
  | "count_exceeded"
  | "missing_session"
  | "upload_failed";

export type ChatImageUploadError = {
  code: ChatImageUploadErrorCode;
  message: string;
};

export type ChatImageAttachment = {
  id: string;
  file: File;
  fileName: string;
  localUrl: string;
  status: ChatImageAttachmentStatus;
  imageId?: string;
  mimeType: string;
  sizeBytes: number;
  width?: number | null;
  height?: number | null;
  error?: ChatImageUploadError;
};

type UseChatImageUploadOptions = {
  sessionId: string | null;
  ensureSession: () => Promise<string | null>;
};

function nextAttachmentId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `chat-image-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

function validationError(file: File, currentCount: number): ChatImageUploadError | null {
  if (currentCount >= CHAT_IMAGE_MAX_COUNT) {
    return {
      code: "count_exceeded",
      message: "A message can include up to 10 images.",
    };
  }
  if (!ALLOWED_MIME_TYPES.has(file.type)) {
    return {
      code: "unsupported_mime",
      message: "Only PNG, JPG, and WebP images are supported.",
    };
  }
  if (file.size > CHAT_IMAGE_MAX_BYTES) {
    return {
      code: "oversize",
      message: "Each image must be 10 MB or smaller.",
    };
  }
  return null;
}

function uploadErrorMessage(error: unknown): string {
  if (error instanceof Error && error.message) return error.message;
  return "Image upload failed.";
}

export function useChatImageUpload({ sessionId, ensureSession }: UseChatImageUploadOptions) {
  const [attachments, setAttachments] = useState<ChatImageAttachment[]>([]);
  const [lastError, setLastError] = useState<ChatImageUploadError | null>(null);
  const attachmentsRef = useRef<ChatImageAttachment[]>([]);
  const previousSessionIdRef = useRef<string | null>(sessionId);

  const commitAttachments = useCallback((next: ChatImageAttachment[]) => {
    attachmentsRef.current = next;
    setAttachments(next);
  }, []);

  const revokeAttachmentUrls = useCallback((items: ChatImageAttachment[]) => {
    for (const item of items) {
      URL.revokeObjectURL(item.localUrl);
    }
  }, []);

  const reset = useCallback(() => {
    revokeAttachmentUrls(attachmentsRef.current);
    commitAttachments([]);
    setLastError(null);
  }, [commitAttachments, revokeAttachmentUrls]);

  const updateAttachment = useCallback(
    (id: string, next: Partial<ChatImageAttachment>) => {
      commitAttachments(
        attachmentsRef.current.map((item) =>
          item.id === id
            ? {
                ...item,
                ...next,
              }
            : item
        )
      );
    },
    [commitAttachments]
  );

  const uploadExistingAttachment = useCallback(
    async (attachment: ChatImageAttachment, resolvedSessionId: string) => {
      updateAttachment(attachment.id, { status: "uploading", error: undefined });
      try {
        const uploaded = await uploadChatImage(resolvedSessionId, attachment.file);
        updateAttachment(attachment.id, {
          status: "ready",
          imageId: uploaded.image_id,
          mimeType: uploaded.mime_type || attachment.mimeType,
          sizeBytes: uploaded.size_bytes || attachment.sizeBytes,
          width: uploaded.width,
          height: uploaded.height,
          error: undefined,
        });
      } catch (error) {
        updateAttachment(attachment.id, {
          status: "failed",
          error: {
            code: "upload_failed",
            message: uploadErrorMessage(error),
          },
        });
      }
    },
    [updateAttachment]
  );

  const add = useCallback(
    async (file: File) => {
      const error = validationError(file, attachmentsRef.current.length);
      if (error) {
        setLastError(error);
        return;
      }

      const resolvedSessionId = sessionId || (await ensureSession());
      if (!resolvedSessionId) {
        setLastError({
          code: "missing_session",
          message: "Create a chat session before uploading images.",
        });
        return;
      }

      const attachment: ChatImageAttachment = {
        id: nextAttachmentId(),
        file,
        fileName: file.name,
        localUrl: URL.createObjectURL(file),
        status: "uploading",
        mimeType: file.type,
        sizeBytes: file.size,
      };
      setLastError(null);
      commitAttachments([...attachmentsRef.current, attachment]);
      await uploadExistingAttachment(attachment, resolvedSessionId);
    },
    [commitAttachments, ensureSession, sessionId, uploadExistingAttachment]
  );

  const remove = useCallback(
    (id: string) => {
      const target = attachmentsRef.current.find((item) => item.id === id);
      if (target) {
        URL.revokeObjectURL(target.localUrl);
      }
      commitAttachments(attachmentsRef.current.filter((item) => item.id !== id));
    },
    [commitAttachments]
  );

  const retry = useCallback(
    async (id: string) => {
      const attachment = attachmentsRef.current.find((item) => item.id === id);
      if (!attachment) return;
      const resolvedSessionId = sessionId || (await ensureSession());
      if (!resolvedSessionId) {
        setLastError({
          code: "missing_session",
          message: "Create a chat session before uploading images.",
        });
        return;
      }
      await uploadExistingAttachment(attachment, resolvedSessionId);
    },
    [ensureSession, sessionId, uploadExistingAttachment]
  );

  useEffect(() => {
    const previous = previousSessionIdRef.current;
    previousSessionIdRef.current = sessionId;
    if (!previous || previous === sessionId) return;
    reset();
  }, [reset, sessionId]);

  useEffect(() => {
    return () => {
      revokeAttachmentUrls(attachmentsRef.current);
      attachmentsRef.current = [];
    };
  }, [revokeAttachmentUrls]);

  const imageIds = useMemo(
    () =>
      attachments
        .filter((item) => item.status === "ready" && item.imageId)
        .map((item) => item.imageId as string),
    [attachments]
  );
  const allReady = attachments.every((item) => item.status === "ready");
  const canAddMore = attachments.length < CHAT_IMAGE_MAX_COUNT;

  return {
    attachments,
    add,
    remove,
    retry,
    reset,
    imageIds,
    allReady,
    canAddMore,
    lastError,
  };
}
