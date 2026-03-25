import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { DocumentReferencesCard } from "@/components/chat/sources-card";
import { renderWithLang } from "@/test/test-utils";

const sources = [
  {
    document_id: "doc-1",
    chunk_id: "chunk-1",
    title: "来源 1",
    text: `${"A".repeat(140)}--FIRST-TAIL--`,
    score: 0.9,
  },
  {
    document_id: "doc-2",
    chunk_id: "chunk-2",
    title: "来源 2",
    text: `${"B".repeat(140)}--SECOND-TAIL--`,
    score: 0.8,
  },
];

describe("DocumentReferencesCard", () => {
  it("toggles popover on item click and closes on outside click", async () => {
    const user = userEvent.setup();

    renderWithLang(<DocumentReferencesCard sources={sources} />);

    expect(screen.queryByText("--FIRST-TAIL--")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /\[1\]/ }));
    expect(screen.getByText(/--FIRST-TAIL--/)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /\[1\]/ }));
    expect(screen.queryByText(/--FIRST-TAIL--/)).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /\[2\]/ }));
    expect(screen.getByText(/--SECOND-TAIL--/)).toBeInTheDocument();

    await user.click(document.body);
    expect(screen.queryByText(/--SECOND-TAIL--/)).not.toBeInTheDocument();
  });
});
