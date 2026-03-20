"use client";

import type { Diagram } from "@/lib/api/types";
import { MermaidRenderer } from "@/components/studio/mermaid-renderer";
import { ReactFlowRenderer } from "@/components/studio/reactflow-renderer";

type DiagramViewerProps = {
  diagram: Diagram;
  content: string;
};

export function DiagramViewer({ diagram, content }: DiagramViewerProps) {
  if (diagram.format === "reactflow_json") {
    return <ReactFlowRenderer diagram={diagram} content={content} />;
  }

  if (diagram.format === "mermaid") {
    return <MermaidRenderer syntax={content} />;
  }

  return (
    <pre
      style={{
        margin: 0,
        whiteSpace: "pre-wrap",
        wordBreak: "break-word",
        fontFamily: "\"Cascadia Code\", monospace",
        fontSize: 12,
        lineHeight: 1.5,
      }}
    >
      {content}
    </pre>
  );
}
