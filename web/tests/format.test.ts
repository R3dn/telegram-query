import { describe, expect, it } from "vitest";
import {
  dayKey, dayLabel, escapeRe, fmtDate, fmtTime,
  highlightRegex, isoDay,
} from "../src/utils/format";

describe("format utils", () => {
  it("slices ISO dates safely", () => {
    expect(fmtDate("2026-01-02T10:00:00")).toBe("2026-01-02");
    expect(fmtTime("2026-01-02T10:30:00")).toBe("10:30");
    expect(dayKey("2026-01-02T10:00:00")).toBe("2026-01-02");
    expect(fmtDate(null)).toBe("");
  });

  it("labels days without throwing", () => {
    expect(dayLabel("2026-01-02")).toBeTruthy();
  });

  it("escapes regex metacharacters", () => {
    expect(escapeRe("a.b(c)")).toBe("a\\.b\\(c\\)");
  });

  it("builds a highlight alternation for piped phrases", () => {
    const en = highlightRegex("offer|عرض");
    expect(en).not.toBeNull();
    expect("big offer today".match(en!)).not.toBeNull();
    const ar = highlightRegex("offer|عرض"); // fresh regex: global-flag lastIndex safety
    expect("عرض خاص".match(ar!)).not.toBeNull();
  });

  it("drops single characters from highlighting", () => {
    expect(highlightRegex("a|bc")).not.toBeNull();
    expect(highlightRegex("a")).toBeNull();
  });
});

describe("isoDay", () => {
  it("returns YYYY-MM-DD", () => {
    expect(isoDay(new Date("2026-05-06T10:00:00Z"))).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  });
});
