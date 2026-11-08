import { useState } from 'react'
import { mlApi, readError } from '../services/api'
import { Alert, Card, Empty, ProfileBadge, RiskBadge } from '../components/ui'

const FIELDS = [
  { key: 'average_score', label: 'Score moyen /100', min: 0, max: 100, step: 'any' },
  { key: 'completion_rate', label: 'Taux de complétion %', min: 0, max: 100, step: 'any' },
  { key: 'time_spent_hours', label: 'Temps passé (heures)', min: 0, max: 500, step: 'any' },
  { key: 'quiz_attempts', label: 'Quiz tentés', min: 0, max: 100, step: 1 },
  { key: 'failed_quizzes', label: 'Quiz échoués', min: 0, max: 100, step: 1 },
  { key: 'login_frequency', label: 'Connexions / semaine', min: 0, max: 30, step: 1 },
  { key: 'satisfaction_score', label: 'Satisfaction /5', min: 1, max: 5, step: 'any' },
]

const PRESETS = {
  'Débutant': { average_score: 55, completion_rate: 50, time_spent_hours: 18, quiz_attempts: 4, failed_quizzes: 2, login_frequency: 3, satisfaction_score: 3 },
  'Moyen': { average_score: 70, completion_rate: 65, time_spent_hours: 25, quiz_attempts: 6, failed_quizzes: 1, login_frequency: 4, satisfaction_score: 3.5 },
  'En difficulté': { average_score: 42, completion_rate: 35, time_spent_hours: 12, quiz_attempts: 5, failed_quizzes: 3, login_frequency: 2, satisfaction_score: 2.5 },
  'Avancé': { average_score: 88, completion_rate: 90, time_spent_hours: 40, quiz_attempts: 10, failed_quizzes: 0, login_frequency: 6, satisfaction_score: 4.5 },
  'Peu actif': { average_score: 50, completion_rate: 22, time_spent_hours: 8, quiz_attempts: 2, failed_quizzes: 1, login_frequency: 1, satisfaction_score: 2.2 },
}

export default function Simulator() {
  const [form, setForm] = useState(PRESETS['En difficulté'])
  const [profile, setProfile] = useState(null)
  const [reco, setReco] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const update = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }))

  async function run(event) {
    event.preventDefault()
    setBusy(true); setError(''); setProfile(null); setReco(null)

    const payload = {}
    for (const field of FIELDS) {
      const value = Number(form[field.key])
      if (Number.isNaN(value) || value < field.min || value > field.max) {
        setBusy(false)
        setError(`« ${field.label} » doit être un nombre entre ${field.min} et ${field.max}.`)
        return
      }
      payload[field.key] = value
    }

    try {
      const { data: analysis } = await mlApi.analyzeProfile(payload)
      setProfile(analysis)
      const { data: recommendation } = await mlApi.recommend({
        profile: analysis.profile,
        average_score: payload.average_score,
        completion_rate: payload.completion_rate,
        failed_quizzes: payload.failed_quizzes,
        satisfaction_score: payload.satisfaction_score,
      })
      setReco(recommendation)
    } catch (err) {
      setError(readError(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="stack">
      <Alert type="error" onClose={() => setError('')}>{error}</Alert>

      <div className="grid grid-2">
        <Card title="Données d'entrée" subtitle="Les 7 variables utilisées par les modèles">
          <div className="row mb-2">
            {Object.keys(PRESETS).map((name) => (
              <button key={name} type="button" className="chip" onClick={() => setForm(PRESETS[name])}>
                Exemple « {name} »
              </button>
            ))}
          </div>

          <form onSubmit={run}>
            <div className="filters">
              {FIELDS.map((f) => (
                <div className="field" key={f.key}>
                  <label htmlFor={f.key}>{f.label}</label>
                  <input
                    id={f.key} type="number" min={f.min} max={f.max} step={f.step}
                    value={form[f.key]} onChange={update(f.key)}
                  />
                </div>
              ))}
            </div>
            <button type="submit" className="btn btn-primary mt-2" disabled={busy}>
              {busy && <span className="spinner" />} Analyser
            </button>
          </form>
        </Card>

        <div className="stack">
          <Card title="Profil détecté" subtitle="Arbre de décision + clustering K-Means">
            {!profile ? <Empty title="Aucune analyse">Renseignez les valeurs puis cliquez sur « Analyser ».</Empty> : (
              <>
                <div className="row" style={{ gap: 8 }}>
                  <ProfileBadge profile={profile.profile} large />
                  <RiskBadge level={profile.risk_level} />
                </div>
                <div className="mt-2">
                  <div className="kv"><span>Cluster K-Means</span><span>{profile.cluster ?? '—'}</span></div>
                  <div className="kv">
                    <span>Confiance de l'arbre</span>
                    <span>{profile.confidence != null ? `${Math.round(profile.confidence * 100)} %` : '—'}</span>
                  </div>
                  <div className="kv">
                    <span>Source de la décision</span>
                    <span>{profile.source === 'model' ? 'Modèle entraîné (.joblib)' : 'Règles de repli'}</span>
                  </div>
                </div>
                <p className="muted mt-2" style={{ marginBottom: 0 }}>{profile.explanation}</p>
              </>
            )}
          </Card>

          <Card title="Recommandations générées" subtitle={reco?.reason}>
            {!reco ? <Empty title="En attente d'analyse" /> : (
              <>
                <span className={`badge ${reco.priority === 'Haute' ? 'badge-red' : reco.priority === 'Moyenne' ? 'badge-amber' : ''}`}>
                  Priorité {reco.priority.toLowerCase()}
                </span>
                <div className="stack mt-2" style={{ gap: 8 }}>
                  {reco.recommended_content.map((c) => (
                    <div className="reco" key={c}>
                      <span className="badge badge-green">•</span>
                      <div className="reco-title">{c}</div>
                    </div>
                  ))}
                </div>
              </>
            )}
          </Card>
        </div>
      </div>
    </div>
  )
}
