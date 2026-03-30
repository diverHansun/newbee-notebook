"use client";

import { SourceList } from "@/components/sources/source-list";

type SourcesPanelProps = {
  notebookId: string;
  onOpenDocument: (documentId: string) => void;
};

export function SourcesPanel({ notebookId, onOpenDocument }: SourcesPanelProps) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16, height: "100%" }}>
      <SourceList
        notebookId={notebookId}
        onOpenDocument={onOpenDocument}
      />
    </div>
  );
}
