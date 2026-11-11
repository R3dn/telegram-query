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

/** i18n key for a background job name (resolve with t()). */
export function jobKey(name: string | null | undefined): string {
  const known = ["sync", "track", "dialogs", "auth", "reindex", "discover",
    "extract", "decisions", "brief"];
  return known.includes(name ?? "") ? `job.${name}` : "job.unknown";
}

/** Human label for background job names (English; prefer t(jobKey(n))). */
export function jobLabel(name: string | null | undefined): string {
  return (
    {
      sync: "Sync",
      track: "Group backfill",
      dialogs: "Group listing",
      auth: "Login",
      reindex: "Reindex",
      discover: "Discovery backfill",
      extract: "Deals extraction",
      decisions: "Decisions extraction",
      brief: "Research brief",
    } as Record<string, string>
  )[name ?? ""] ?? "Job";
}

/** Status chip color class for derived deal/decision states. */
export function statusTone(status: string): string {
  return (
    {
      active: "good",
      confirmed: "good",
      committed: "good",
      completed: "good",
      upcoming: "warn",
      unverified: "warn",
      proposed: "warn",
      unknown: "",
      expired: "err",
      overdue: "err",
      dismissed: "err",
      cancelled: "err",
    } as Record<string, string>
  )[status] ?? "";
}

/** i18n key for a scheduler interval (resolve with t()). */
export function intervalKey(min: number): string {
  if (min % 1440 === 0) return min === 1440
    ? "interval.everyDay" : "interval.everyDays";
  if (min % 60 === 0) return "interval.everyHours";
  return "interval.everyMin";
}

/** The {n} value that pairs with intervalKey(min). */
export function intervalN(min: number): number {
  if (min % 1440 === 0) return min / 1440;
  if (min % 60 === 0) return min / 60;
  return min;
}

/** Human label for a scheduler interval in minutes (English; prefer
 *  t(intervalKey(n), {n})). */
export function intervalLabel(min: number): string {
  if (min % 1440 === 0) return min === 1440 ? "every day" : `every ${min / 1440} days`;
  if (min % 60 === 0) return `every ${min / 60}h`;
  return `every ${min} min`;
}

/** "14:32" style local time from an ISO datetime string. */
export function fmtClock(iso: string | null | undefined): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleTimeString(undefined, {
      hour: "2-digit", minute: "2-digit",
    });
  } catch {
    return "—";
  }
}

/** Local date+time for scheduler / bookmark display. */
export function fmtLocal(iso: string | null | undefined): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString(undefined, {
      month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
    });
  } catch {
    return iso;
  }
}
