"use client";

import { useMemo, useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";

import { listSkills } from "@/lib/api/skills";
import { useLang } from "@/lib/hooks/useLang";
import { uiStrings } from "@/lib/i18n/strings";

export type SlashCommand = {
  command: string;
  description: string;
  available: boolean;
};

function NoteIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z" />
      <polyline points="14 3 14 9 20 9" />
      <line x1="8" y1="13" x2="16" y2="13" />
      <line x1="8" y1="17" x2="13" y2="17" />
    </svg>
  );
}

function DiagramIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <line x1="3" y1="20" x2="21" y2="20" />
      <rect x="5" y="11" width="3" height="9" />
      <rect x="10.5" y="6" width="3" height="14" />
      <rect x="16" y="14" width="3" height="6" />
    </svg>
  );
}

function VideoIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <rect x="2.5" y="5" width="14" height="14" rx="2" />
      <polygon points="22 7 16.5 11 16.5 13 22 17 22 7" />
    </svg>
  );
}

function ExternalSkillIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M12 3v3" />
      <path d="M12 18v3" />
      <path d="M5.6 5.6l2.1 2.1" />
      <path d="M16.3 16.3l2.1 2.1" />
      <path d="M3 12h3" />
      <path d="M18 12h3" />
      <path d="M5.6 18.4l2.1-2.1" />
      <path d="M16.3 7.7l2.1-2.1" />
    </svg>
  );
}

const COMMAND_ICONS: Record<string, ReactNode> = {
  "/note": <NoteIcon />,
  "/diagram": <DiagramIcon />,
  "/video": <VideoIcon />,
};

function getCommandIcon(command: string): ReactNode {
  return COMMAND_ICONS[command] ?? <ExternalSkillIcon />;
}

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
              title={item.description}
            >
              <span className="slash-command-icon" aria-hidden="true">
                {getCommandIcon(item.command)}
              </span>
              <span className="slash-command-name">{item.command}</span>
              <span className="slash-command-separator" aria-hidden="true">·</span>
              <span className="slash-command-description">{item.description}</span>
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
