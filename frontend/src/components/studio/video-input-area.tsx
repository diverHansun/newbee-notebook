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
import { ALL_VIDEO_SUMMARIES_QUERY_KEY, VIDEO_SUMMARIES_QUERY_KEY, VIDEO_SUMMARY_QUERY_KEY } from "@/lib/hooks/use-videos";
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

type StepType = "start" | "subtitle" | "asr" | "summarize";

function getStepLabel(
  type: StepType,
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

function isAuthError(message: string): boolean {
  const lower = message.toLowerCase();
  return (
    lower.includes("credential") ||
    lower.includes("sessdata") ||
    lower.includes("authenticationerror") ||
    lower.includes("未提供")
  );
}

type ProgressEntry = {
  label: string;
  status: "done" | "active";
};

export function VideoInputArea({ notebookId }: VideoInputAreaProps) {
  const { t } = useLang();
  const queryClient = useQueryClient();
  const authQuery = useBilibiliAuthStatus();
  const logoutMutation = useBilibiliLogout();

  const [input, setInput] = useState("");
  const [validationError, setValidationError] = useState<string | null>(null);
  const [streamError, setStreamError] = useState<string | null>(null);
  const [isAuthRelatedError, setIsAuthRelatedError] = useState(false);
  const [progressSteps, setProgressSteps] = useState<ProgressEntry[]>([]);
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
    setIsAuthRelatedError(false);
    setProgressSteps([]);

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
              setProgressSteps((prev) => {
                const updated = prev.map((s) => ({ ...s, status: "done" as const }));
                return [...updated, { label: getStepLabel(event.type, t), status: "active" as const }];
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
                setStreamError(event.message);
              }
              setProgressSteps((prev) => prev.map((s) => ({ ...s, status: "done" as const })));
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
      {progressSteps.length > 0 ? (
        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          {progressSteps.map((step, i) => (
            <div key={i} style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13 }}>
              {step.status === "done" ? (
                <span style={{ color: "#16a34a", fontWeight: 600, width: 14, textAlign: "center" }}>✓</span>
              ) : (
                <span
                  style={{
                    display: "inline-block",
                    width: 14,
                    height: 14,
                    border: "2px solid currentColor",
                    borderTopColor: "transparent",
                    borderRadius: "50%",
                    animation: "thinking-spin 0.8s linear infinite",
                  }}
                />
              )}
              <span className="muted">{step.label}</span>
            </div>
          ))}
        </div>
      ) : null}
      {streamError ? (
        <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
          <span className="muted" style={{ color: "#b91c1c", fontSize: 12 }}>
            {streamError}
          </span>
          {isAuthRelatedError && !authQuery.data?.logged_in ? (
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
