/** Reusable modal shell with overlay-click and Esc handling. */
import { useEffect, type ReactNode } from "react";
import { useLang } from "../i18n";
import { Ic } from "../design/icons";

export function Modal(props: {
  title: string;
  wide?: boolean;
  onClose: () => void;
  children: ReactNode;
  footer?: ReactNode;
}) {
  const { t } = useLang();

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") props.onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [props.onClose]);

  return (
    <div
      className="modal-overlay"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) props.onClose();
      }}
    >
      <div className={`modal ${props.wide ? "wide" : ""}`}>
        <div className="modal-head">
          <h3>{props.title}</h3>
          <button className="btn ghost sm" title={t("action.close")}
                  onClick={props.onClose}>
            <Ic.Close size={14} />
          </button>
        </div>
        <div className="modal-body">{props.children}</div>
        {props.footer && <div className="modal-foot">{props.footer}</div>}
      </div>
    </div>
  );
}
