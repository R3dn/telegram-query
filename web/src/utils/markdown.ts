/** Minimal, safe Markdown renderer for AI answers.
 *
 * Supports: bold, inline code, ordered/unordered lists, headings, [n]
 * citations, paragraphs. ALL text is HTML-escaped first; the citation
 * pattern then wraps [n] tokens in clickable spans (data-cite).
 */

export function escapeHtml(s: string): string {
  return (s ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c] as string),
  );
}

export function mdToHtml(md: string): string {
  if (!md || !md.trim()) return "";

  const inline = (t: string) =>
    escapeHtml(t)
      .replace(/\[({?\d+}?)\]/g, '<span class="cite" data-cite="$1">[$1]</span>')
      .replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>")
      .replace(/`([^`]+)`/g, "<code>$1</code>");

  const lines = md.replace(/\r/g, "").split("\n");
  let html = "";
  let list: "ul" | "ol" | null = null;
  const closeList = () => {
    if (list) {
      html += `</${list}>`;
      list = null;
    }
  };

  for (const raw of lines) {
    const line = raw.trimEnd();
    if (/^\s*[-*]\s+/.test(line)) {
      if (list !== "ul") {
        closeList();
        html += "<ul>";
        list = "ul";
      }
      html += `<li>${inline(line.replace(/^\s*[-*]\s+/, ""))}</li>`;
    } else if (/^\s*\d+[.)]\s+/.test(line)) {
      if (list !== "ol") {
        closeList();
        html += "<ol>";
        list = "ol";
      }
      html += `<li>${inline(line.replace(/^\s*\d+[.)]\s+/, ""))}</li>`;
    } else if (/^#{1,4}\s+/.test(line)) {
      closeList();
      html += `<h4>${inline(line.replace(/^#{1,4}\s+/, ""))}</h4>`;
    } else if (line.trim() === "") {
      closeList();
      html += "</p>";
    } else {
      closeList();
      if (html === "" || /<\/p>$|<\/ul>$|<\/ol>$/.test(html)) html += "<p>";
      html += `${inline(line)} `;
    }
  }
  closeList();
  return html
    .replace(/<p>\s*<\/p>/g, "")
    .replace(/<\/p>(?=\S)/g, "</p>");
}
