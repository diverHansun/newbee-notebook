import { apiFetch } from "@/lib/api/client";
import type { EffectivePolicy, PolicyPreferenceUpdate } from "@/lib/api/types";

export function getEffectivePolicy(
  notebookId: string,
  sessionId?: string | null
): Promise<EffectivePolicy> {
  const query = sessionId
    ? `?session_id=${encodeURIComponent(sessionId)}`
    : "";
  return apiFetch<EffectivePolicy>(
    `/policy/notebooks/${encodeURIComponent(notebookId)}/effective${query}`
  );
}

export function updatePolicyPreference(
  notebookId: string,
  update: PolicyPreferenceUpdate
): Promise<EffectivePolicy> {
  return apiFetch<EffectivePolicy>(
    `/policy/notebooks/${encodeURIComponent(notebookId)}`,
    {
      method: "PUT",
      body: update,
    }
  );
}
