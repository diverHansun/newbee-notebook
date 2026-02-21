"use client";

import { NotebookDocumentItem } from "@/lib/api/types";
import { SourceList } from "@/components/sources/source-list";

type SourcesPanelProps = {
  notebookId: string;
  onOpenDocument: (documentId: string) => void;
  onDocumentsUpdate?: (documents: NotebookDocumentItem[]) => void;
};

export function SourcesPanel({ notebookId, onOpenDocument, onDocumentsUpdate }: SourcesPanelProps) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16, height: "100%" }}>
      <SourceList
        notebookId={notebookId}
        onOpenDocument={onOpenDocument}
        onDocumentsUpdate={onDocumentsUpdate}
      />
    </div>
  );
}
