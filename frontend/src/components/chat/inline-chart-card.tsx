"use client";

import { useMemo, useRef, useState } from "react";

import { EChartsRenderer } from "@/components/studio/echarts-renderer";
import type { DiagramExportHandle } from "@/components/studio/reactflow-renderer";
import { useCreateDiagram } from "@/lib/hooks/use-diagrams";
import { useLang } from "@/lib/hooks/useLang";
import { uiStrings } from "@/lib/i18n/strings";

type SaveStatus = "idle" | "saving" | "saved" | "error";

type InlineChartCardProps = {
  rawContent: string;
  notebookId: string;
};

const CHART_HEIGHT = 320;

function deriveTitle(rawContent: string, fallback: string): string {
  try {
    const parsed = JSON.parse(rawContent) as { title?: unknown };
    if (parsed && typeof parsed === "object" && parsed.title) {
      const titleObj = parsed.title as { text?: unknown };
      if (typeof titleObj.text === "string" && titleObj.text.trim()) {
        return titleObj.text.trim();
      }
    }
  } catch {
    // fall through to fallback
  }
  const now = new Date();
  const pad = (n: number) => String(n).padStart(2, "0");
  const stamp = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())} ${pad(
    now.getHours()
  )}:${pad(now.getMinutes())}`;
  return `${fallback} - ${stamp}`;
}

function isContentParseable(rawContent: string): boolean {
  const trimmed = rawContent.trim();
  if (!trimmed) return false;
  try {
    const parsed = JSON.parse(trimmed) as unknown;
    return Boolean(parsed && typeof parsed === "object" && !Array.isArray(parsed));
  } catch {
    return false;
  }
}

function SaveIcon({ saved }: { saved: boolean }) {
  if (saved) {
    return (
      <svg
        width="16"
        height="16"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2.4"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
      >
        <polyline points="20 6 9 17 4 12" />
      </svg>
    );
  }
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
      <polyline points="7 10 12 15 17 10" />
      <line x1="12" y1="15" x2="12" y2="3" />
    </svg>
  );
}

export function InlineChartCard({ rawContent, notebookId }: InlineChartCardProps) {
  const { t, ti } = useLang();
  const [status, setStatus] = useState<SaveStatus>("idle");
  const [errorDetail, setErrorDetail] = useState<string>("");
  const rendererRef = useRef<DiagramExportHandle>(null);
  const createDiagramMutation = useCreateDiagram(notebookId);

  const parseable = useMemo(() => isContentParseable(rawContent), [rawContent]);
  const derivedTitle = useMemo(
    () => deriveTitle(rawContent, t(uiStrings.inlineChart.titleFallback)),
    [rawContent, t]
  );

  const isSaved = status === "saved";
  const isInflight = status === "saving";
  const buttonDisabled = isSaved || isInflight || !parseable;

  const saveLabel = isSaved
    ? t(uiStrings.inlineChart.saved)
    : isInflight
      ? t(uiStrings.inlineChart.saving)
      : t(uiStrings.inlineChart.saveToStudio);

  const handleSave = async () => {
    if (buttonDisabled) return;
    setStatus("saving");
    setErrorDetail("");
    try {
      await createDiagramMutation.mutateAsync({
        title: derivedTitle,
        diagram_type: "echarts",
        content: rawContent,
      });
      setStatus("saved");
    } catch (err) {
      setStatus("error");
      setErrorDetail((err as Error)?.message || "");
    }
  };

  return (
    <div
      className="card inline-chart-card"
      data-testid="inline-chart-card"
      data-save-status={status}
      style={{
        padding: 0,
        overflow: "hidden",
        marginTop: 8,
        marginBottom: 8,
      }}
    >
      <div
        className="inline-chart-toolbar"
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 8,
          padding: "8px 12px",
          borderBottom: "1px solid hsl(var(--border))",
          fontSize: 12,
        }}
      >
        <span
          className="inline-chart-title"
          style={{
            fontWeight: 500,
            color: "hsl(var(--foreground))",
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
            minWidth: 0,
          }}
          title={derivedTitle}
        >
          {derivedTitle}
        </span>
        <button
          type="button"
          className="btn btn-ghost btn-sm"
          aria-label={saveLabel}
          title={saveLabel}
          disabled={buttonDisabled}
          onClick={() => void handleSave()}
          data-testid="inline-chart-save-button"
          style={{
            padding: "4px 6px",
            color: isSaved ? "hsl(150, 50%, 45%)" : undefined,
            opacity: !parseable ? 0.4 : 1,
          }}
        >
          <SaveIcon saved={isSaved} />
        </button>
      </div>

      {parseable ? (
        <div style={{ padding: 12 }}>
          <EChartsRenderer ref={rendererRef} content={rawContent} height={CHART_HEIGHT} />
        </div>
      ) : (
        <div
          className="muted"
          data-testid="inline-chart-loading"
          style={{
            padding: 24,
            textAlign: "center",
            fontSize: 12,
            color: "hsl(var(--muted-foreground))",
          }}
        >
          {t(uiStrings.inlineChart.loading)}
        </div>
      )}

      {status === "error" ? (
        <div
          className="inline-chart-error"
          data-testid="inline-chart-error"
          style={{
            padding: "8px 12px",
            borderTop: "1px solid hsl(var(--border))",
            fontSize: 12,
            color: "hsl(0, 70%, 50%)",
          }}
        >
          {ti(uiStrings.inlineChart.saveFailed, { detail: errorDetail || "" })}
        </div>
      ) : null}
    </div>
  );
}
