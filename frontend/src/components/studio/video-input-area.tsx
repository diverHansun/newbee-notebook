"use client";

import Image from "next/image";
import { useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";

import { streamBilibiliQrLogin } from "@/lib/api/bilibili-auth";
import { summarizeVideoStream } from "@/lib/api/videos";
import {
  BILIBILI_AUTH_STATUS_QUERY_KEY,
  useBilibiliAuthStatus,
  useBilibiliLogout,
} from "@/lib/hooks/use-bilibili-auth";
import { ALL_VIDEO_SUMMARIES_QUERY_KEY, VIDEO_SUMMARIES_QUERY_KEY } from "@/lib/hooks/use-videos";
import { useLang } from "@/lib/hooks/useLang";
import { uiStrings } from "@/lib/i18n/strings";

type VideoInputAreaProps = {
  notebookId: string;
};

const BV_ID_PATTERN = /^BV[0-9A-Za-z]+$/i;
const BILIBILI_URL_PATTERN = /^https?:\/\/(?:www\.)?bilibili\.com\/video\/BV[0-9A-Za-z]+/i;

function isValidBilibiliInput(value: string): boolean {
  const trimmed = value.trim();
  return BV_ID_PATTERN.test(trimmed) || BILIBILI_URL_PATTERN.test(trimmed);
}

function getStepLabel(
  type: "start" | "subtitle" | "asr" | "summarize",
  t: (value: { zh: string; en: string }) => string
): string {
  switch (type) {
    case "start":
      return t(uiStrings.video.stepStart);
    case "subtitle":
      return t(uiStrings.video.stepSubtitle);
    case "asr":
      return t(uiStrings.video.stepAsr);
    case "summarize":
      return t(uiStrings.video.stepSummarize);
  }
}

export function VideoInputArea({ notebookId }: VideoInputAreaProps) {
  const { t } = useLang();
  const queryClient = useQueryClient();
  const authQuery = useBilibiliAuthStatus();
  const logoutMutation = useBilibiliLogout();

  const [input, setInput] = useState("");
  const [validationError, setValidationError] = useState<string | null>(null);
  const [streamError, setStreamError] = useState<string | null>(null);
  const [currentStep, setCurrentStep] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [loginDialogOpen, setLoginDialogOpen] = useState(false);
  const [loginDialogMessage, setLoginDialogMessage] = useState<string | null>(null);
  const [qrImageBase64, setQrImageBase64] = useState<string | null>(null);
  const [qrUrl, setQrUrl] = useState<string | null>(null);

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
    setCurrentStep(null);

    if (!isValidBilibiliInput(trimmedInput)) {
      setValidationError(t(uiStrings.video.invalidInput));
      return;
    }

    setIsSubmitting(true);
    try {
      await summarizeVideoStream(
        {
          url_or_bvid: trimmedInput,
          notebook_id: notebookId,
        },
        {
          onEvent: async (event) => {
            if (
              event.type === "start" ||
              event.type === "subtitle" ||
              event.type === "asr" ||
              event.type === "summarize"
            ) {
              if (!hasRefreshedProcessingLists) {
                hasRefreshedProcessingLists = true;
                await queryClient.invalidateQueries({ queryKey: ALL_VIDEO_SUMMARIES_QUERY_KEY });
                await queryClient.invalidateQueries({
                  queryKey: VIDEO_SUMMARIES_QUERY_KEY(notebookId),
                });
              }
              setCurrentStep(getStepLabel(event.type, t));
              return;
            }
            if (event.type === "done") {
              await queryClient.invalidateQueries({ queryKey: ALL_VIDEO_SUMMARIES_QUERY_KEY });
              await queryClient.invalidateQueries({
                queryKey: VIDEO_SUMMARIES_QUERY_KEY(notebookId),
              });
              setCurrentStep(null);
              return;
            }
            if (event.type === "error") {
              setStreamError(event.message);
              setCurrentStep(null);
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

  return (
    <div className="card stack-md" style={{ padding: 12 }}>
      <div className="row-between" style={{ gap: 8, alignItems: "center" }}>
        <div className="stack-sm">
          <strong>{t(uiStrings.video.title)}</strong>
          <span className="muted" style={{ fontSize: 12 }}>
            {t(uiStrings.video.description)}
          </span>
        </div>
        <div className="row" style={{ gap: 8 }}>
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
      </div>

      <div className="row" style={{ gap: 8, alignItems: "flex-start" }}>
        <input
          className="input"
          style={{ flex: 1 }}
          placeholder={t(uiStrings.video.inputPlaceholder)}
          value={input}
          onChange={(event) => setInput(event.target.value)}
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
        <span className="muted" style={{ color: "#b91c1c", fontSize: 12 }}>
          {validationError}
        </span>
      ) : null}
      {currentStep ? <span className="muted">{currentStep}</span> : null}
      {streamError ? (
        <span className="muted" style={{ color: "#b91c1c", fontSize: 12 }}>
          {streamError}
        </span>
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
