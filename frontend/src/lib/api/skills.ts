import { apiFetch } from "@/lib/api/client";

export type SkillKind = "builtin" | "installed";

export type SkillCatalogItem = {
  name: string;
  command: string;
  description: string;
  enabled: boolean;
  kind: SkillKind;
  source: string;
  content_hash: string;
  path: string;
  scopes: string[];
  manageable: boolean;
  deletable: boolean;
  readonly_reason?: string | null;
};

export type SkillsListResponse = {
  skills: SkillCatalogItem[];
};

export type DeleteSkillResponse = {
  deleted: boolean;
  name: string;
};

export function listSkills() {
  return apiFetch<SkillsListResponse>("/skills");
}

export function toggleSkill(skillName: string, enabled: boolean) {
  return apiFetch<SkillCatalogItem>(`/skills/${encodeURIComponent(skillName)}/toggle`, {
    method: "POST",
    body: { enabled },
  });
}

export function deleteSkill(skillName: string) {
  return apiFetch<DeleteSkillResponse>(`/skills/${encodeURIComponent(skillName)}`, {
    method: "DELETE",
  });
}
