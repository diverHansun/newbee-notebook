"use client";

import { useMemo, useState } from "react";

import { useLang } from "@/lib/hooks/useLang";
import { uiStrings } from "@/lib/i18n/strings";

type SlashCommand = {
  command: string;
  description: string;
  available: boolean;
};

type SlashCommandHintProps = {
  input: string;
  onSelect: (command: string) => void;
};

export function shouldShowSlashCommandHint(input: string): boolean {
  return input.startsWith("/") && !input.includes(" ");
}

function normalizeCommandQuery(input: string): string {
  return input.trim().toLowerCase();
}

export function SlashCommandHint({ input, onSelect }: SlashCommandHintProps) {
  const { t } = useLang();
  const [activeIndex, setActiveIndex] = useState(0);

  const commands = useMemo<SlashCommand[]>(
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
    ],
    [t]
  );

  const query = normalizeCommandQuery(input);
  const filteredCommands = commands.filter((item) => item.command.startsWith(query));

  if (!shouldShowSlashCommandHint(input) || filteredCommands.length === 0) {
    return null;
  }

  return (
    <div className="slash-command-panel" aria-label={t(uiStrings.slashCommand.hint)}>
      <div className="slash-command-panel-header">{t(uiStrings.slashCommand.hint)}</div>
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
