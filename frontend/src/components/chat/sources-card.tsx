"use client";

import { useEffect, useRef, useState } from "react";

import { useLang } from "@/lib/hooks/useLang";
import { uiStrings } from "@/lib/i18n/strings";
import { NormalizedSource } from "@/lib/utils/sources";

type DocumentReferencesCardProps = {
  sources: NormalizedSource[];
};

export function DocumentReferencesCard({ sources }: DocumentReferencesCardProps) {
  const { t } = useLang();
  const containerRef = useRef<HTMLDivElement>(null);
  const [expandedIndex, setExpandedIndex] = useState<number | null>(null);

  // Reset expandedIndex if it points beyond current sources
  useEffect(() => {
    if (expandedIndex === null) return;
    if (expandedIndex >= sources.length) {
      setExpandedIndex(null);
    }
  }, [expandedIndex, sources.length]);

  // Close popover on outside click
  useEffect(() => {
    if (expandedIndex === null) return;

    const handlePointerDown = (event: PointerEvent) => {
      const target = event.target as Node | null;
      if (!target) return;
      if (containerRef.current && !containerRef.current.contains(target)) {
        setExpandedIndex(null);
      }
    };

    document.addEventListener("pointerdown", handlePointerDown);
    return () => document.removeEventListener("pointerdown", handlePointerDown);
  }, [expandedIndex]);

  if (sources.length === 0) return null;

  const expandedSource = expandedIndex === null ? null : sources[expandedIndex] || null;

  return (
    <div ref={containerRef} className="card source-ref-card" style={{ padding: 12, position: "relative" }}>
      <div className="stack-sm">
        <span style={{ fontSize: 12, fontWeight: 600, color: "hsl(var(--muted-foreground))" }}>
          {t(uiStrings.sources.title)}
        </span>

        {/* All sources in a fixed-height scroll container — use mouse wheel to browse */}
        <div
          className="stack-sm"
          style={{ maxHeight: 230, overflowY: "auto", paddingRight: 2 }}
        >
          {sources.map((source, index) => (
            <button
              key={`${source.document_id}-${source.chunk_id}-${index}`}
              type="button"
              aria-expanded={expandedIndex === index}
              aria-controls={expandedIndex === index ? "source-ref-popover" : undefined}
              style={{
                display: "block",
                width: "100%",
                textAlign: "left",
                padding: "8px 10px",
                borderRadius: "calc(var(--radius) - 2px)",
                border: "none",
                cursor: "pointer",
              }}
              className={`source-ref-btn${expandedIndex === index ? " is-active" : ""}`}
              onClick={() => {
                setExpandedIndex((prev) => (prev === index ? null : index));
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
          ))}
        </div>

        {/* source detail popover */}
        {expandedSource && (
          <div
            id="source-ref-popover"
            role="dialog"
            aria-label="引用全文"
            className="source-ref-popover"
            style={{
              position: "absolute",
              left: 12,
              right: 12,
              zIndex: 10,
            }}
          >
            <div className="source-ref-popover-head">
              <strong style={{ fontSize: 12 }}>
                [{(expandedIndex ?? 0) + 1}] {expandedSource.title || expandedSource.document_id}
              </strong>
              <button
                type="button"
                className="btn btn-ghost btn-sm"
                onClick={() => setExpandedIndex(null)}
              >
                {t(uiStrings.common.collapse)}
              </button>
            </div>
            <p className="source-ref-popover-text" style={{ fontSize: 12, lineHeight: 1.7, margin: 0, whiteSpace: "pre-wrap" }}>
              {expandedSource.text || "(empty source text)"}
            </p>
            {expandedSource.text.length > 1000 && (
              <p className="muted" style={{ fontSize: 11, marginTop: 6, marginBottom: 0 }}>
                全文共 {expandedSource.text.length} 字
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
