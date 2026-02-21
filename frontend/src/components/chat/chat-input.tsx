"use client";

import { FormEvent, useState } from "react";

type ChatInputProps = {
  mode: "chat" | "ask";
  isStreaming: boolean;
  askBlocked: boolean;
  onModeChange: (mode: "chat" | "ask") => void;
  onSend: (text: string, mode: "chat" | "ask") => void;
  onCancel: () => void;
};

export function ChatInput({
  mode,
  isStreaming,
  askBlocked,
  onModeChange,
  onSend,
  onCancel,
}: ChatInputProps) {
  const [input, setInput] = useState("");

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const content = input.trim();
    if (!content || isStreaming) return;
    if (mode === "ask" && askBlocked) return;
    onSend(content, mode);
    setInput("");
  };

  return (
    <form
      onSubmit={submit}
      style={{
        padding: "12px 16px",
        display: "flex",
        gap: 8,
        alignItems: "flex-end",
      }}
    >
      {/* Mode selector */}
      <div style={{ display: "flex", flexDirection: "column", gap: 4, flexShrink: 0 }}>
        <select
          className="select"
          style={{ width: 90 }}
          value={mode}
          onChange={(event) => onModeChange(event.target.value as "chat" | "ask")}
          disabled={isStreaming}
        >
          <option value="chat">Chat</option>
          <option value="ask">Ask</option>
        </select>
        {mode === "ask" && askBlocked && (
          <span className="badge badge-failed" style={{ fontSize: 10 }}>
            RAG 不可用
          </span>
        )}
      </div>

      {/* Text input */}
      <textarea
        className="textarea"
        style={{
          flex: 1,
          minHeight: 44,
          maxHeight: 120,
          resize: "none",
        }}
        placeholder={mode === "ask" ? "输入问题（基于文档检索）..." : "输入消息..."}
        value={input}
        onChange={(event) => setInput(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            submit(event);
          }
        }}
      />

      {/* Send / Cancel */}
      {isStreaming ? (
        <button className="btn btn-destructive" type="button" onClick={onCancel} style={{ flexShrink: 0 }}>
          取消
        </button>
      ) : (
        <button
          className="btn btn-primary"
          type="submit"
          disabled={!input.trim()}
          style={{ flexShrink: 0 }}
        >
          发送
        </button>
      )}
    </form>
  );
}
