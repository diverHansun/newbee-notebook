import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const { mermaidRender, mermaidInitialize } = vi.hoisted(() => ({
  mermaidRender: vi.fn(async () => ({ svg: "<svg><text>Mermaid Diagram</text></svg>" })),
  mermaidInitialize: vi.fn(),
}));

vi.mock("mermaid", () => ({
  default: {
    initialize: mermaidInitialize,
    render: mermaidRender,
  },
}));

import { MermaidRenderer } from "@/components/studio/mermaid-renderer";

describe("MermaidRenderer", () => {
  it("renders mermaid syntax into svg markup", async () => {
    render(<MermaidRenderer syntax={"flowchart TD\nA[Notebook] --> B[Diagram]"} />);

    await waitFor(() => {
      expect(mermaidRender).toHaveBeenCalled();
    });

    expect(screen.getByText("Mermaid Diagram")).toBeInTheDocument();
  });

  it("supports zoom controls for mermaid view", async () => {
    render(<MermaidRenderer syntax={"flowchart TD\nA[Notebook] --> B[Diagram]"} />);

    await waitFor(() => {
      expect(screen.getByText("Mermaid Diagram")).toBeInTheDocument();
    });

    const canvas = screen.getByTestId("diagram-mermaid-canvas");
    expect(canvas.getAttribute("style")).toContain("scale(1)");

    fireEvent.click(screen.getByRole("button", { name: /zoom in/i }));
    expect(canvas.getAttribute("style")).toContain("scale(1.1)");

    fireEvent.click(screen.getByRole("button", { name: /reset view/i }));
    expect(canvas.getAttribute("style")).toContain("scale(1)");
  });
});
