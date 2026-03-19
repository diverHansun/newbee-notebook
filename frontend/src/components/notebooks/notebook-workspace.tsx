"use client";

import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";

import { ChatPanel } from "@/components/chat/chat-panel";
import { ExplainCard } from "@/components/chat/explain-card";
import { AppShell } from "@/components/layout/app-shell";
import { DocumentReader } from "@/components/reader/document-reader";
import { SourcesPanel } from "@/components/sources/sources-panel";
import { StudioPanel } from "@/components/studio/studio-panel";
import { getNotebook } from "@/lib/api/notebooks";
import { MessageMode, NotebookDocumentItem } from "@/lib/api/types";
import { useChatSession } from "@/lib/hooks/useChatSession";
import { useLang } from "@/lib/hooks/useLang";
import { uiStrings } from "@/lib/i18n/strings";
import { useReaderStore } from "@/stores/reader-store";
import { useUiStore } from "@/stores/ui-store";

type NotebookWorkspaceProps = {
  notebookId: string;
};

function buildRagHint(
  documents: NotebookDocumentItem[],
  ti: ReturnType<typeof useLang>["ti"]
): string | null {
  const blocking = documents.filter((item) =>
    ["uploaded", "pending", "processing", "converted"].includes(item.status)
  );
  if (blocking.length === 0) return null;

  const counts = {
    uploaded: blocking.filter((d) => d.status === "uploaded").length,
    pending: blocking.filter((d) => d.status === "pending").length,
    processing: blocking.filter((d) => d.status === "processing").length,
    converted: blocking.filter((d) => d.status === "converted").length,
  };

  return ti(uiStrings.workspace.ragHint, {
    queued: counts.uploaded + counts.pending,
    processing: counts.processing,
    converted: counts.converted,
  });
}

export function NotebookWorkspace({ notebookId }: NotebookWorkspaceProps) {
  const { t, ti } = useLang();
  const notebookQuery = useQuery({
    queryKey: ["notebook", notebookId],
    queryFn: () => getNotebook(notebookId),
  });

  const [documents, setDocuments] = useState<NotebookDocumentItem[]>([]);
  const chat = useChatSession(notebookId);
  const readerStore = useReaderStore();
  const uiStore = useUiStore();

  const ragHint = useMemo(() => buildRagHint(documents, ti), [documents, ti]);
  const askBlocked = Boolean(ragHint);

  const openDocument = (documentId: string, markId?: string | null) => {
    readerStore.openDocument(documentId, markId);
    uiStore.setMainView("reader");
  };

  const sendByMode = async (
    text: string,
    mode: MessageMode,
    context?: { document_id: string; selected_text: string },
    sourceDocIds?: string[] | null
  ) => {
    await chat.sendMessage(text, mode, context, sourceDocIds);
  };

  const mainContent =
    uiStore.mainView === "reader" && readerStore.currentDocumentId ? (
      <DocumentReader
        documentId={readerStore.currentDocumentId}
        onBack={() => {
          readerStore.closeDocument();
          uiStore.setMainView("chat");
        }}
        onExplain={({ documentId, selectedText }) =>
          sendByMode(t(uiStrings.workspace.explainPrompt), "explain", {
            document_id: documentId,
            selected_text: selectedText,
          })
        }
        onConclude={({ documentId, selectedText }) =>
          sendByMode(t(uiStrings.workspace.concludePrompt), "conclude", {
            document_id: documentId,
            selected_text: selectedText,
          })
        }
      />
    ) : (
      <ChatPanel
        notebookId={notebookId}
        sessions={chat.sessions}
        currentSessionId={chat.currentSessionId}
        messages={chat.messages}
        mode={chat.currentMode}
        isStreaming={chat.isStreaming}
        askBlocked={askBlocked}
        ragHint={ragHint || undefined}
        onModeChange={chat.setMode}
        onSendMessage={(text, mode, sourceDocIds) => sendByMode(text, mode, undefined, sourceDocIds)}
        onCancel={chat.cancelStream}
        onSwitchSession={chat.switchSession}
        onCreateSession={chat.createSession}
        onDeleteSession={chat.deleteSession}
        onOpenDocument={openDocument}
        onResolveConfirmation={chat.resolveConfirmation}
      />
    );

  return (
    <AppShell
      title={notebookQuery.data?.title || notebookId}
      left={
        <SourcesPanel
          notebookId={notebookId}
          onOpenDocument={openDocument}
          onDocumentsUpdate={setDocuments}
        />
      }
      main={mainContent}
      right={<StudioPanel notebookId={notebookId} onOpenDocument={openDocument} />}
      mainOverlay={<ExplainCard card={chat.explainCard} />}
    />
  );
}
