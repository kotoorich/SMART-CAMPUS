import { AlertCircle, CheckCircle2, Info, LoaderCircle } from "lucide-react"

export function PageHeader({ eyebrow, title, description, actions, icon: Icon }) {
  return (
    <header className="sc-page-head">
      <div>
        {eyebrow && <p className="sc-eyebrow">{eyebrow}</p>}
        <h1>{Icon && <Icon size={26} />} {title}</h1>
        {description && <p className="sc-muted">{description}</p>}
      </div>
      {actions && <div className="sc-head-actions">{actions}</div>}
    </header>
  )
}

export function Panel({ title, subtitle, actions, children, className = "" }) {
  return (
    <section className={`sc-panel ${className}`}>
      {(title || actions) && (
        <div className="sc-section-head">
          <div>
            {title && <h2>{title}</h2>}
            {subtitle && <p className="sc-muted">{subtitle}</p>}
          </div>
          {actions}
        </div>
      )}
      {children}
    </section>
  )
}

export function Notice({ kind = "info", children }) {
  if (!children) return null
  const icons = { success: CheckCircle2, error: AlertCircle, info: Info }
  const Icon = icons[kind] || Info
  return <div className={`sc-notice ${kind}`} role={kind === "error" ? "alert" : "status"}><Icon size={15} /> {children}</div>
}

export function Loading({ label = "Loading…" }) {
  return <div className="sc-loading"><LoaderCircle className="animate-spin" size={18} /> {label}</div>
}

export function EmptyState({ icon: Icon, title, description, action }) {
  return (
    <div className="sc-empty">
      {Icon && <Icon size={28} />}
      <strong>{title}</strong>
      {description && <p>{description}</p>}
      {action}
    </div>
  )
}

export function StatusPill({ value }) {
  if (!value) return <span className="sc-status neutral">—</span>
  const key = String(value).toLowerCase()
  return <span className={`sc-status ${key}`}>{value}</span>
}

export function StatCard({ label, value, hint, tone = "default" }) {
  return (
    <div className={`sc-metric ${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
      {hint && <small>{hint}</small>}
    </div>
  )
}

export function LiveDot({ status }) {
  const label = status === "live" ? "Live" : status === "offline" ? "Offline" : "Connecting"
  return <span className={`sc-live ${status}`} title={`Realtime updates: ${label}`}><span className="sc-live-dot" /> {label}</span>
}
