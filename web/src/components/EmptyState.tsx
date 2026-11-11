/** Polished empty state with a Lucide icon, title, hint, and next action. */
import type { ReactNode } from "react";
import { Ic, type IconName } from "../design/icons";

export function EmptyState(props: {
  icon: IconName;
  title: string;
  hint?: string;
  action?: ReactNode;
}) {
  const C = Ic[props.icon];
  return (
    <div className="empty">
      <div className="ic"><C size={30} strokeWidth={1.5} /></div>
      <h4>{props.title}</h4>
      {props.hint && <p>{props.hint}</p>}
      {props.action}
    </div>
  );
}
