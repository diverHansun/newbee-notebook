"use client";

import { Background, Controls, ReactFlow } from "@xyflow/react";
import mermaid from "mermaid";
import { useEffect, useId, useMemo, useState } from "react";

import type { Diagram } from "@/lib/api/types";
import { buildReactFlowElements } from "@/lib/diagram/reactflow-layout";

type DiagramViewerProps = {
  diagram: Diagram;
  content: string;
};

export function DiagramViewer({ diagram, content }: DiagramViewerProps) {
  const mermaidId = useId().replace(/:/g, "-");
  const [mermaidSvg, setMermaidSvg] = useState("");
  const [mermaidPending, setMermaidPending] = useState(false);

  const reactFlowElements = useMemo(() => {
    if (diagram.format !== "reactflow_json") {
      return null;
    }
    return buildReactFlowElements(content, diagram.node_positions);
  }, [content, diagram.format, diagram.node_positions]);

  useEffect(() => {
    if (diagram.format !== "mermaid" || content.trim().length === 0) {
      setMermaidSvg("");
      setMermaidPending(false);
      return;
    }

    let active = true;
    const theme =
      typeof document !== "undefined" && document.documentElement.classList.contains("dark")
        ? "dark"
        : "default";

    setMermaidPending(true);
    mermaid.initialize({
      startOnLoad: false,
      securityLevel: "loose",
      theme,
    });

    mermaid
      .render(`diagram-${mermaidId}`, content)
      .then(({ svg }) => {
        if (!active) {
          return;
        }
        setMermaidSvg(svg);
        setMermaidPending(false);
      })
      .catch(() => {
        if (!active) {
          return;
        }
        setMermaidSvg("");
        setMermaidPending(false);
      });

    return () => {
      active = false;
    };
  }, [content, diagram.format, mermaidId]);

  if (diagram.format === "reactflow_json" && reactFlowElements) {
    return (
      <div
        data-testid="diagram-viewer-reactflow"
        style={{
          height: "100%",
          minHeight: 420,
          borderRadius: 16,
          border: "1px solid hsl(var(--border))",
          background:
            "linear-gradient(180deg, hsl(var(--background)) 0%, hsl(var(--secondary)) 100%)",
          overflow: "hidden",
        }}
      >
        <ReactFlow
          nodes={reactFlowElements.nodes}
          edges={reactFlowElements.edges}
          fitView
          proOptions={{ hideAttribution: true }}
          nodesDraggable={false}
          nodesConnectable={false}
          elementsSelectable={false}
          zoomOnDoubleClick={false}
        >
          <Background />
          <Controls showInteractive={false} />
        </ReactFlow>
      </div>
    );
  }

  if (diagram.format === "mermaid") {
    if (mermaidSvg.length > 0) {
      return (
        <div
          data-testid="diagram-viewer-mermaid"
          style={{
            minHeight: 240,
            borderRadius: 16,
            border: "1px solid hsl(var(--border))",
            background: "hsl(var(--card))",
            padding: 16,
            overflow: "auto",
          }}
          dangerouslySetInnerHTML={{ __html: mermaidSvg }}
        />
      );
    }

    if (mermaidPending) {
      return <span className="muted">Loading...</span>;
    }
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
