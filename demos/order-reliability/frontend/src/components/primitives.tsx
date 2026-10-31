import type { ReactNode } from 'react';

export function Panel({
  title,
  subtitle,
  children,
  className = '',
}: {
  title: string;
  subtitle?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`panel ${className}`}>
      <header>
        <h2>{title}</h2>
        {subtitle && <p>{subtitle}</p>}
      </header>
      {children}
    </section>
  );
}
export function Status({ value }: { value: string }) {
  const tone = ['DONE', 'COMPLETE', 'CONFIRMED', 'FULFILLED'].includes(value)
    ? 'good'
    : ['UNKNOWN', 'MANUAL_REVIEW'].includes(value)
      ? 'warn'
      : 'neutral';
  return <span className={`status ${tone}`}>{value.replaceAll('_', ' ')}</span>;
}
export function Empty({ children }: { children: ReactNode }) {
  return <p className="empty">{children}</p>;
}
export function Field({ name, value }: { name: string; value: ReactNode }) {
  return (
    <div className="field">
      <dt>{name}</dt>
      <dd>{value ?? '—'}</dd>
    </div>
  );
}
