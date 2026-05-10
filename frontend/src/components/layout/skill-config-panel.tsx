"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  deleteSkill,
  listSkills,
  toggleSkill,
  type SkillCatalogItem,
} from "@/lib/api/skills";
import { useLang } from "@/lib/hooks/useLang";
import { uiStrings } from "@/lib/i18n/strings";

function SkillBadge({ children }: { children: string }) {
  return <span className="control-panel-skill-badge">{children}</span>;
}

function SkillCard({
  skill,
  pending,
  onToggle,
  onDelete,
}: {
  skill: SkillCatalogItem;
  pending: boolean;
  onToggle: (skill: SkillCatalogItem) => void;
  onDelete: (skill: SkillCatalogItem) => void;
}) {
  const { t, ti } = useLang();
  const isBuiltin = skill.kind === "builtin";

  return (
    <div className="control-panel-skill-item">
      <div className="control-panel-skill-item-header">
        <div className="control-panel-skill-title-block">
          <div className="control-panel-skill-title-row">
            <span className="control-panel-skill-command">{skill.command}</span>
            <SkillBadge>
              {isBuiltin
                ? t(uiStrings.controlPanel.skillBuiltinBadge)
                : t(uiStrings.controlPanel.skillInstalledBadge)}
            </SkillBadge>
            {!skill.manageable ? (
              <SkillBadge>{t(uiStrings.controlPanel.skillReadonlyBadge)}</SkillBadge>
            ) : null}
          </div>
          <div className="control-panel-skill-description">{skill.description}</div>
        </div>

        {skill.manageable ? (
          <button
            type="button"
            role="switch"
            aria-checked={skill.enabled}
            aria-label={ti(uiStrings.controlPanel.toggleSkill, { name: skill.name })}
            className={`control-panel-switch${skill.enabled ? " is-on" : ""}`}
            disabled={pending}
            onClick={() => onToggle(skill)}
          >
            <span className="control-panel-switch-thumb" aria-hidden />
          </button>
        ) : null}
      </div>

      <div className="control-panel-skill-meta">
        <div className="control-panel-readonly-row">
          <span className="control-panel-readonly-label">
            {t(uiStrings.controlPanel.skillSource)}
          </span>
          <span>{skill.source}</span>
        </div>
        {skill.path ? (
          <div className="control-panel-readonly-row">
            <span className="control-panel-readonly-label">
              {t(uiStrings.controlPanel.skillPath)}
            </span>
            <span className="control-panel-skill-path">{skill.path}</span>
          </div>
        ) : null}
        <div className="control-panel-readonly-row">
          <span className="control-panel-readonly-label">
            {t(uiStrings.controlPanel.skillStatus)}
          </span>
          <span>{skill.enabled ? t(uiStrings.controlPanel.enabled) : t(uiStrings.controlPanel.disabled)}</span>
        </div>
      </div>

      {skill.deletable ? (
        <button
          type="button"
          className="control-panel-reset-btn control-panel-inline-btn"
          disabled={pending}
          aria-label={ti(uiStrings.controlPanel.deleteSkill, { name: skill.name })}
          onClick={() => onDelete(skill)}
        >
          {t(uiStrings.common.delete)}
        </button>
      ) : null}
    </div>
  );
}

export function SkillConfigPanel() {
  const { t, ti } = useLang();
  const queryClient = useQueryClient();

  const skillsQuery = useQuery({
    queryKey: ["skills"],
    queryFn: listSkills,
    staleTime: 0,
    retry: false,
  });

  const toggleMutation = useMutation({
    mutationFn: ({ name, enabled }: { name: string; enabled: boolean }) =>
      toggleSkill(name, enabled),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["skills"] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (name: string) => deleteSkill(name),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["skills"] });
    },
  });

  const errorMessage =
    toggleMutation.error instanceof Error
      ? toggleMutation.error.message
      : deleteMutation.error instanceof Error
        ? deleteMutation.error.message
        : skillsQuery.error instanceof Error
          ? skillsQuery.error.message
          : null;

  if (skillsQuery.isLoading) {
    return (
      <div className="control-panel-card">
        <div className="control-panel-card-title">{t(uiStrings.controlPanel.skills)}</div>
        <div className="control-panel-card-hint">{t(uiStrings.common.loading)}</div>
      </div>
    );
  }

  const skills = skillsQuery.data?.skills ?? [];
  const builtinSkills = skills.filter((skill) => skill.kind === "builtin");
  const installedSkills = skills.filter((skill) => skill.kind === "installed");
  const pending = toggleMutation.isPending || deleteMutation.isPending;

  const handleToggle = (skill: SkillCatalogItem) => {
    toggleMutation.mutate({ name: skill.name, enabled: !skill.enabled });
  };

  const handleDelete = (skill: SkillCatalogItem) => {
    if (!window.confirm(ti(uiStrings.controlPanel.confirmDeleteSkill, { name: skill.name }))) {
      return;
    }
    deleteMutation.mutate(skill.name);
  };

  return (
    <div className="control-panel-stack">
      {errorMessage ? (
        <div className="control-panel-error">
          {t(uiStrings.controlPanel.configSaveFailed)}: {errorMessage}
        </div>
      ) : null}

      <div className="control-panel-card">
        <div className="control-panel-card-title">
          {t(uiStrings.controlPanel.skillStudioTitle)}
        </div>
        <div className="control-panel-card-hint">
          {t(uiStrings.controlPanel.skillStudioHint)}
        </div>
        <div className="control-panel-card-body">
          <div className="control-panel-skill-list">
            {builtinSkills.map((skill) => (
              <SkillCard
                key={skill.name}
                skill={skill}
                pending={pending}
                onToggle={handleToggle}
                onDelete={handleDelete}
              />
            ))}
          </div>
        </div>
      </div>

      <div className="control-panel-card">
        <div className="control-panel-card-title">
          {t(uiStrings.controlPanel.skillInstalledTitle)}
        </div>
        <div className="control-panel-card-hint">
          {t(uiStrings.controlPanel.skillInstalledHint)}
        </div>
        <div className="control-panel-card-body control-panel-stack">
          <div className="control-panel-readonly-row">
            <span className="control-panel-readonly-label">
              {t(uiStrings.controlPanel.skillInstallDirectory)}
            </span>
            <span>configs/skills</span>
          </div>

          {installedSkills.length === 0 ? (
            <div className="control-panel-warning">
              {t(uiStrings.controlPanel.skillInstalledEmpty)}
            </div>
          ) : (
            <div className="control-panel-skill-list">
              {installedSkills.map((skill) => (
                <SkillCard
                  key={skill.name}
                  skill={skill}
                  pending={pending}
                  onToggle={handleToggle}
                  onDelete={handleDelete}
                />
              ))}
            </div>
          )}

          <button
            type="button"
            className="control-panel-reset-btn control-panel-inline-btn"
            onClick={() => void skillsQuery.refetch()}
            disabled={skillsQuery.isFetching}
          >
            {t(uiStrings.common.refresh)}
          </button>
        </div>
      </div>
    </div>
  );
}
