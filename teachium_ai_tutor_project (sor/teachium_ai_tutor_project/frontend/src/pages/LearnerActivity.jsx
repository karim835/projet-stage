import { useCallback, useEffect, useState } from 'react'
import { learnerApi, readError } from '../services/api'
import { Alert, Card, Empty, Loading, ProfileBadge, formatDate, num } from '../components/ui'

const TYPES = [
  { value: 'quiz', label: 'Quiz passé', hint: 'Score obligatoire. Met à jour la moyenne et le compteur d\'échecs.' },
  { value: 'course', label: 'Cours terminé', hint: 'Augmente le nombre de cours terminés et le taux de complétion.' },
  { value: 'session', label: 'Session de travail', hint: 'Ajoute seulement du temps d\'apprentissage.' },
]

const TYPE_LABEL = { quiz: 'Quiz', course: 'Cours', session: 'Session' }

export default function LearnerActivity() {
  const [activities, setActivities] = useState([])
  const [learner, setLearner] = useState(null)
  const [form, setForm] = useState({ activity_type: 'quiz', title: '', score: '', duration_minutes: '' })
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  const load = useCallback(async () => {
    try {
      setError('')
      const [activity, dashboard] = await Promise.all([learnerApi.myActivity(), learnerApi.myDashboard()])
      setActivities(activity.data)
      setLearner(dashboard.data.learner)
    } catch (err) {
      setError(readError(err))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const update = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }))

  async function submit(event) {
    event.preventDefault()
    setError('')
    setSuccess('')

    if (form.activity_type === 'quiz' && form.score === '') {
      setError('Un quiz doit être enregistré avec un score entre 0 et 100.')
      return
    }
    const score = form.score === '' ? null : Number(form.score)
    if (score !== null && (Number.isNaN(score) || score < 0 || score > 100)) {
      setError('Le score doit être un nombre compris entre 0 et 100.')
      return
    }
    const duration = form.duration_minutes === '' ? null : Number(form.duration_minutes)
    if (duration !== null && (Number.isNaN(duration) || duration < 0 || duration > 1440)) {
      setError('La durée doit être comprise entre 0 et 1440 minutes.')
      return
    }

    setSaving(true)
    const before = learner
    try {
      const { data } = await learnerApi.recordActivity({
        activity_type: form.activity_type,
        title: form.title.trim() || null,
        score,
        duration_minutes: duration,
      })
      setLearner(data)
      const changed = before && before.profile !== data.profile
      setSuccess(
        changed
          ? `Activité enregistrée. Votre profil est passé de « ${before.profile} » à « ${data.profile} » et vos recommandations ont été régénérées.`
          : `Activité enregistrée. Score moyen recalculé : ${num(data.average_score)}/100. Profil confirmé : ${data.profile}.`,
      )
      setForm({ activity_type: form.activity_type, title: '', score: '', duration_minutes: '' })
      const refreshed = await learnerApi.myActivity()
      setActivities(refreshed.data)
    } catch (err) {
      setError(readError(err))
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <Loading />

  const selected = TYPES.find((t) => t.value === form.activity_type)

  return (
    <div className="stack">
      <Alert type="error" onClose={() => setError('')}>{error}</Alert>
      <Alert type="success" onClose={() => setSuccess('')}>{success}</Alert>

      <div className="grid grid-2">
        <Card title="Enregistrer une activité" subtitle="Les indicateurs et le profil sont recalculés immédiatement">
          <form onSubmit={submit}>
            <div className="field">
              <label htmlFor="type">Type d'activité</label>
              <select id="type" value={form.activity_type} onChange={update('activity_type')}>
                {TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
              </select>
              <span className="field-hint">{selected?.hint}</span>
            </div>

            <div className="field">
              <label htmlFor="title">Intitulé <span className="muted">(facultatif)</span></label>
              <input id="title" value={form.title} onChange={update('title')} placeholder="Ex. Quiz Python — les boucles" maxLength={255} />
            </div>

            {form.activity_type === 'quiz' && (
              <div className="field">
                <label htmlFor="score">Score obtenu /100</label>
                <input id="score" type="number" min="0" max="100" step="any" value={form.score} onChange={update('score')} />
                <span className="field-hint">Un score inférieur à 50 est comptabilisé comme un quiz échoué.</span>
              </div>
            )}

            <div className="field">
              <label htmlFor="duration">Durée en minutes <span className="muted">(facultatif)</span></label>
              <input id="duration" type="number" min="0" max="1440" step="any" value={form.duration_minutes} onChange={update('duration_minutes')} />
            </div>

            <button type="submit" className="btn btn-primary btn-block" disabled={saving}>
              {saving && <span className="spinner" />} Enregistrer et relancer l'analyse
            </button>
          </form>
        </Card>

        <Card title="Indicateurs actuels" subtitle="Mis à jour après chaque activité">
          {learner && (
            <>
              <div className="row mb-2" style={{ gap: 8 }}>
                <ProfileBadge profile={learner.profile} large />
                {learner.confidence != null && (
                  <span className="badge">Confiance {Math.round(learner.confidence * 100)} %</span>
                )}
              </div>
              <div className="kv"><span>Score moyen</span><span>{num(learner.average_score)}/100</span></div>
              <div className="kv"><span>Taux de complétion</span><span>{num(learner.completion_rate)} %</span></div>
              <div className="kv"><span>Cours terminés</span><span>{learner.completed_courses} / {learner.total_courses || '—'}</span></div>
              <div className="kv"><span>Quiz tentés</span><span>{learner.quiz_attempts}</span></div>
              <div className="kv"><span>Quiz échoués</span><span>{learner.failed_quizzes}</span></div>
              <div className="kv"><span>Temps d'apprentissage</span><span>{num(learner.time_spent_hours)} h</span></div>
              <div className="kv"><span>Connexions / semaine</span><span>{learner.login_frequency}</span></div>

            </>
          )}
        </Card>
      </div>

      <Card title={`Historique d'activité (${activities.length})`}>
        {activities.length === 0 ? (
          <Empty title="Aucune activité enregistrée">
            Utilisez le formulaire ci-dessus pour enregistrer votre premier quiz ou cours terminé.
          </Empty>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Type</th>
                  <th>Intitulé</th>
                  <th className="text-right">Score</th>
                  <th className="text-right">Durée</th>
                </tr>
              </thead>
              <tbody>
                {[...activities].reverse().map((a) => (
                  <tr key={a.id}>
                    <td className="nowrap">{formatDate(a.created_at)}</td>
                    <td><span className="badge">{TYPE_LABEL[a.activity_type] || a.activity_type}</span></td>
                    <td>{a.title || '—'}</td>
                    <td className="text-right num">{a.score != null ? `${num(a.score)}/100` : '—'}</td>
                    <td className="text-right num">{a.duration_minutes != null ? `${num(a.duration_minutes, 0)} min` : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  )
}
