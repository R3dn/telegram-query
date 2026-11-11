/** Prominent search input with recent-search dropdown and mode handling. */
import { useEffect, useRef, useState } from "react";
import { useStore } from "../state/store";
import { useLang } from "../i18n";
import { Ic } from "../design/icons";

export function SearchBar() {
  const { mode, q, runSearch, searchHistory, pushSearch } = useStore();
  const { t } = useLang();
  const [value, setValue] = useState("");
  const [focused, setFocused] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => { setValue(mode === "search" ? q : ""); }, [mode, q]);

  // "/" focuses search
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const typing = /^(input|textarea|select)$/i.test((e.target as HTMLElement).tagName);
      if (e.key === "/" && !typing) {
        e.preventDefault();
        inputRef.current?.focus();
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);

  const submit = (query: string) => {
    runSearch(query);
    inputRef.current?.blur();
    setFocused(false);
  };

  const showHistory = focused && searchHistory.length > 0;

  return (
    <div className="searchbar">
      <div className="searchbox">
        <span className="search-ic"><Ic.Search size={15} /></span>
        <input
          ref={inputRef}
          className="input"
          placeholder={mode === "search" ? t("search.activePlaceholder") : t("search.placeholder")}
          value={value}
          onFocus={() => setFocused(true)}
          onBlur={() => setTimeout(() => setFocused(false), 150)}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") submit(value);
            if (e.key === "Escape") {
              if (mode === "search") {
                e.preventDefault();
                setValue("");
                runSearch("");
              }
              inputRef.current?.blur();
            }
          }}
        />
        <button
          className="btn sm ghost search-clear"
          title={t("search.backToBrowse")}
          onClick={() => { setValue(""); runSearch(""); }}
        >
          <Ic.Close size={13} />
        </button>
      </div>
      {showHistory && (
        <div className="history-panel">
          <div className="history-head">
            <span className="label">{t("search.recent")}</span>
          </div>
          {searchHistory.map((h, i) => (
            <button key={i} className="history-item" onMouseDown={() => { pushSearch(h.q); submit(h.q); }}>
              <span className="history-q" dir="auto">{h.q}</span>
              <span className="history-date">{new Date(h.at).toLocaleDateString()}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
