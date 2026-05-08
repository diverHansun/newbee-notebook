import { fireEvent, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { PolicySelector } from "@/components/chat/policy-selector";
import type { EffectivePolicy } from "@/lib/api/types";
import { renderWithLang } from "@/test/test-utils";

const defaultPolicy: EffectivePolicy = {
  notebook_id: "nb-1",
  session_id: "session-1",
  policy: "default",
  source: "default",
};

describe("PolicySelector", () => {
  it("switches from default permission to session full access", () => {
    const onChange = vi.fn();

    renderWithLang(<PolicySelector policy={defaultPolicy} onChange={onChange} />);

    fireEvent.click(screen.getByRole("button", { name: "Agent permission policy" }));
    fireEvent.click(screen.getByRole("menuitem", { name: /Full access permission/i }));

    expect(onChange).toHaveBeenCalledWith({
      scope: "session",
      session_id: "session-1",
      policy: "yolo",
    });
  });

  it("switches notebook full access back to default by clearing notebook scope", () => {
    const onChange = vi.fn();

    renderWithLang(
      <PolicySelector
        policy={{
          ...defaultPolicy,
          policy: "yolo",
          source: "notebook",
        }}
        onChange={onChange}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "Agent permission policy" }));
    fireEvent.click(screen.getByRole("menuitem", { name: /Default permission/i }));

    expect(onChange).toHaveBeenCalledWith({
      scope: "notebook",
      session_id: "session-1",
      policy: "default",
    });
  });

  it("does not emit a session full access update without a session id", () => {
    const onChange = vi.fn();

    renderWithLang(
      <PolicySelector
        policy={{
          ...defaultPolicy,
          session_id: null,
        }}
        onChange={onChange}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "Agent permission policy" }));
    fireEvent.click(screen.getByRole("menuitem", { name: /Full access permission/i }));

    expect(onChange).not.toHaveBeenCalled();
  });
});
