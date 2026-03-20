import { describe, expect, it } from "vitest";

import { buildReactFlowElements } from "@/lib/diagram/reactflow-layout";

describe("buildReactFlowElements", () => {
  it("uses saved positions when available and auto-layouts the remaining nodes", () => {
    const result = buildReactFlowElements(
      JSON.stringify({
        nodes: [
          { id: "root", label: "Root" },
          { id: "child-a", label: "Child A" },
          { id: "child-b", label: "Child B" },
        ],
        edges: [
          { source: "root", target: "child-a" },
          { source: "root", target: "child-b" },
        ],
      }),
      {
        root: { x: 24, y: 48 },
      }
    );

    expect(result).not.toBeNull();
    expect(result?.nodes).toHaveLength(3);
    expect(result?.edges).toHaveLength(2);
    expect(result?.nodes.find((node) => node.id === "root")?.position).toEqual({
      x: 24,
      y: 48,
    });
    expect(result?.nodes.find((node) => node.id === "child-a")?.position).not.toEqual({
      x: 0,
      y: 0,
    });
    expect(result?.nodes.find((node) => node.id === "child-b")?.position).not.toEqual({
      x: 0,
      y: 0,
    });
  });
});
