import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { learnerApi, quizApi, readError } from '../services/api'
import { Alert, Card, Empty, Loading, ProfileBadge, RiskBadge, StatCard, formatDate, num } from '../components/ui'

const AXIS = { fontSize: 11, fill: '#6b7280' }
const GRID = '#eef0f3'

const EDITABLE = [
  { key: 'average_score', label: 'Score moyen /100', min: 0, max: 100, step: 'any' },
  { key: 'completion_rate', label: 'Taux de complétion %', min: 0, max: 100, step: 'any' },
  { key: 'time_spent_hours', label: 'Temps passé (h)', min: 0, max: 10000, step: 'any' },
  { key: 'quiz_attempts', label: 'Quiz tentés', min: 0, max: 1000, step: 1 },
  { key: 'failed_quizzes', label: 'Quiz échoués', min: 0, max: 1000, step: 1 },
  { key: 'login_frequency', label: 'Connexions / semaine', min: 0, max: 100, step: 1 },
  { key: 'satisfaction_score', label: 'Satisfaction /5', min: 1, max: 5, step: 'any' },
]

export default function LearnerDetail() {
  const { id } = useParams()
  const [learner, setLearner] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [busy, setBusy] = useState(false)
  const [editing, setEditing] = useState(false)
  const [form, setForm] = useState({})
  const [evaluating, setEvaluating] = useState(false)
  const [evaluation, setEvaluation] = useState({ score: '', title: '', duration_minutes: '' })

  const load = useCallback(async () => {
    try {
      setError('')
      const { data } = await learnerApi.detail(id)
      setLearner(data)
      setForm(Object.fromEntries(EDITABLE.map((f) => [f.key, data[f.key]])))
    } catch (err) {
      setError(readError(err))
    } finally {
      setLoading(false)
    }
  }, [id])

  useEffect(() => { load() }, [load])

  async function reanalyze() {
    setBusy(true); setError(''); setSuccess('')
    try {
      const previous = learner.profile
      const { data } = await learnerApi.analyze(id)
      setLearner(data)
      setSuccess(previous === data.profile
        ? `Analyse relancée. Profil confirmé : ${data.profile}.`
        : `Analyse relancée. Profil : ${previous} → ${data.profile}.`)
    } catch (err) {
      setError(readError(err))
    } finally {
      setBusy(false)
    }
  }

  async function save(event) {
    event.preventDefault()
    setBusy(true); setError(''); setSuccess('')
    try {
      const payload = Object.fromEntries(
        EDITABLE.map((f) => [f.key, Number(form[f.key])]).filter(([, v]) => !Number.isNaN(v)),
      )
      const { data } = await learnerApi.update(id, payload)
      setLearner(data)
      setForm(Object.fromEntries(EDITABLE.map((f) => [f.key, data[f.key]])))
      setEditing(false)
      setSuccess(`Indicateurs enregistrés et analyse relancée. Profil : ${data.profile}.`)
    } catch (err) {
      setError(readError(err))
    } finally {
      setBusy(false)
    }
  }

  async function saveEvaluation(event) {
    event.preventDefault()
    setError(''); setSuccess('')

    const score = Number(evaluation.score)
    if (evaluation.score === '' || Number.isNaN(score) || score < 0 || score > 100) {
      setError('La note doit être un nombre compris entre 0 et 100.')
      return
    }
    const duration = evaluation.duration_minutes === '' ? null : Number(evaluation.duration_minutes)

    setBusy(true)
    try {
      const { data } = await quizApi.recordEvaluation(id, {
        score,
        title: evaluation.title.trim() || null,
        duration_minutes: duration,
        passing_score: 50,
      })
      setSuccess(data.message)
      setEvaluation({ score: '', title: '', duration_minutes: '' })
      setEvaluating(false)
      await load()
    } catch (err) {
      setError(readError(err))
    } finally {
      setBusy(false)
    }
  }

  if (loading) return <Loading />
  if (!learner) return <Alert type="error">{error || 'Apprenant introuvable.'}</Alert>

  // Quiz corrigés automatiquement + évaluations saisies par le formateur.
  const quizzes = (learner.activities || [])
    .filter((a) => a.score != null)
    .map((a, i) => ({
      label: `${a.activity_type === 'evaluation' ? 'E' : 'Q'}${i + 1}`,
      score: a.score,
      titre: `${a.title || 'Quiz'}${a.activity_type === 'evaluation' ? ' (saisi par le formateur)' : ''}`,
    }))

  return (
    <div className="stack">
      <div className="row-between">
        <Link className="btn btn-sm" to="/formateur/apprenants">← Retour à la liste</Link>
        <div className="row">
          <button type="button" className="btn btn-sm" onClick={() => { setEvaluating((v) => !v); setEditing(false) }} disabled={busy}>
            {evaluating ? 'Annuler la saisie' : 'Saisir une évaluation'}
          </button>
          <button type="button" className="btn btn-sm" onClick={() => { setEditing((v) => !v); setEvaluating(false) }} disabled={busy}>
            {editing ? 'Annuler la modification' : 'Modifier les indicateurs'}
          </button>
          <button type="button" className="btn btn-sm btn-primary" onClick={reanalyze} disabled={busy}>
            {busy && <span className="spinner" />} Relancer l'analyse
          </button>
        </div>
      </div>

      <Alert type="error" onClose={() => setError('')}>{error}</Alert>
      <Alert type="success" onClose={() => setSuccess('')}>{success}</Alert>

      <Card
        title={learner.name}
        subtitle={[
          `Identifiant ${learner.student_id}`,
          learner.email,
          learner.course_category && `Filière ${learner.course_category}`,
          learner.has_account ? 'Compte actif' : 'Apprenant importé (sans compte)',
        ].filter(Boolean).join(' · ')}
      >
        <div className="row" style={{ gap: 8 }}>
          <ProfileBadge profile={learner.profile} large />
          <RiskBadge level={learner.risk_level} />
          {learner.cluster != null && <span className="badge">Cluster K-Means n°{learner.cluster}</span>}
          {learner.confidence != null && <span className="badge">Confiance {Math.round(learner.confidence * 100)} %</span>}
          {learner.reference_profile && (
            <span className="badge">Profil de référence du dataset : {learner.reference_profile}</span>
          )}
        </div>
        {learner.explanation && <p className="muted mt-2" style={{ marginBottom: 0 }}>{learner.explanation}</p>}
      </Card>

      {evaluating && (
        <Card
          title="Saisir une évaluation hors ligne"
          subtitle="Devoir, examen en présentiel ou tout travail noté en dehors de l'application"
        >
          <form onSubmit={saveEvaluation}>
            <div className="filters">
              <div className="field">
                <label htmlFor="eval-score">Note obtenue /100</label>
                <input id="eval-score" type="number" min="0" max="100" step="any" value={evaluation.score}
                  onChange={(e) => setEvaluation((v) => ({ ...v, score: e.target.value }))} />
                <span className="field-hint">Une note inférieure à 50 est comptée comme un échec.</span>
              </div>
              <div className="field">
                <label htmlFor="eval-title">Intitulé <span className="muted">(facultatif)</span></label>
                <input id="eval-title" value={evaluation.title} maxLength={200} placeholder="Ex. Examen blanc de mi-parcours"
                  onChange={(e) => setEvaluation((v) => ({ ...v, title: e.target.value }))} />
              </div>
              <div className="field">
                <label htmlFor="eval-duration">Durée en minutes <span className="muted">(facultatif)</span></label>
                <input id="eval-duration" type="number" min="0" max="1440" step="any" value={evaluation.duration_minutes}
                  onChange={(e) => setEvaluation((v) => ({ ...v, duration_minutes: e.target.value }))} />
              </div>
            </div>
            <button type="submit" className="btn btn-primary mt-2" disabled={busy}>
              {busy && <span className="spinner" />} Enregistrer la note
            </button>
          </form>
        </Card>
      )}

      {editing && (
        <Card title="Modifier les indicateurs" subtitle="L'analyse ML est relancée automatiquement après enregistrement">
          <form onSubmit={save}>
            <div className="filters">
              {EDITABLE.map((f) => (
                <div className="field" key={f.key}>
                  <label htmlFor={f.key}>{f.label}</label>
                  <input
                    id={f.key} type="number" min={f.min} max={f.max} step={f.step}
                    value={form[f.key] ?? ''}
                    onChange={(e) => setForm((s) => ({ ...s, [f.key]: e.target.value }))}
                  />
                </div>
              ))}
            </div>
            <button type="submit" className="btn btn-primary mt-2" disabled={busy}>
              {busy && <span className="spinner" />} Enregistrer et réanalyser
            </button>
          </form>
        </Card>
      )}

      <div className="grid grid-4">
        <StatCard label="Score moyen" value={num(learner.average_score)} unit="/100" percent={learner.average_score} />
        <StatCard label="Complétion" value={num(learner.completion_rate)} unit="%" percent={learner.completion_rate}
          hint={`${learner.completed_courses}/${learner.total_courses || '—'} cours`} />
        <StatCard label="Temps passé" value={num(learner.time_spent_hours)} unit="h" />
        <StatCard label="Satisfaction" value={num(learner.satisfaction_score, 1)} unit="/5" percent={learner.satisfaction_score * 20} />
      </div>

      <div className="grid grid-4">
        <StatCard label="Quiz tentés" value={learner.quiz_attempts} />
        <StatCard label="Quiz échoués" value={learner.failed_quizzes} />
        <StatCard label="Connexions / semaine" value={learner.login_frequency} />
        <StatCard label="Analyses enregistrées" value={learner.profile_history?.length ?? 0} />
      </div>

      <div className="grid grid-2">
        <Card title="Recommandations en cours" subtitle={learner.recommendations?.[0]?.reason}>
          {!learner.recommendations?.length ? <Empty title="Aucune recommandation" /> : (
            <div className="stack" style={{ gap: 8 }}>
              {learner.recommendations.map((r) => (
                <div className={`reco ${r.completed ? 'done' : ''}`} key={r.id}>
                  <div style={{ flex: 1 }}>
                    <div className="reco-title">{r.content}</div>
                    <div className="row" style={{ gap: 6, marginTop: 5 }}>
                      {r.priority && <span className="badge">Priorité {r.priority.toLowerCase()}</span>}
                      {r.completed && <span className="badge badge-green">Suivie</span>}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>

        <Card title="Historique des analyses" subtitle="Chaque exécution des modèles">
          {!learner.profile_history?.length ? <Empty title="Aucune analyse" /> : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr><th>Date</th><th>Profil</th><th className="text-right">Cluster</th><th className="text-right">Confiance</th><th>Source</th></tr>
                </thead>
                <tbody>
                  {learner.profile_history.map((p) => (
                    <tr key={p.id}>
                      <td className="nowrap">{formatDate(p.created_at)}</td>
                      <td><ProfileBadge profile={p.profile} /></td>
                      <td className="text-right num">{p.cluster ?? '—'}</td>
                      <td className="text-right num">{p.confidence != null ? `${Math.round(p.confidence * 100)} %` : '—'}</td>
                      <td><span className="badge">{p.source === 'model' ? 'Modèle entraîné' : 'Règles'}</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </div>

      {quizzes.length > 0 && (
        <Card title="Notes enregistrées" subtitle="Quiz corrigés automatiquement (Q) et évaluations saisies par le formateur (E)">
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={quizzes} margin={{ top: 8, right: 12, bottom: 4, left: -18 }}>
              <CartesianGrid stroke={GRID} vertical={false} />
              <XAxis dataKey="label" tick={AXIS} axisLine={{ stroke: GRID }} tickLine={false} />
              <YAxis domain={[0, 100]} tick={AXIS} axisLine={false} tickLine={false} />
              <Tooltip
                contentStyle={{ fontSize: 12, borderRadius: 8, border: '1px solid #e5e7eb' }}
                formatter={(v) => [`${v}/100`, 'Score']}
                labelFormatter={(_, p) => p?.[0]?.payload?.titre || ''}
              />
              <Bar dataKey="score" fill="#16a34a" radius={[3, 3, 0, 0]} name="Score" />
            </BarChart>
          </ResponsiveContainer>
        </Card>
      )}
    </div>
  )
}
