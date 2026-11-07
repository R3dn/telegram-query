/** Formatting helpers shared across the UI. */

export function fmtDate(iso: string | null | undefined): string {
  return (iso ?? "").slice(0, 10);
}

export function fmtTime(iso: string): string {
  return (iso ?? "").slice(11, 16);
}

export function fmtDateTime(iso: string | null): string {
  return (iso ?? "").slice(0, 16).replace("T", " ");
}

export function dayKey(iso: string): string {
  return (iso ?? "").slice(0, 10);
}

export function dayLabel(day: string): string {
  try {
    return new Date(day + "T12:00:00Z").toLocaleDateString(undefined, {
      weekday: "short", year: "numeric", month: "short", day: "numeric",
    });
  } catch {
    return day;
  }
}

export function nfmt(n: number): string {
  return n.toLocaleString();
}

/** Escape a string for safe use inside a RegExp. */
export function escapeRe(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/** Build one case-insensitive regex alternation for the given query phrases. */
export function highlightRegex(query: string): RegExp | null {
  const phrases = query
    .split("|")
    .map((p) => p.trim())
    .filter((p) => p.length >= 2);
  if (!phrases.length) return null;
  try {
    return new RegExp(`(${phrases.map(escapeRe).join("|")})`, "gi");
  } catch {
    return null;
  }
}

export function isoDay(d: Date): string {
  return d.toISOString().slice(0, 10);
}

export function todayIso(): string {
  return isoDay(new Date());
}

export function daysAgoIso(days: number): string {
  return isoDay(new Date(Date.now() - days * 864e5));
}

/** Human label for background job names (shared by sidebar/jobs/store). */
export function jobLabel(name: string | null | undefined): string {
  return (
    {
      sync: "Sync",
      track: "Group backfill",
      dialogs: "Group listing",
      auth: "Login",
    } as Record<string, string>
  )[name ?? ""] ?? "Job";
}
