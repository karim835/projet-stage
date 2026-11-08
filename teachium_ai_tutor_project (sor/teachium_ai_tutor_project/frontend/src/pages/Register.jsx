import { useState } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { homeRouteFor, useAuth } from '../context/AuthContext'
import { Alert, Card } from '../components/ui'

const CATEGORIES = ['Python', 'Data', 'Web', 'Management', 'Communication']

export default function Register() {
  const { register, user, loading } = useAuth()
  const navigate = useNavigate()
  const [form, setForm] = useState({
    name: '', email: '', password: '', confirm: '', course_category: '',
  })
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  if (loading) return null
  if (user) return <Navigate to={homeRouteFor(user.role)} replace />

  const update = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }))

  async function submit(event) {
    event.preventDefault()
    if (form.name.trim().length < 2) return setError('Le nom doit contenir au moins 2 caractères.')
    if (!form.email.trim()) return setError('Renseignez une adresse e-mail.')
    if (!form.course_category) return setError('Choisissez votre filière pour recevoir les quiz adaptés.')
    if (form.password.length < 8) return setError('Le mot de passe doit contenir au moins 8 caractères.')
    if (form.password !== form.confirm) return setError('Les deux mots de passe ne correspondent pas.')

    setBusy(true)
    setError('')
    const result = await register({
      name: form.name.trim(),
      email: form.email.trim(),
      password: form.password,
      role: 'learner',
      course_category: form.course_category,
    })
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
            <div className="small muted">Création d'un compte apprenant</div>
          </div>
        </div>

        <Card title="Créer un compte">
          <Alert type="error">{error}</Alert>

          <form onSubmit={submit}>
            <div className="field">
              <label htmlFor="name">Nom complet</label>
              <input id="name" value={form.name} onChange={update('name')} placeholder="Prénom Nom" />
            </div>
            <div className="field">
              <label htmlFor="email">Adresse e-mail</label>
              <input id="email" type="email" value={form.email} onChange={update('email')} />
            </div>
            <div className="field">
              <label htmlFor="course-category">Filière</label>
              <select
                id="course-category"
                value={form.course_category}
                onChange={update('course_category')}
                required
              >
                <option value="">Choisir une filière</option>
                {CATEGORIES.map((category) => (
                  <option key={category} value={category}>{category}</option>
                ))}
              </select>
              <span className="field-hint">Votre filière détermine les quiz et les ressources qui vous sont proposés.</span>
            </div>
            <div className="field">
              <label htmlFor="password">Mot de passe</label>
              <input id="password" type="password" value={form.password} onChange={update('password')} />
              <span className="field-hint">8 caractères minimum.</span>
            </div>
            <div className="field">
              <label htmlFor="confirm">Confirmer le mot de passe</label>
              <input id="confirm" type="password" value={form.confirm} onChange={update('confirm')} />
            </div>

            <div className="alert alert-info small">
              Une fiche apprenant est créée automatiquement. Commencez par les quiz de votre
              filière : leurs résultats alimenteront progressivement votre profil pédagogique.
            </div>

            <button type="submit" className="btn btn-primary btn-block" disabled={busy}>
              {busy && <span className="spinner" />} Créer mon compte
            </button>
          </form>

          <p className="small muted mt-2" style={{ textAlign: 'center', marginBottom: 0 }}>
            Déjà inscrit ? <Link to="/connexion">Se connecter</Link>
          </p>
        </Card>
      </div>
    </div>
  )
}
