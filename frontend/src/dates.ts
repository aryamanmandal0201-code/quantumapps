// Due dates come from the API as "YYYY-MM-DD" (no time zone), so parse them as local dates.
export function parseDay(iso: string | null): Date | null {
  if (!iso) return null;
  const [y, m, d] = iso.split("-").map(Number);
  if (y === undefined || m === undefined || d === undefined) return null;
  return new Date(y, m - 1, d);
}

function startOfToday(): Date {
  const now = new Date();
  return new Date(now.getFullYear(), now.getMonth(), now.getDate());
}

export type DueTone = "normal" | "soon" | "overdue";

export function dueInfo(iso: string | null, done: boolean): { label: string; tone: DueTone } | null {
  const day = parseDay(iso);
  if (!day) return null;
  const diff = Math.round((day.getTime() - startOfToday().getTime()) / 86400000);
  let label: string;
  if (diff === 0) label = "Due today";
  else if (diff === 1) label = "Due tomorrow";
  else if (diff === -1) label = "Due yesterday";
  else label = "Due " + day.toLocaleDateString(undefined, { weekday: "short", day: "numeric", month: "short" });
  let tone: DueTone = "normal";
  if (!done && diff < 0) tone = "overdue";
  else if (!done && diff <= 1) tone = "soon";
  return { label, tone };
}

export function shortDate(isoDateTime: string): string {
  return new Date(isoDateTime).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
}
