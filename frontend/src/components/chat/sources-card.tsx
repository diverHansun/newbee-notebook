"use client";

import { NormalizedSource } from "@/lib/utils/sources";

type SourcesCardProps = {
  sources: NormalizedSource[];
  onOpenDocument: (documentId: string) => void;
};

export function SourcesCard({ sources, onOpenDocument }: SourcesCardProps) {
  if (sources.length === 0) return null;

  return (
    <div className="card" style={{ padding: 12 }}>
      <div className="stack-sm">
        <span style={{ fontSize: 12, fontWeight: 600, color: "hsl(var(--muted-foreground))" }}>
          引用来源
        </span>
        {sources.slice(0, 3).map((source, index) => (
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
              cursor: "pointer",
              transition: "background 200ms ease-out",
            }}
            className="source-ref-btn"
            onClick={() => onOpenDocument(source.document_id)}
            onMouseEnter={(e) => {
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
        ))}
        {sources.length > 3 && (
          <span className="muted" style={{ fontSize: 12, paddingLeft: 10 }}>
            展开更多（共 {sources.length} 条）
          </span>
        )}
      </div>
    </div>
  );
}
