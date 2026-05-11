"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { listSkills } from "@/lib/api/skills";
import { useLang } from "@/lib/hooks/useLang";
import { uiStrings } from "@/lib/i18n/strings";

export type SlashCommand = {
  command: string;
  description: string;
  available: boolean;
};

type SlashCommandHintProps = {
  input: string;
  onSelect: (command: string) => void;
};

type UseEnabledSkillCommandsOptions = {
  queryEnabled?: boolean;
};

export function shouldShowSlashCommandHint(input: string): boolean {
  return input.startsWith("/") && !input.includes(" ");
}

export function isCompleteSlashCommand(input: string, commands: SlashCommand[]): boolean {
  const value = input.toLowerCase();
  return commands.some((item) => {
    const command = item.command.toLowerCase();
    return value.startsWith(command) && /\s/.test(value.charAt(command.length));
  });
}

function normalizeCommandQuery(input: string): string {
  return input.trim().toLowerCase();
}

export function useEnabledSkillCommands({
  queryEnabled = true,
}: UseEnabledSkillCommandsOptions = {}): SlashCommand[] {
  const { t } = useLang();

  const builtinCommands = useMemo<SlashCommand[]>(
    () => [
      {
        command: "/note",
        description: t(uiStrings.slashCommand.noteDescription),
        available: true,
      },
      {
        command: "/diagram",
        description: t(uiStrings.slashCommand.diagramDescription),
        available: true,
      },
      {
        command: "/video",
        description: t(uiStrings.slashCommand.videoDescription),
        available: true,
      },
    ],
    [t]
  );

  const skillsQuery = useQuery({
    queryKey: ["skills"],
    queryFn: listSkills,
    enabled: queryEnabled,
    staleTime: 10_000,
    retry: false,
  });

  const commands = useMemo<SlashCommand[]>(() => {
    const catalog = skillsQuery.data?.skills ?? [];
    if (catalog.length === 0) {
      return builtinCommands;
    }

    const builtinDescriptionByCommand = new Map(
      builtinCommands.map((item) => [item.command, item.description])
    );

    const fromCatalog = catalog
      .filter((skill) => skill.enabled)
      .map((skill) => ({
        command: skill.command || `/${skill.name}`,
        description:
          builtinDescriptionByCommand.get(skill.command || `/${skill.name}`) ||
          skill.description,
        available: true,
      }));

    return fromCatalog.length > 0 ? fromCatalog : builtinCommands;
  }, [builtinCommands, skillsQuery.data?.skills]);

  return commands;
}

export function SlashCommandHint({ input, onSelect }: SlashCommandHintProps) {
  const { t } = useLang();
  const [activeIndex, setActiveIndex] = useState(0);
  const commands = useEnabledSkillCommands();

  const query = normalizeCommandQuery(input);
  const filteredCommands = commands.filter((item) => item.command.startsWith(query));

  if (!shouldShowSlashCommandHint(input) || filteredCommands.length === 0) {
    return null;
  }

  return (
    <div className="slash-command-panel" aria-label={t(uiStrings.slashCommand.panelLabel)}>
      <div className="slash-command-panel-body">
        {filteredCommands.map((item, index) => {
          const isActive = index === activeIndex;
          return (
            <button
              key={item.command}
              type="button"
              className={`slash-command-row${isActive ? " is-active" : ""}`}
              disabled={!item.available}
              onMouseEnter={() => setActiveIndex(index)}
              onClick={() => onSelect(item.command)}
            >
              <span className="slash-command-main">
                <span className="slash-command-name">{item.command}</span>
                <span className="slash-command-description">{item.description}</span>
              </span>
              {!item.available ? (
                <span className="slash-command-status">{t(uiStrings.slashCommand.comingSoon)}</span>
              ) : null}
            </button>
          );
        })}
      </div>
    </div>
  );
}
