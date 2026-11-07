import { beforeEach, describe, expect, it } from "vitest";
import {
  clearChat, clearSearchHistory, getChat, getSearchHistory,
  getTheme, pushChat, pushSearchHistory, setTheme,
} from "../src/utils/history";

describe("search history", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("stores, dedupes, and caps entries", () => {
    pushSearchHistory("alpha");
    pushSearchHistory("beta");
    pushSearchHistory("alpha"); // dedupe moves it to the front
    expect(getSearchHistory().map((h) => h.q)).toEqual(["alpha", "beta"]);
    for (let i = 0; i < 12; i++) pushSearchHistory(`q${i}`);
    expect(getSearchHistory().length).toBeLessThanOrEqual(8);
  });

  it("ignores empty input", () => {
    pushSearchHistory("   ");
    expect(getSearchHistory()).toEqual([]);
  });

  it("clears", () => {
    pushSearchHistory("x");
    expect(clearSearchHistory()).toEqual([]);
  });
});

describe("ai chat history", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("appends turns and caps at 50", () => {
    pushChat({ question: "q", answer: "a", sources: [], keywords: [] });
    expect(getChat().length).toBe(1);
    for (let i = 0; i < 60; i++) {
      pushChat({ question: `q${i}`, answer: null, sources: [], keywords: [] });
    }
    expect(getChat().length).toBeLessThanOrEqual(50);
  });

  it("clears", () => {
    pushChat({ question: "q", answer: null, sources: [], keywords: [] });
    expect(clearChat()).toEqual([]);
  });
});

describe("theme", () => {
  it("round-trips through localStorage and the html class", () => {
    setTheme("light");
    expect(getTheme()).toBe("light");
    expect(document.documentElement.classList.contains("light")).toBe(true);
    setTheme("dark");
    expect(getTheme()).toBe("dark");
    expect(document.documentElement.classList.contains("light")).toBe(false);
  });
});
