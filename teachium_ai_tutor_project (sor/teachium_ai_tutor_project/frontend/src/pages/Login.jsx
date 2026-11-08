import { useState } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { homeRouteFor, useAuth } from '../context/AuthContext'
import { Alert, Card } from '../components/ui'

const DEMO = [
  { email: 'apprenant.difficulte@teachium.ma', password: 'Apprenant@2026', label: 'Apprenant — En difficulté' },
  { email: 'apprenant.avance@teachium.ma', password: 'Apprenant@2026', label: 'Apprenant — Avancé' },
  { email: 'formateur@teachium.ma', password: 'Formateur@2026', label: 'Formateur' },
  { email: 'admin@teachium.ma', password: 'Admin@2026', label: 'Administrateur' },
]

export default function Login() {
  const { login, user, loading } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  if (loading) return null
  if (user) return <Navigate to={homeRouteFor(user.role)} replace />

  async function submit(event, creds) {
    event?.preventDefault()
    const mail = creds?.email ?? email
    const pass = creds?.password ?? password

    if (!mail.trim() || !pass) {
      setError('Renseignez votre adresse e-mail et votre mot de passe.')
      return
    }

    setBusy(true)
    setError('')
    const result = await login(mail.trim(), pass)
    setBusy(false)

    if (result.ok) navigate(homeRouteFor(result.user.role), { replace: true })
    else setError(result.error)
  }

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="auth-brand">
          <div className="brand-mark" style={{ width: 36, height: 36, fontSize: 16 }}>T</div>
          <div>
            <div style={{ fontWeight: 600, fontSize: 17 }}>TEACHIUM AI Tutor</div>
            <div className="small muted">Tutorat intelligent et parcours personnalisés</div>
          </div>
        </div>

        <Card title="Connexion">
          <Alert type="error">{error}</Alert>

          <form onSubmit={submit}>
            <div className="field">
              <label htmlFor="email">Adresse e-mail</label>
              <input
                id="email" type="email" autoComplete="username" value={email}
                onChange={(e) => setEmail(e.target.value)} placeholder="prenom.nom@teachium.ma"
              />
            </div>
            <div className="field">
              <label htmlFor="password">Mot de passe</label>
              <input
                id="password" type="password" autoComplete="current-password" value={password}
                onChange={(e) => setPassword(e.target.value)} placeholder="••••••••"
              />
            </div>
            <button type="submit" className="btn btn-primary btn-block" disabled={busy}>
              {busy && <span className="spinner" />} Se connecter
            </button>
          </form>

          <p className="small muted mt-2" style={{ textAlign: 'center', marginBottom: 0 }}>
            Pas encore de compte ? <Link to="/inscription">Créer un compte apprenant</Link>
          </p>

          <div className="auth-demo">
            <h4>Comptes de démonstration</h4>
            {DEMO.map((account) => (
              <button
                key={account.email} type="button" className="demo-account" disabled={busy}
                onClick={(e) => submit(e, account)}
              >
                <span>
                  {account.label}
                  <br />
                  <small>{account.email}</small>
                </span>
                <span className="badge">Entrer</span>
              </button>
            ))}
          </div>
        </Card>
      </div>
    </div>
  )
}
