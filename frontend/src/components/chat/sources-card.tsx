"use client";

import { useState } from "react";

import { useLang } from "@/lib/hooks/useLang";
import { uiStrings } from "@/lib/i18n/strings";
import { NormalizedSource } from "@/lib/utils/sources";

type DocumentReferencesCardProps = {
  sources: NormalizedSource[];
  onOpenDocument: (documentId: string) => void;
};

type ToolResultsCardProps = {
  sources: NormalizedSource[];
};

export function DocumentReferencesCard({
  sources,
  onOpenDocument,
}: DocumentReferencesCardProps) {
  const { t, ti } = useLang();
  const [expanded, setExpanded] = useState(false);

  if (sources.length === 0) return null;

  const visibleSources = expanded ? sources : sources.slice(0, 3);

  return (
    <div className="card" style={{ padding: 12 }}>
      <div className="stack-sm">
        <span style={{ fontSize: 12, fontWeight: 600, color: "hsl(var(--muted-foreground))" }}>
          {t(uiStrings.sources.title)}
        </span>

        <div
          className="stack-sm"
          style={expanded ? { maxHeight: 240, overflowY: "auto", paddingRight: 2 } : undefined}
        >
          {visibleSources.map((source, index) => (
            (() => {
              const canOpen = Boolean(source.document_id);
              return (
            <button
              key={`${source.document_id}-${source.chunk_id}-${index}`}
              type="button"
              style={{
                display: "block",
                width: "100%",
                textAlign: "left",
                padding: "8px 10px",
                borderRadius: "calc(var(--radius) - 2px)",
                background: "transparent",
                border: "none",
                cursor: canOpen ? "pointer" : "default",
                opacity: canOpen ? 1 : 0.9,
                transition: "background 200ms ease-out",
              }}
              className="source-ref-btn"
              onClick={() => {
                if (!canOpen) return;
                onOpenDocument(source.document_id);
              }}
              onMouseEnter={(e) => {
                if (!canOpen) return;
                e.currentTarget.style.background = "hsl(var(--accent))";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = "transparent";
              }}
            >
              <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 2 }}>
                [{index + 1}] {source.title || source.document_id}
              </div>
              <div
                className="muted"
                style={{
                  fontSize: 12,
                  lineHeight: 1.5,
                  display: "-webkit-box",
                  WebkitLineClamp: 2,
                  WebkitBoxOrient: "vertical",
                  overflow: "hidden",
                }}
              >
                {source.text.slice(0, 120)}
              </div>
            </button>
              );
            })()
          ))}
        </div>

        {sources.length > 3 && (
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            style={{ alignSelf: "flex-start" }}
            onClick={() => setExpanded((prev) => !prev)}
          >
            {expanded ? t(uiStrings.common.collapse) : ti(uiStrings.sources.expandMore, { n: sources.length })}
          </button>
        )}
      </div>
    </div>
  );
}

export function ToolResultsCard({ sources }: ToolResultsCardProps) {
  const { t } = useLang();
  if (sources.length === 0) return null;

  return (
    <div
      className="card"
      style={{
        padding: 10,
        background: "hsl(var(--muted) / 0.35)",
        borderStyle: "dashed",
      }}
    >
      <div className="stack-sm">
        <span style={{ fontSize: 11, fontWeight: 600, color: "hsl(var(--muted-foreground))" }}>
          {t(uiStrings.sources.toolResults)}
        </span>
        {sources.slice(0, 3).map((source, index) => (
          <div
            key={`${source.document_id}-${source.chunk_id}-${index}`}
            style={{
              padding: "6px 8px",
              borderRadius: "calc(var(--radius) - 2px)",
              background: "hsl(var(--card))",
              border: "1px solid hsl(var(--border))",
            }}
          >
            <div
              style={{
                fontSize: 11,
                fontWeight: 600,
                lineHeight: 1.4,
                marginBottom: 2,
                color: "hsl(var(--foreground))",
              }}
            >
              [{index + 1}] {source.title || source.document_id}
            </div>
            <div
              className="muted"
              style={{
                fontSize: 11,
                lineHeight: 1.45,
                whiteSpace: "nowrap",
                overflow: "hidden",
                textOverflow: "ellipsis",
              }}
              title={source.text}
            >
              {source.text.slice(0, 80)}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
