"use client";

import Image from "next/image";
import { useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";

import { streamBilibiliQrLogin } from "@/lib/api/bilibili-auth";
import type { VideoStreamEvent } from "@/lib/api/types";
import { summarizeVideoStream } from "@/lib/api/videos";
import {
  BILIBILI_AUTH_STATUS_QUERY_KEY,
  useBilibiliAuthStatus,
  useBilibiliLogout,
} from "@/lib/hooks/use-bilibili-auth";
import { ALL_VIDEO_SUMMARIES_QUERY_KEY, VIDEO_SUMMARIES_QUERY_KEY, VIDEO_SUMMARY_QUERY_KEY } from "@/lib/hooks/use-videos";
import { useLang } from "@/lib/hooks/useLang";
import { uiStrings } from "@/lib/i18n/strings";

type VideoInputAreaProps = {
  notebookId: string;
};

type DetectedPlatform = "bilibili" | "youtube" | "unknown" | null;
type StepType = "start" | "subtitle" | "asr" | "summarize";

type ProgressEntry = {
  label: string;
  status: "done" | "active";
};

type VideoInfoPreview = {
  title: string;
  uploaderName?: string;
  durationSeconds?: number;
};

const BV_ID_PATTERN = /^BV[0-9A-Za-z]+$/i;
const BILIBILI_URL_PATTERN = /^https?:\/\/(?:www\.)?bilibili\.com\/video\/BV[0-9A-Za-z]+/i;
const YOUTUBE_ID_PATTERN = /^[0-9A-Za-z_-]{11}$/;
const YOUTUBE_URL_PATTERN =
  /^https?:\/\/(?:(?:www|m)\.)?(?:youtube\.com\/(?:(?:watch\?v=|shorts\/|embed\/|live\/)[^?&/]+)|youtu\.be\/[^?&/]+)/i;

function detectPlatform(value: string): DetectedPlatform {
  const trimmed = value.trim();
  if (!trimmed) return null;
  if (BV_ID_PATTERN.test(trimmed) || BILIBILI_URL_PATTERN.test(trimmed)) {
    return "bilibili";
  }
  if (YOUTUBE_URL_PATTERN.test(trimmed) || (!BV_ID_PATTERN.test(trimmed) && YOUTUBE_ID_PATTERN.test(trimmed))) {
    return "youtube";
  }
  return "unknown";
}

function isValidVideoInput(value: string): boolean {
  const platform = detectPlatform(value);
  return platform === "bilibili" || platform === "youtube";
}

function isAuthError(message: string): boolean {
  const lower = message.toLowerCase();
  return (
    lower.includes("credential") ||
    lower.includes("sessdata") ||
    lower.includes("authenticationerror") ||
    lower.includes("未提供")
  );
}

function formatDuration(durationSeconds: number): string {
  const totalSeconds = Math.max(0, Math.floor(durationSeconds || 0));
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${String(seconds).padStart(2, "0")}`;
}

function getStepLabel(
  event: Extract<VideoStreamEvent, { type: StepType }>,
  t: (value: { zh: string; en: string }) => string
): string {
  switch (event.type) {
    case "start":
      return t(uiStrings.video.stepStart);
    case "subtitle":
      if (event.source === "caption_tracks") {
        return t(uiStrings.video.stepSubtitleCaptionTracks);
      }
      if (event.source === "asr") {
        return t(uiStrings.video.stepSubtitleAsr);
      }
      return t(uiStrings.video.stepSubtitle);
    case "asr":
      return t(uiStrings.video.stepAsr);
    case "summarize":
      return t(uiStrings.video.stepSummarize);
  }
}

function getFriendlyErrorMessage(
  event: Extract<VideoStreamEvent, { type: "error" }>,
  t: (value: { zh: string; en: string }) => string
): string {
  if (event.error_code === "E_VIDEO_SUMMARIZE_IN_PROGRESS") {
    return t(uiStrings.video.inProgressError);
  }
  if (event.error_code === "E_VIDEO_MAX_CONCURRENT_LIMIT") {
    return t(uiStrings.video.maxConcurrentError);
  }
  return event.message;
}

export function VideoInputArea({ notebookId }: VideoInputAreaProps) {
  const { lang, t } = useLang();
  const queryClient = useQueryClient();
  const authQuery = useBilibiliAuthStatus();
  const logoutMutation = useBilibiliLogout();

  const [input, setInput] = useState("");
  const [validationError, setValidationError] = useState<string | null>(null);
  const [streamError, setStreamError] = useState<string | null>(null);
  const [isAuthRelatedError, setIsAuthRelatedError] = useState(false);
  const [progressSteps, setProgressSteps] = useState<ProgressEntry[]>([]);
  const [streamInfo, setStreamInfo] = useState<VideoInfoPreview | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [loginDialogOpen, setLoginDialogOpen] = useState(false);
  const [loginDialogMessage, setLoginDialogMessage] = useState<string | null>(null);
  const [qrImageBase64, setQrImageBase64] = useState<string | null>(null);
  const [qrUrl, setQrUrl] = useState<string | null>(null);

  const detectedPlatform = useMemo(() => detectPlatform(input), [input]);
  const qrImageSrc = useMemo(() => {
    if (!qrImageBase64) return null;
    return `data:image/png;base64,${qrImageBase64}`;
  }, [qrImageBase64]);

  const handleStartLogin = async () => {
    setLoginDialogOpen(true);
    setLoginDialogMessage(t(uiStrings.video.loginDialogHint));
    setQrImageBase64(null);
    setQrUrl(null);

    await streamBilibiliQrLogin({
      onEvent: async (event) => {
        if (event.type === "qr_generated") {
          setQrImageBase64(event.image_base64 ?? null);
          setQrUrl(event.qr_url ?? null);
          setLoginDialogMessage(t(uiStrings.video.loginDialogHint));
          return;
        }
        if (event.type === "scanned") {
          setLoginDialogMessage(t(uiStrings.video.loginScanned));
          return;
        }
        if (event.type === "done") {
          setLoginDialogMessage(t(uiStrings.video.loginSuccess));
          await queryClient.invalidateQueries({ queryKey: BILIBILI_AUTH_STATUS_QUERY_KEY });
          return;
        }
        if (event.type === "timeout") {
          setLoginDialogMessage(t(uiStrings.video.loginTimeout));
          return;
        }
        if (event.type === "error") {
          setLoginDialogMessage(event.message);
        }
      },
    });
  };

  const handleSummarize = async () => {
    const trimmedInput = input.trim();
    let hasRefreshedProcessingLists = false;
    setValidationError(null);
    setStreamError(null);
    setIsAuthRelatedError(false);
    setProgressSteps([]);
    setStreamInfo(null);

    if (!isValidVideoInput(trimmedInput)) {
      setValidationError(t(uiStrings.video.invalidInput));
      return;
    }

    setIsSubmitting(true);
    try {
      await summarizeVideoStream(
        {
          url_or_id: trimmedInput,
          notebook_id: notebookId,
          lang,
        },
        {
          onEvent: async (event) => {
            if (
              event.type === "start" ||
              event.type === "info" ||
              event.type === "subtitle" ||
              event.type === "asr" ||
              event.type === "summarize"
            ) {
              if (!hasRefreshedProcessingLists && detectedPlatform !== "youtube") {
                hasRefreshedProcessingLists = true;
                await queryClient.invalidateQueries({ queryKey: ALL_VIDEO_SUMMARIES_QUERY_KEY });
                await queryClient.invalidateQueries({
                  queryKey: VIDEO_SUMMARIES_QUERY_KEY(notebookId),
                });
              }
            }

            if (event.type === "info") {
              setStreamInfo({
                title: event.title,
                uploaderName: event.uploader_name,
                durationSeconds: event.duration_seconds,
              });
              return;
            }

            if (
              event.type === "start" ||
              event.type === "subtitle" ||
              event.type === "asr" ||
              event.type === "summarize"
            ) {
              setProgressSteps((prev) => {
                const updated = prev.map((s) => ({ ...s, status: "done" as const }));
                return [...updated, { label: getStepLabel(event, t), status: "active" as const }];
              });
              return;
            }
            if (event.type === "done") {
              await queryClient.invalidateQueries({ queryKey: ALL_VIDEO_SUMMARIES_QUERY_KEY });
              await queryClient.invalidateQueries({
                queryKey: VIDEO_SUMMARIES_QUERY_KEY(notebookId),
              });
              await queryClient.invalidateQueries({
                queryKey: VIDEO_SUMMARY_QUERY_KEY(event.summary_id),
              });
              if (event.reused) {
                setProgressSteps([{ label: t(uiStrings.video.stepReused), status: "done" }]);
              } else {
                setProgressSteps((prev) => {
                  const updated = prev.map((s) => ({ ...s, status: "done" as const }));
                  return [...updated, { label: t(uiStrings.video.stepDone), status: "done" }];
                });
              }
              return;
            }
            if (event.type === "error") {
              if (event.error_code === "E_BILIBILI_AUTH" || isAuthError(event.message)) {
                setStreamError(t(uiStrings.video.authError));
                setIsAuthRelatedError(true);
              } else {
                setStreamError(getFriendlyErrorMessage(event, t));
              }
              if (detectedPlatform === "youtube") {
                await queryClient.invalidateQueries({ queryKey: ALL_VIDEO_SUMMARIES_QUERY_KEY });
                await queryClient.invalidateQueries({
                  queryKey: VIDEO_SUMMARIES_QUERY_KEY(notebookId),
                });
              }
              setProgressSteps([]);
            }
          },
        }
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleLogout = async () => {
    await logoutMutation.mutateAsync();
  };

  const platformStatus =
    detectedPlatform === "bilibili" ? (
      <div className="video-platform-status">
        <span className="chip">{t(uiStrings.video.platformBilibili)}</span>
        <span className="chip">
          {authQuery.data?.logged_in
            ? t(uiStrings.video.authConnected)
            : t(uiStrings.video.authDisconnected)}
        </span>
        {authQuery.data?.logged_in ? (
          <button className="btn btn-ghost btn-sm" type="button" onClick={() => void handleLogout()}>
            {t(uiStrings.video.logout)}
          </button>
        ) : (
          <button className="btn btn-ghost btn-sm" type="button" onClick={() => void handleStartLogin()}>
            {t(uiStrings.video.login)}
          </button>
        )}
      </div>
    ) : detectedPlatform === "youtube" ? (
      <div className="video-platform-status">
        <span className="chip">{t(uiStrings.video.platformYouTube)}</span>
        <span className="chip">{t(uiStrings.video.youtubeNoLogin)}</span>
        <span className="muted video-input-description">
          {t(uiStrings.video.youtubeLangHint)}
        </span>
      </div>
    ) : detectedPlatform === "unknown" ? (
      <span className="muted video-input-description">
        {t(uiStrings.video.unknownPlatformHint)}
      </span>
    ) : (
      <span className="muted video-input-description">
        {t(uiStrings.video.supportedPlatformsHint)}
      </span>
    );

  return (
    <div className="card stack-md video-input-card">
      <div className="video-input-header">
        <div className="stack-sm">
          <strong>{t(uiStrings.video.title)}</strong>
          <span className="muted video-input-description">
            {t(uiStrings.video.description)}
          </span>
        </div>
        {platformStatus}
      </div>

      <div className="video-input-form">
        <input
          className="input"
          style={{ flex: 1, minWidth: 0 }}
          placeholder={t(uiStrings.video.inputPlaceholder)}
          value={input}
          onChange={(event) => {
            setInput(event.target.value);
            setValidationError(null);
            setStreamError(null);
            setStreamInfo(null);
          }}
        />
        <button
          className="btn btn-sm"
          type="button"
          disabled={isSubmitting}
          onClick={() => void handleSummarize()}
        >
          {isSubmitting ? t(uiStrings.common.processing) : t(uiStrings.video.summarize)}
        </button>
      </div>

      {validationError ? (
        <span className="video-error-text">{validationError}</span>
      ) : null}

      {streamInfo ? (
        <div className="video-info-card">
          <strong className="video-info-title">{streamInfo.title}</strong>
          <div className="video-meta-row">
            {streamInfo.uploaderName ? <span className="chip">{streamInfo.uploaderName}</span> : null}
            {typeof streamInfo.durationSeconds === "number" ? (
              <span className="chip">{formatDuration(streamInfo.durationSeconds)}</span>
            ) : null}
          </div>
        </div>
      ) : null}

      {progressSteps.length > 0 ? (
        <div className="video-progress-list">
          {progressSteps.map((step, i) => (
            <div key={i} className="video-progress-item">
              {step.status === "done" ? (
                <span className="video-progress-done">✓</span>
              ) : (
                <span className="video-progress-pending" />
              )}
              <span className="muted">{step.label}</span>
            </div>
          ))}
        </div>
      ) : null}

      {streamError ? (
        <div className="row" style={{ gap: 8, alignItems: "center", flexWrap: "wrap" }}>
          <span className="video-error-text">{streamError}</span>
          {isAuthRelatedError && detectedPlatform === "bilibili" && !authQuery.data?.logged_in ? (
            <button
              className="btn btn-ghost btn-sm"
              type="button"
              style={{ fontSize: 12 }}
              onClick={() => void handleStartLogin()}
            >
              {t(uiStrings.video.login)}
            </button>
          ) : null}
        </div>
      ) : null}

      {loginDialogOpen ? (
        <div
          className="card"
          role="dialog"
          aria-label={t(uiStrings.video.loginDialogTitle)}
          style={{ padding: 16, borderStyle: "dashed" }}
        >
          <div className="stack-sm">
            <div className="row-between">
              <strong>{t(uiStrings.video.loginDialogTitle)}</strong>
              <button
                className="btn btn-ghost btn-sm"
                type="button"
                onClick={() => setLoginDialogOpen(false)}
              >
                {t(uiStrings.common.cancel)}
              </button>
            </div>
            <span className="muted">{loginDialogMessage}</span>
            {qrImageSrc ? (
              <Image
                src={qrImageSrc}
                alt={t(uiStrings.video.loginQrAlt)}
                width={180}
                height={180}
                unoptimized
                style={{ objectFit: "contain" }}
              />
            ) : null}
            {!qrImageSrc && qrUrl ? (
              <a href={qrUrl} target="_blank" rel="noreferrer" className="btn btn-ghost btn-sm">
                {t(uiStrings.video.openQrLink)}
              </a>
            ) : null}
          </div>
        </div>
      ) : null}
    </div>
  );
}
