import type { Session } from "@/lib/api/types";

function parseTimestamp(value: string): number | null {
  const timestamp = Date.parse(value);
  return Number.isFinite(timestamp) ? timestamp : null;
}

function compareSessionCreationOrder(left: Session, right: Session): number {
  const leftCreatedAt = parseTimestamp(left.created_at);
  const rightCreatedAt = parseTimestamp(right.created_at);

  if (leftCreatedAt !== null && rightCreatedAt !== null && leftCreatedAt !== rightCreatedAt) {
    return leftCreatedAt - rightCreatedAt;
  }

  const leftUpdatedAt = parseTimestamp(left.updated_at);
  const rightUpdatedAt = parseTimestamp(right.updated_at);
  if (leftUpdatedAt !== null && rightUpdatedAt !== null && leftUpdatedAt !== rightUpdatedAt) {
    return leftUpdatedAt - rightUpdatedAt;
  }

  return left.session_id.localeCompare(right.session_id);
}

export function buildSessionDisplayTitleMap(
  sessions: Session[],
  untitledPattern: string
): Map<string, string> {
  const orderedSessions = [...sessions].sort(compareSessionCreationOrder);

  return new Map(
    orderedSessions.map((session, index) => {
      const normalizedTitle = session.title?.trim();
      const displayTitle = normalizedTitle || untitledPattern.replace("{n}", String(index + 1));
      return [session.session_id, displayTitle];
    })
  );
}

export function getSessionDisplayTitle(
  session: Session | null,
  titleMap: Map<string, string>,
  placeholder: string
): string {
  if (!session) return placeholder;
  return titleMap.get(session.session_id) || session.title?.trim() || session.session_id.slice(0, 8);
}