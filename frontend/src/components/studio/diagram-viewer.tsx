"use client";

import { forwardRef, useImperativeHandle, useRef } from "react";

import type { Diagram } from "@/lib/api/types";
import { MermaidRenderer } from "@/components/studio/mermaid-renderer";
import {
  ReactFlowRenderer,
  type DiagramExportHandle,
} from "@/components/studio/reactflow-renderer";

type DiagramViewerProps = {
  diagram: Diagram;
  content: string;
};

export const DiagramViewer = forwardRef<DiagramExportHandle, DiagramViewerProps>(
  function DiagramViewer({ diagram, content }, ref) {
    const innerRef = useRef<DiagramExportHandle>(null);

    useImperativeHandle(ref, () => ({
      exportImage: (filename: string) =>
        innerRef.current?.exportImage(filename) ?? Promise.resolve(),
    }));

    if (diagram.format === "reactflow_json") {
      return <ReactFlowRenderer ref={innerRef} diagram={diagram} content={content} />;
    }

    if (diagram.format === "mermaid") {
      return <MermaidRenderer ref={innerRef} syntax={content} />;
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
);
