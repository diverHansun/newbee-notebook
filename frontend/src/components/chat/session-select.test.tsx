import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { SessionSelect } from "@/components/chat/session-select";
import type { Session } from "@/lib/api/types";
import { renderWithLang } from "@/test/test-utils";

const sessions: Session[] = Array.from({ length: 12 }, (_, index) => ({
  session_id: `session-${index + 1}`,
  notebook_id: "nb-1",
  title: `Session ${index + 1}`,
  message_count: index,
  include_ec_context: false,
  created_at: "2026-03-19T00:00:00.000Z",
  updated_at: "2026-03-19T00:00:00.000Z",
}));

describe("SessionSelect", () => {
  it("opens a scrollable listbox and switches sessions when an option is clicked", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();

    renderWithLang(
      <SessionSelect
        sessions={sessions}
        currentSessionId="session-6"
        onChange={onChange}
      />,
      { lang: "en" }
    );

    expect(screen.getByRole("button", { name: "Session 6" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Session 6" }));

    const listbox = screen.getByRole("listbox", { name: "Select session" });
    expect(listbox).toHaveStyle({ maxHeight: "320px", overflowY: "auto" });
    expect(screen.getByRole("option", { name: "Session 4" })).toBeInTheDocument();

    await user.click(screen.getByRole("option", { name: "Session 4" }));

    expect(onChange).toHaveBeenCalledWith("session-4");
    expect(screen.queryByRole("listbox", { name: "Select session" })).not.toBeInTheDocument();
  });

  it("closes the open listbox when clicking outside", async () => {
    const user = userEvent.setup();

    renderWithLang(
      <div>
        <SessionSelect sessions={sessions} currentSessionId="session-2" onChange={() => {}} />
        <button type="button">Outside</button>
      </div>,
      { lang: "en" }
    );

    await user.click(screen.getByRole("button", { name: "Session 2" }));
    expect(screen.getByRole("listbox", { name: "Select session" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Outside" }));

    expect(screen.queryByRole("listbox", { name: "Select session" })).not.toBeInTheDocument();
  });
});
