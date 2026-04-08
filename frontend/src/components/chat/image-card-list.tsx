"use client";

import { useEffect, useState } from "react";

import { ChatImage } from "@/lib/api/types";
import { useLang } from "@/lib/hooks/useLang";
import { uiStrings } from "@/lib/i18n/strings";

type ImageCardListProps = {
  images: ChatImage[];
};

const IMAGE_LOAD_RETRY_MAX = 8;
const IMAGE_LOAD_RETRY_BASE_DELAY_MS = 400;
const IMAGE_LOAD_RETRY_MAX_DELAY_MS = 2500;
const PROMPT_PREVIEW_MAX_CHARS = 96;

function imageDataUrl(imageId: string, download = false, retryToken?: number): string {
  const base = `/api/v1/generated-images/${imageId}/data`;
  const params = new URLSearchParams();
  if (download) params.set("download", "1");
  if (typeof retryToken === "number" && retryToken > 0) {
    // Add a lightweight cache buster for eventual consistency retries.
    params.set("retry", String(retryToken));
  }
  const query = params.toString();
  return query ? `${base}?${query}` : base;
}

function promptPreview(prompt: string): string {
  const normalized = prompt.trim();
  if (normalized.length <= PROMPT_PREVIEW_MAX_CHARS) {
    return normalized;
  }
  return `${normalized.slice(0, PROMPT_PREVIEW_MAX_CHARS - 1)}...`;
}

function GeneratedImageCard({ image }: { image: ChatImage }) {
  const { t } = useLang();
  const [retryAttempt, setRetryAttempt] = useState(0);
  const [retryRequested, setRetryRequested] = useState(false);
  const [copied, setCopied] = useState(false);
  const previewUrl = imageDataUrl(image.imageId, false, retryAttempt);
  const fullPrompt = image.prompt || "";
  const previewText = promptPreview(fullPrompt);
  const promptButtonLabel = t(uiStrings.chat.copyImagePrompt);
  const copiedLabel = t(uiStrings.chat.promptCopied);
  const downloadLabel = t(uiStrings.chat.downloadImage);
  const imageAlt = fullPrompt || t(uiStrings.chat.generatedImageFallbackAlt);

  useEffect(() => {
    if (!retryRequested) return;
    if (retryAttempt >= IMAGE_LOAD_RETRY_MAX) return;

    const delay = Math.min(
      IMAGE_LOAD_RETRY_MAX_DELAY_MS,
      IMAGE_LOAD_RETRY_BASE_DELAY_MS * (retryAttempt + 1)
    );
    const timerId = window.setTimeout(() => {
      setRetryAttempt((current) => current + 1);
      setRetryRequested(false);
    }, delay);

    return () => window.clearTimeout(timerId);
  }, [retryAttempt, retryRequested]);

  useEffect(() => {
    if (!copied) return;
    const timerId = window.setTimeout(() => setCopied(false), 1600);
    return () => window.clearTimeout(timerId);
  }, [copied]);

  async function handleCopyPrompt() {
    if (!fullPrompt.trim()) return;
    try {
      await navigator.clipboard.writeText(fullPrompt);
      setCopied(true);
    } catch {
      setCopied(false);
    }
  }

  return (
    <figure className="generated-image-card" key={image.imageId}>
      <div className="generated-image-card-visual">
        <a
          className="generated-image-card-link"
          href={imageDataUrl(image.imageId)}
          target="_blank"
          rel="noreferrer"
        >
          <img
            className="generated-image-card-media"
            src={previewUrl}
            alt={imageAlt}
            loading="lazy"
            onLoad={() => setRetryRequested(false)}
            onError={() => {
              if (retryAttempt >= IMAGE_LOAD_RETRY_MAX) return;
              if (!retryRequested) setRetryRequested(true);
            }}
          />
        </a>
        <a
          className="generated-image-card-downloadIcon"
          href={imageDataUrl(image.imageId, true)}
          download={`${image.imageId}.png`}
          aria-label={downloadLabel}
          title={downloadLabel}
        >
          <svg viewBox="0 0 20 20" aria-hidden="true" focusable="false">
            <path
              d="M10 3.25a.75.75 0 0 1 .75.75v6.44l1.97-1.97a.75.75 0 1 1 1.06 1.06l-3.25 3.25a.75.75 0 0 1-1.06 0L6.22 9.53a.75.75 0 1 1 1.06-1.06l1.97 1.97V4a.75.75 0 0 1 .75-.75ZM4.5 14.75A.75.75 0 0 1 5.25 14h9.5a.75.75 0 0 1 0 1.5h-9.5a.75.75 0 0 1-.75-.75Z"
              fill="currentColor"
            />
          </svg>
        </a>
      </div>
      <figcaption className="generated-image-card-meta">
        <button
          type="button"
          className={`generated-image-card-prompt ${copied ? "is-copied" : ""}`}
          title={copied ? copiedLabel : fullPrompt}
          aria-label={promptButtonLabel}
          onClick={handleCopyPrompt}
        >
          {copied ? copiedLabel : previewText}
        </button>
      </figcaption>
    </figure>
  );
}

export function ImageCardList({ images }: ImageCardListProps) {
  if (!images || images.length === 0) return null;

  return (
    <div className="generated-image-list" data-testid="generated-image-list">
      {images.map((image) => (
        <GeneratedImageCard image={image} key={image.imageId} />
      ))}
    </div>
  );
}
