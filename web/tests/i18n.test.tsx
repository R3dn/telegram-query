/** i18n core: language switching, RTL application, interpolation,
 *  and the honest fallback chain (active lang → EN → key). */
import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { LangProvider, useLang } from "../src/i18n";

function Probe() {
  const { t, lang, isRTL, dir, setLang } = useLang();
  return (
    <div>
      <span data-testid="lang">{lang}</span>
      <span data-testid="dir">{dir}</span>
      <span data-testid="rtl">{String(isRTL)}</span>
      <span data-testid="nav">{t("nav.discover")}</span>
      <span data-testid="days">{t("filter.days", { n: 7 })}</span>
      <span data-testid="missing">{t("totally.missing.key")}</span>
      <button onClick={() => setLang("ar")}>ar</button>
    </div>
  );
}

describe("i18n", () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.lang = "en";
    document.documentElement.dir = "ltr";
    document.documentElement.classList.remove("rtl");
  });

  afterEach(() => {
    document.documentElement.lang = "en";
    document.documentElement.dir = "ltr";
    document.documentElement.classList.remove("rtl");
  });

  it("defaults to English and resolves strings", () => {
    render(
      <LangProvider>
        <Probe />
      </LangProvider>,
    );
    expect(screen.getByTestId("lang").textContent).toBe("en");
    expect(screen.getByTestId("rtl").textContent).toBe("false");
    expect(screen.getByTestId("nav").textContent).toBe("Discover");
    expect(screen.getByTestId("days").textContent).toBe("7 days");
  });

  it("interpolates {n} placeholders", () => {
    render(
      <LangProvider>
        <Probe />
      </LangProvider>,
    );
    expect(screen.getByTestId("days").textContent).toBe("7 days");
  });

  it("falls back to the key itself when nothing translates", () => {
    render(
      <LangProvider>
        <Probe />
      </LangProvider>,
    );
    expect(screen.getByTestId("missing").textContent).toBe("totally.missing.key");
  });

  it("switching to Arabic flips <html> dir/lang, the rtl class, and strings", () => {
    render(
      <LangProvider>
        <Probe />
      </LangProvider>,
    );
    act(() => {
      screen.getByRole("button", { name: "ar" }).click();
    });
    expect(screen.getByTestId("lang").textContent).toBe("ar");
    expect(screen.getByTestId("rtl").textContent).toBe("true");
    expect(screen.getByTestId("dir").textContent).toBe("rtl");
    expect(document.documentElement.dir).toBe("rtl");
    expect(document.documentElement.lang).toBe("ar");
    expect(document.documentElement.classList.contains("rtl")).toBe(true);
    // Arabic dictionary value for nav.discover
    expect(screen.getByTestId("nav").textContent).toBe("الاستكشاف");
    // EN keys stay the same shape in Arabic (days uses {n})
    expect(screen.getByTestId("days").textContent).toContain("7");
  });

  it("persists the choice in localStorage", () => {
    render(
      <LangProvider>
        <Probe />
      </LangProvider>,
    );
    act(() => {
      screen.getByRole("button", { name: "ar" }).click();
    });
    expect(localStorage.getItem("tgq-lang")).toBe("ar");
  });

  it("restores a persisted language on mount", () => {
    localStorage.setItem("tgq-lang", "ar");
    render(
      <LangProvider>
        <Probe />
      </LangProvider>,
    );
    expect(screen.getByTestId("lang").textContent).toBe("ar");
    expect(document.documentElement.dir).toBe("rtl");
  });
});
