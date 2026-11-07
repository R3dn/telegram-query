/** Toast stack - rendered once at the app root. */
import { useStore } from "../state/store";

export function Toasts() {
  const { toasts } = useStore();
  return (
    <div className="toasts">
      {toasts.map((t) => (
        <div key={t.id} className={`toast ${t.type} ${t.out ? "out" : ""}`}>
          {t.text}
        </div>
      ))}
    </div>
  );
}
