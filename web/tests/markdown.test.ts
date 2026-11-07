import { describe, expect, it } from "vitest";
import { mdToHtml, escapeHtml } from "../src/utils/markdown";

describe("escapeHtml", () => {
  it("escapes all dangerous characters", () => {
    expect(escapeHtml(`<img src=x onerror="a">&'`)).toBe(
      "&lt;img src=x onerror=&quot;a&quot;&gt;&amp;&#39;",
    );
  });
});

describe("mdToHtml", () => {
  it("renders bold, code, and citations", () => {
    const html = mdToHtml("**bold** `code` [2]");
    expect(html).toContain("<b>bold</b>");
    expect(html).toContain("<code>code</code>");
    expect(html).toContain('class="cite" data-cite="2"');
  });

  it("escapes HTML in message text (never injects)", () => {
    const html = mdToHtml("<script>alert(1)</script>");
    expect(html).not.toContain("<script>");
    expect(html).toContain("&lt;script&gt;");
  });

  it("renders lists and merges paragraphs", () => {
    const html = mdToHtml("- one\n- two\npara");
    expect(html).toContain("<ul><li>one</li><li>two</li></ul>");
    expect(html).toContain("<p>para ");
  });

  it("handles empty input", () => {
    expect(mdToHtml("")).toBe("");
  });
});
