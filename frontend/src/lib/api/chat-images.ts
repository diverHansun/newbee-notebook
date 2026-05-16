import { apiFetch } from "@/lib/api/client";

export type ChatImageUploadItem = {
  image_id: string;
  mime_type: string;
  size_bytes: number;
  width: number | null;
  height: number | null;
  preview_url?: string | null;
  thumbnail_url?: string | null;
};

type ChatImageUploadResponse = {
  images: ChatImageUploadItem[];
  errors?: unknown[];
};

export async function uploadChatImage(
  sessionId: string,
  file: File
): Promise<ChatImageUploadItem> {
  const form = new FormData();
  form.append("files", file);

  const response = await apiFetch<ChatImageUploadResponse>(
    `/chat/sessions/${encodeURIComponent(sessionId)}/images`,
    {
      method: "POST",
      body: form,
    }
  );

  const uploaded = response.images?.[0];
  if (!uploaded?.image_id) {
    throw new Error("Chat image upload returned no image");
  }
  return uploaded;
}

export function getChatImageThumbnailUrl(imageId: string): string {
  return `/api/v1/chat/images/${encodeURIComponent(imageId)}/thumbnail`;
}

export function getChatImageDataUrl(imageId: string): string {
  return `/api/v1/chat/images/${encodeURIComponent(imageId)}/data`;
}
