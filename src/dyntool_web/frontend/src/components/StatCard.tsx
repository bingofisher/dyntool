import type { ReactNode } from "react";

export const StatCard = ({ label, value, hint }: { label: string; value: ReactNode; hint?: string }) => (
  <article className="stat-card">
    <span>{label}</span>
    <strong>{value}</strong>
    {hint ? <small>{hint}</small> : null}
  </article>
);
