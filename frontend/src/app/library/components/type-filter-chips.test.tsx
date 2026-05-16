import { describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { TypeFilterChips } from "@/app/library/components/type-filter-chips";
import { renderWithLang } from "@/test/test-utils";
import type { DocumentTypeGroup } from "@/lib/api/types";

describe("TypeFilterChips", () => {
  it("renders all 8 groups in English", () => {
    renderWithLang(
      <TypeFilterChips selected={new Set()} onToggle={() => {}} onClear={() => {}} />,
      { lang: "en" }
    );
    expect(screen.getByRole("button", { name: /Document \(PDF\)/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Word/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Slides/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /HTML/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Images/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Spreadsheet/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /E-book/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Text/i })).toBeInTheDocument();
  });

  it("renders Chinese labels when lang is zh", () => {
    renderWithLang(
      <TypeFilterChips selected={new Set()} onToggle={() => {}} onClear={() => {}} />,
      { lang: "zh" }
    );
    expect(screen.getByRole("button", { name: /幻灯片/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /电子书/ })).toBeInTheDocument();
  });

  it("marks selected chips as active via aria-pressed", () => {
    const selected = new Set<DocumentTypeGroup>(["slides"]);
    renderWithLang(
      <TypeFilterChips selected={selected} onToggle={() => {}} onClear={() => {}} />,
      { lang: "en" }
    );
    const slidesChip = screen.getByRole("button", { name: /Slides/i });
    expect(slidesChip.getAttribute("aria-pressed")).toBe("true");

    const wordChip = screen.getByRole("button", { name: /Word/i });
    expect(wordChip.getAttribute("aria-pressed")).toBe("false");
  });

  it("calls onToggle with the clicked group", async () => {
    const onToggle = vi.fn();
    renderWithLang(
      <TypeFilterChips selected={new Set()} onToggle={onToggle} onClear={() => {}} />,
      { lang: "en" }
    );
    await userEvent.click(screen.getByRole("button", { name: /Spreadsheet/i }));
    expect(onToggle).toHaveBeenCalledWith("sheet");
  });

  it("hides Clear button when nothing is selected", () => {
    renderWithLang(
      <TypeFilterChips selected={new Set()} onToggle={() => {}} onClear={() => {}} />,
      { lang: "en" }
    );
    expect(screen.queryByRole("button", { name: /Clear filters/i })).not.toBeInTheDocument();
  });

  it("shows Clear button and active count when there is a selection, and calls onClear", async () => {
    const onClear = vi.fn();
    renderWithLang(
      <TypeFilterChips
        selected={new Set<DocumentTypeGroup>(["slides", "word"])}
        onToggle={() => {}}
        onClear={onClear}
      />,
      { lang: "en" }
    );
    expect(screen.getByText(/2 selected/i)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /Clear filters/i }));
    expect(onClear).toHaveBeenCalledTimes(1);
  });
});
