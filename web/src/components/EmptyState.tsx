/** Polished empty state with icon, title, hint, and a next action. */
import type { ReactNode } from "react";

export function EmptyState(props: {
  icon: string;
  title: string;
  hint?: string;
  action?: ReactNode;
}) {
  return (
    <div className="empty">
      <div className="ic">{props.icon}</div>
      <h4>{props.title}</h4>
      {props.hint && <p>{props.hint}</p>}
      {props.action}
    </div>
  );
}
