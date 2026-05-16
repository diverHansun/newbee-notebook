import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";

import { DocumentTypeBadge } from "@/app/library/components/document-type-badge";
import { renderWithLang } from "@/test/test-utils";

describe("DocumentTypeBadge", () => {
  it("uppercases the content type label", () => {
    renderWithLang(<DocumentTypeBadge contentType="pdf" />);
    expect(screen.getByText("PDF")).toBeInTheDocument();
  });

  it("renders pptx as PPTX", () => {
    renderWithLang(<DocumentTypeBadge contentType="pptx" />);
    expect(screen.getByText("PPTX")).toBeInTheDocument();
  });

  it("provides an English aria-label with the type", () => {
    renderWithLang(<DocumentTypeBadge contentType="docx" />, { lang: "en" });
    expect(screen.getByLabelText("File type: DOCX")).toBeInTheDocument();
  });

  it("provides a Chinese aria-label when lang is zh", () => {
    renderWithLang(<DocumentTypeBadge contentType="epub" />, { lang: "zh" });
    expect(screen.getByLabelText("文件类型：EPUB")).toBeInTheDocument();
  });

  it("uses the localized accessible label as the tooltip title", () => {
    renderWithLang(<DocumentTypeBadge contentType="epub" />, { lang: "en" });

    const badge = screen.getByText("EPUB");
    const ariaLabel = badge.getAttribute("aria-label");

    expect(ariaLabel).toBeTruthy();
    expect(badge).toHaveAttribute("title", ariaLabel as string);
  });

  it("does not crash on empty or unknown content type", () => {
    renderWithLang(<DocumentTypeBadge contentType="" />);
    expect(screen.getByText("—")).toBeInTheDocument();
  });
});
