/** Petits composants d'interface réutilisés partout. */
import { useEffect, useState } from 'react'

export function Card({ title, subtitle, actions, children, bodyClass = 'card-body', className = '' }) {
  return (
    <section className={`card ${className}`}>
      {(title || actions) && (
        <div className="card-head">
          <div>
            {title && <h2>{title}</h2>}
            {subtitle && <p>{subtitle}</p>}
          </div>
          {actions}
        </div>
      )}
      <div className={bodyClass}>{children}</div>
    </section>
  )
}

export function StatCard({ label, value, unit, hint, percent }) {
  const shown = value === null || value === undefined || value === '' ? '—' : value
  return (
    <div className="card stat-card">
      <div className="stat-label">{label}</div>
      <div className="stat-value">
        {shown}
        {unit && shown !== '—' && <span className="stat-unit">{unit}</span>}
      </div>
      {typeof percent === 'number' && (
        <div className="meter">
          <span style={{ width: `${Math.max(0, Math.min(100, percent))}%` }} />
        </div>
      )}
      {hint && <div className="stat-hint">{hint}</div>}
    </div>
  )
}

/** Couleur de badge cohérente pour chaque profil pédagogique. */
export const PROFILE_TONE = {
  'Avancé': 'badge-green',
  'Moyen': 'badge-blue',
  'Débutant': 'badge',
  'En difficulté': 'badge-red',
  'Peu actif': 'badge-amber',
}

export const PROFILE_COLOR = {
  'Avancé': '#16a34a',
  'Moyen': '#2563eb',
  'Débutant': '#64748b',
  'En difficulté': '#dc2626',
  'Peu actif': '#d97706',
}

export function ProfileBadge({ profile, large = false }) {
  if (!profile) return <span className="badge">Non analysé</span>
  return (
    <span className={`badge ${PROFILE_TONE[profile] || ''} ${large ? 'badge-lg' : ''}`}>{profile}</span>
  )
}

export function RiskBadge({ level }) {
  if (!level) return null
  const tone = level === 'Élevé' ? 'badge-red' : level === 'Moyen' ? 'badge-amber' : 'badge-green'
  return <span className={`badge ${tone}`}>Risque {level.toLowerCase()}</span>
}

export function Alert({ type = 'error', children, onClose }) {
  if (!children) return null
  return (
    <div className={`alert alert-${type}`}>
      <div style={{ flex: 1 }}>{children}</div>
      {onClose && (
        <button type="button" className="btn-link" onClick={onClose} aria-label="Fermer">
          Fermer
        </button>
      )}
    </div>
  )
}

export function Loading({ label = 'Chargement...' }) {
  return (
    <div className="loading-box">
      <span className="spinner" /> {label}
    </div>
  )
}

export function Empty({ title, children }) {
  return (
    <div className="empty">
      {title && <strong>{title}</strong>}
      {children}
    </div>
  )
}

/** Boîte de confirmation — utilisée pour toute action destructive. */
export function ConfirmDialog({ open, title, message, confirmLabel = 'Confirmer', requireText, onConfirm, onCancel, busy }) {
  const [typed, setTyped] = useState('')

  useEffect(() => { if (open) setTyped('') }, [open])

  if (!open) return null
  const blocked = requireText ? typed.trim().toLowerCase() !== requireText.toLowerCase() : false

  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true">
      <div className="modal">
        <div className="modal-head"><h2>{title}</h2></div>
        <div className="modal-body">
          <p className="muted">{message}</p>
          {requireText && (
            <div className="field mt-2">
              <label>Saisissez <span className="mono">{requireText}</span> pour confirmer</label>
              <input value={typed} onChange={(e) => setTyped(e.target.value)} autoFocus />
            </div>
          )}
        </div>
        <div className="modal-foot">
          <button type="button" className="btn" onClick={onCancel} disabled={busy}>Annuler</button>
          <button type="button" className="btn btn-danger" onClick={onConfirm} disabled={blocked || busy}>
            {busy && <span className="spinner" />} {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  )
}

export function formatDate(value, withTime = true) {
  if (!value) return '—'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return '—'
  return d.toLocaleString('fr-FR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    ...(withTime ? { hour: '2-digit', minute: '2-digit' } : {}),
  })
}

export function num(value, digits = 1) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '—'
  return Number(value).toFixed(digits)
}
