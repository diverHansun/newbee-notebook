"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  deleteSkill,
  listSkills,
  toggleSkill,
  type SkillCatalogItem,
} from "@/lib/api/skills";
import { useLang } from "@/lib/hooks/useLang";
import { builtinSkillDescriptions, uiStrings } from "@/lib/i18n/strings";

function BuiltinSkillRow({ skill }: { skill: SkillCatalogItem }) {
  const { t } = useLang();
  const localized = builtinSkillDescriptions[skill.name];
  const description = localized ? t(localized) : skill.description;
  return (
    <div className="control-panel-skill-row">
      <div className="control-panel-skill-row-text">
        <span className="control-panel-skill-command">{skill.command}</span>
        <span className="control-panel-skill-description">{description}</span>
      </div>
    </div>
  );
}

function InstalledSkillRow({
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

  return (
    <div className="control-panel-skill-row">
      <div className="control-panel-skill-row-text">
        <span className="control-panel-skill-command">{skill.command}</span>
        <span className="control-panel-skill-description">{skill.description}</span>
      </div>

      <div className="control-panel-skill-row-actions">
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

        {skill.deletable ? (
          <button
            type="button"
            className="control-panel-skill-delete-btn"
            disabled={pending}
            aria-label={ti(uiStrings.controlPanel.deleteSkill, { name: skill.name })}
            onClick={() => onDelete(skill)}
          >
            {t(uiStrings.common.delete)}
          </button>
        ) : null}
      </div>
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
        <div className="control-panel-card-body">
          <div className="control-panel-skill-rows">
            {builtinSkills.map((skill) => (
              <BuiltinSkillRow key={skill.name} skill={skill} />
            ))}
          </div>
        </div>
      </div>

      <div className="control-panel-card">
        <div className="control-panel-card-title">
          {t(uiStrings.controlPanel.skillInstalledTitle)}
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
            <div className="control-panel-skill-rows">
              {installedSkills.map((skill) => (
                <InstalledSkillRow
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
