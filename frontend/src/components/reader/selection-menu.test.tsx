import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SelectionMenu } from "@/components/reader/selection-menu";
import { useReaderStore } from "@/stores/reader-store";
import { renderWithLang } from "@/test/test-utils";

describe("SelectionMenu", () => {
  beforeEach(() => {
    useReaderStore.setState({
      currentDocumentId: "doc-1",
      selection: {
        documentId: "doc-1",
        selectedText: "Marked text",
      },
      isSelecting: false,
      isTocOpen: true,
      isMenuVisible: true,
      menuPosition: { top: 12, left: 24 },
    });
  });

  it("invokes the mark callback with the current selection", async () => {
    const user = userEvent.setup();
    const onMark = vi.fn();

    renderWithLang(
      <SelectionMenu
        onExplain={() => {}}
        onConclude={() => {}}
        onMark={onMark}
      />
    );

    await user.click(screen.getByRole("button", { name: /bookmark/i }));

    expect(onMark).toHaveBeenCalledWith({
      documentId: "doc-1",
      selectedText: "Marked text",
    });
  });
});
