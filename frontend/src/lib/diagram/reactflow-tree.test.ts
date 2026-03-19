import { describe, expect, it } from "vitest";

import { parseReactFlowTree } from "@/lib/diagram/reactflow-tree";

describe("parseReactFlowTree", () => {
  it("builds a tree from reactflow_json content", () => {
    const tree = parseReactFlowTree(
      JSON.stringify({
        nodes: [
          { id: "root", label: "Root" },
          { id: "a", label: "A" },
          { id: "b", label: "B" },
        ],
        edges: [
          { source: "root", target: "a" },
          { source: "root", target: "b" },
        ],
      })
    );

    expect(tree).toHaveLength(1);
    expect(tree[0].label).toBe("Root");
    expect(tree[0].children.map((item) => item.label)).toEqual(["A", "B"]);
  });

  it("returns empty array for invalid payload", () => {
    expect(parseReactFlowTree('{"nodes":"x"}')).toEqual([]);
  });
});
