import { describe, expect, it } from "vitest";

import {
  applyDagreLayout,
  buildReactFlowElements,
  mergeUserPositions,
} from "@/lib/diagram/reactflow-layout";

describe("applyDagreLayout", () => {
  it("places the root before its children from left to right", () => {
    const result = applyDagreLayout(
      [
        { id: "root", label: "Root" },
        { id: "child-a", label: "Child A" },
        { id: "child-b", label: "Child B" },
      ],
      [
        { source: "root", target: "child-a" },
        { source: "root", target: "child-b" },
      ]
    );

    expect(result).toHaveLength(3);
    const root = result.find((node) => node.id === "root");
    const childA = result.find((node) => node.id === "child-a");
    const childB = result.find((node) => node.id === "child-b");
    expect(root).toBeDefined();
    expect(childA).toBeDefined();
    expect(childB).toBeDefined();
    expect(root!.position.x).toBeLessThan(childA!.position.x);
    expect(root!.position.x).toBeLessThan(childB!.position.x);
  });
});

describe("mergeUserPositions", () => {
  it("overrides only matching node positions", () => {
    const merged = mergeUserPositions(
      [
        { id: "root", label: "Root", position: { x: 10, y: 20 } },
        { id: "child", label: "Child", position: { x: 110, y: 120 } },
      ],
      { root: { x: 24, y: 48 } }
    );

    expect(merged.find((node) => node.id === "root")?.position).toEqual({ x: 24, y: 48 });
    expect(merged.find((node) => node.id === "child")?.position).toEqual({ x: 110, y: 120 });
  });
});

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
