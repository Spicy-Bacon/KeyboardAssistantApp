import type { ReactNode } from "react";

export function PageHeader({ title, subtitle }: { title: string; subtitle: string }) {
  return (
    <header className="page-header">
      <div>
        <h1>{title}</h1>
        <p>{subtitle}</p>
      </div>
    </header>
  );
}

export function SettingsCard({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="settings-card">
      <h2>{title}</h2>
      <div className="card-body">{children}</div>
    </section>
  );
}

export function SettingsRow({ title, description, children }: { title: string; description: string; children: ReactNode }) {
  return (
    <div className="settings-row">
      <div className="settings-copy">
        <div className="row-title">{title}</div>
        <div className="row-subtitle">{description}</div>
      </div>
      <div className="settings-control">{children}</div>
    </div>
  );
}

export function ToggleSwitch({ checked, onChange }: { checked: boolean; onChange: (checked: boolean) => void }) {
  return (
    <button className={`toggle ${checked ? "checked" : ""}`} onClick={() => onChange(!checked)} aria-pressed={checked}>
      <span />
    </button>
  );
}

export function SelectDropdown<T extends string>({ value, options, onChange }: { value: T; options: T[]; onChange: (value: T) => void }) {
  return (
    <select className="select" value={value} onChange={(event) => onChange(event.target.value as T)}>
      {options.map((option) => (
        <option value={option} key={option}>
          {option}
        </option>
      ))}
    </select>
  );
}

export function Button({ children, onClick, muted, danger }: { children: ReactNode; onClick?: () => void; muted?: boolean; danger?: boolean }) {
  return (
    <button className={`button ${muted ? "muted" : ""} ${danger ? "danger" : ""}`} onClick={onClick}>
      {children}
    </button>
  );
}

export function TextInput({ value, placeholder, onChange }: { value: string; placeholder: string; onChange: (value: string) => void }) {
  return <input className="text-input" value={value} placeholder={placeholder} onChange={(event) => onChange(event.target.value)} />;
}

export function StatusPill({ status, label }: { status: "ok" | "warn"; label: string }) {
  return <span className={`status-pill ${status}`}>{label}</span>;
}

export function MetricGrid({ metrics }: { metrics: Array<[string, number]> }) {
  return (
    <div className="metric-grid">
      {metrics.map(([label, value]) => (
        <div className="metric" key={label}>
          <strong>{value}</strong>
          <span>{label}</span>
        </div>
      ))}
    </div>
  );
}

export function PathLine({ label, value }: { label: string; value: string }) {
  return (
    <div className="path-line">
      <span>{label}</span>
      <code>{value || "Unavailable"}</code>
    </div>
  );
}

export function EmptyState({ label }: { label: string }) {
  return <div className="empty-state">{label}</div>;
}
