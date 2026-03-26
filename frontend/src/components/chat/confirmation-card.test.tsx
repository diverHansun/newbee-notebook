import { fireEvent, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ConfirmationCard } from "@/components/chat/confirmation-card";
import type { PendingConfirmation } from "@/stores/chat-store";
import { renderWithLang } from "@/test/test-utils";

function createPendingConfirmation(): PendingConfirmation {
  return {
    requestId: "req-1",
    toolName: "update_note",
    actionType: "update",
    targetType: "note",
    argsSummary: {
      note_id: "note-1",
    },
    description: "Update note metadata.",
    status: "pending",
    expiresAt: Date.parse("2026-03-19T00:03:00.000Z"),
  };
}

describe("ConfirmationCard", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-03-19T00:00:00.000Z"));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("renders pending confirmation details and resolves actions", async () => {
    const onConfirm = vi.fn();
    const onReject = vi.fn();

    renderWithLang(
      <ConfirmationCard
        confirmation={createPendingConfirmation()}
        onConfirm={onConfirm}
        onReject={onReject}
      />
    );

    expect(screen.getByText("Update note")).toBeInTheDocument();
    expect(screen.getByText("note-1")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Confirm" }));
    fireEvent.click(screen.getByRole("button", { name: "Reject" }));

    expect(onConfirm).toHaveBeenCalledTimes(1);
    expect(onReject).toHaveBeenCalledTimes(1);
  });

  it("renders a resolved status without action buttons", () => {
    renderWithLang(
      <ConfirmationCard
        confirmation={{ ...createPendingConfirmation(), status: "confirmed" }}
        onConfirm={() => {}}
        onReject={() => {}}
      />
    );

    expect(screen.getByText("Confirmed")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Confirm" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Reject" })).not.toBeInTheDocument();
  });
});
