/** Toast stack - rendered once at the app root.
 *
 *  Each toast leads with a status icon (good/err/info); the text itself
 *  comes from the caller and is already localized. */
import { useStore } from "../state/store";
import { Ic } from "../design/icons";

export function Toasts() {
  const { toasts } = useStore();
  return (
    <div className="toasts">
      {toasts.map((t) => (
        <div key={t.id} className={`toast ${t.type} ${t.out ? "out" : ""}`}>
          <span className="toast-ic">
            {t.type === "good" ? (
              <Ic.CircleCheck size={14} />
            ) : t.type === "err" ? (
              <Ic.CircleAlert size={14} />
            ) : (
              <Ic.Info size={14} />
            )}
          </span>
          <span>{t.text}</span>
        </div>
      ))}
    </div>
  );
}
