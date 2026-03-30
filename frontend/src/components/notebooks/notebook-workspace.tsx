"use client";

import { useEffect } from "react";

import { ChatPanel } from "@/components/chat/chat-panel";
import { ExplainCard } from "@/components/chat/explain-card";
import { AppShell } from "@/components/layout/app-shell";
import { DocumentReader } from "@/components/reader/document-reader";
import { SourcesPanel } from "@/components/sources/sources-panel";
import { StudioPanel } from "@/components/studio/studio-panel";
import { MessageMode } from "@/lib/api/types";
import { useChatSession } from "@/lib/hooks/useChatSession";
import { useLang } from "@/lib/hooks/useLang";
import { uiStrings } from "@/lib/i18n/strings";
import { useChatStore } from "@/stores/chat-store";
import { useReaderStore } from "@/stores/reader-store";
import { useUiStore } from "@/stores/ui-store";

type NotebookWorkspaceProps = {
  notebookId: string;
};

export function NotebookWorkspace({ notebookId }: NotebookWorkspaceProps) {
  const { t } = useLang();
  const chat = useChatSession(notebookId);
  const readerStore = useReaderStore();
  const uiStore = useUiStore();

  useEffect(() => {
    readerStore.closeDocument();
    uiStore.setMainView("chat");
    useChatStore.getState().setCurrentSessionId(null);
    useChatStore.getState().clearMessages();
  }, [notebookId]); // eslint-disable-line react-hooks/exhaustive-deps

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
      left={
        <SourcesPanel
          notebookId={notebookId}
          onOpenDocument={openDocument}
        />
      }
      main={mainContent}
      right={<StudioPanel notebookId={notebookId} onOpenDocument={openDocument} />}
      mainOverlay={<ExplainCard card={chat.explainCard} />}
    />
  );
}
