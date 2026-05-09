import { fireEvent, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { PermissionRequestCard } from "@/components/chat/permission-request-card";
import type { PendingPermissionRequest } from "@/stores/chat-store";
import { renderWithLang } from "@/test/test-utils";

function createPendingPermissionRequest(): PendingPermissionRequest {
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

describe("PermissionRequestCard", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-03-19T00:00:00.000Z"));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("renders pending permission request details and resolves actions", async () => {
    const onResolve = vi.fn();

    renderWithLang(
      <PermissionRequestCard
        request={{
          ...createPendingPermissionRequest(),
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
      <PermissionRequestCard
        request={{
          ...createPendingPermissionRequest(),
          responseOptions: ["once", "always_session", "always_persist", "reject"],
        }}
        onResolve={() => {}}
      />
    );

    const choiceList = screen.getByRole("list", { name: "Permission choices" });
    expect(choiceList).toHaveAttribute("data-layout", "vertical");
    expect(screen.getAllByRole("listitem")).toHaveLength(4);
  });

  it("displays bash permission requests as shell without changing the raw request", () => {
    renderWithLang(
      <PermissionRequestCard
        request={{
          ...createPendingPermissionRequest(),
          toolName: "bash",
          description: "Agent requested to run bash",
          argsSummary: {
            command: "echo ok",
          },
        }}
        onResolve={() => {}}
      />
    );

    expect(screen.getByText("AI requested to run shell")).toBeInTheDocument();
    expect(screen.getByText("shell")).toBeInTheDocument();
    expect(screen.queryByText("bash")).toBeNull();
  });

  it("displays shell permission requests with shell wording", () => {
    renderWithLang(
      <PermissionRequestCard
        request={{
          ...createPendingPermissionRequest(),
          toolName: "shell",
          description: "Agent requested to run Bash",
          argsSummary: {
            command: "echo ok",
          },
        }}
        onResolve={() => {}}
      />
    );

    expect(screen.getByText("AI requested to run shell")).toBeInTheDocument();
    expect(screen.getByText("shell")).toBeInTheDocument();
    expect(screen.queryByText("Agent requested to run Bash")).toBeNull();
  });

  it("renders a resolved status without action buttons", () => {
    renderWithLang(
      <PermissionRequestCard
        request={{ ...createPendingPermissionRequest(), status: "confirmed" }}
        onResolve={() => {}}
      />
    );

    expect(screen.getByText("Allowed")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Allow once" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Reject" })).not.toBeInTheDocument();
  });
});
