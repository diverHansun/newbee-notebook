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
    const onResolve = vi.fn();

    renderWithLang(
      <ConfirmationCard
        confirmation={{
          ...createPendingConfirmation(),
          responseOptions: ["once", "always_session", "always_persist", "reject"],
        }}
        onResolve={onResolve}
      />
    );

    expect(screen.getByText("Update note metadata.")).toBeInTheDocument();
    expect(screen.getByText("update_note")).toBeInTheDocument();
    expect(screen.getByText("note-1")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Allow once" }));
    fireEvent.click(screen.getByRole("button", { name: "Always allow in this session" }));
    fireEvent.click(screen.getByRole("button", { name: "Always allow in this notebook" }));
    fireEvent.click(screen.getByRole("button", { name: "Reject" }));

    expect(onResolve).toHaveBeenNthCalledWith(1, "once");
    expect(onResolve).toHaveBeenNthCalledWith(2, "always_session");
    expect(onResolve).toHaveBeenNthCalledWith(3, "always_persist");
    expect(onResolve).toHaveBeenNthCalledWith(4, "reject");
  });

  it("renders permission choices as a vertical list", () => {
    renderWithLang(
      <ConfirmationCard
        confirmation={{
          ...createPendingConfirmation(),
          responseOptions: ["once", "always_session", "always_persist", "reject"],
        }}
        onResolve={() => {}}
      />
    );

    const choiceList = screen.getByRole("list", { name: "Permission choices" });
    expect(choiceList).toHaveAttribute("data-layout", "vertical");
    expect(screen.getAllByRole("listitem")).toHaveLength(4);
  });

  it("renders a resolved status without action buttons", () => {
    renderWithLang(
      <ConfirmationCard
        confirmation={{ ...createPendingConfirmation(), status: "confirmed" }}
        onResolve={() => {}}
      />
    );

    expect(screen.getByText("Confirmed")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Allow once" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Reject" })).not.toBeInTheDocument();
  });
});
