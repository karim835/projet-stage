import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from 'recharts'
import { learnerApi, readError } from '../services/api'
import { Alert, Card, Empty, Loading, ProfileBadge, RiskBadge, StatCard, formatDate, num } from '../components/ui'

const AXIS = { fontSize: 11, fill: '#6b7280' }
const GRID = '#eef0f3'

export default function LearnerDashboard() {
  const [data, setData] = useState(null)
  const [activities, setActivities] = useState([])
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [analyzing, setAnalyzing] = useState(false)

  const load = useCallback(async () => {
    try {
      setError('')
      const [dashboard, activity] = await Promise.all([
        learnerApi.myDashboard(),
        learnerApi.myActivity(),
      ])
      setData(dashboard.data)
      setActivities(activity.data)
    } catch (err) {
      setError(readError(err))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  async function reanalyze() {
    setAnalyzing(true)
    setError('')
    try {
      await learnerApi.analyzeMe()
      await load()
    } catch (err) {
      setError(readError(err))
    } finally {
      setAnalyzing(false)
    }
  }

  if (loading) return <Loading />
  if (error && !data) return <Alert type="error">{error}</Alert>
  if (!data) return null

  const l = data.learner
  const ref = data.stats_reference || {}

  // Progression : historique réel des analyses (du plus ancien au plus récent).
  const history = [...(l.profile_history || [])].reverse().map((p, i) => ({
    index: `#${i + 1}`,
    date: formatDate(p.created_at, false),
    confiance: p.confidence != null ? Math.round(p.confidence * 100) : null,
    profil: p.profile,
  }))

  // Scores réels des quiz enregistrés.
  const quizzes = activities
    .filter((a) => a.activity_type === 'quiz' && a.score != null)
    .map((a, i) => ({ label: `Q${i + 1}`, score: a.score, titre: a.title || 'Quiz', date: formatDate(a.created_at, false) }))

  const comparison = [
    { indicateur: 'Score moyen', vous: l.average_score, promotion: ref.average_score },
    { indicateur: 'Complétion', vous: l.completion_rate, promotion: ref.average_completion_rate },
    { indicateur: 'Temps (h)', vous: l.time_spent_hours, promotion: ref.average_time_spent },
    { indicateur: 'Satisfaction ×20', vous: l.satisfaction_score * 20, promotion: ref.average_satisfaction ? ref.average_satisfaction * 20 : null },
  ]

  const activeRecos = (l.recommendations || []).filter((r) => !r.completed)

  return (
    <div className="stack">
      <Alert type="error" onClose={() => setError('')}>{error}</Alert>

      <Card
        title={l.name}
        subtitle={`Identifiant ${l.student_id}${l.course_category ? ` · Filière ${l.course_category}` : ''}`}
        actions={
          <button type="button" className="btn btn-sm" onClick={reanalyze} disabled={analyzing}>
            {analyzing && <span className="spinner" />} Relancer l'analyse
          </button>
        }
      >
        <div className="row" style={{ gap: 8 }}>
          <ProfileBadge profile={l.profile} large />
          <RiskBadge level={l.risk_level} />
          {l.cluster != null && <span className="badge">Cluster K-Means n°{l.cluster}</span>}
          {l.confidence != null && <span className="badge">Confiance {Math.round(l.confidence * 100)} %</span>}
        </div>
        {l.explanation && <p className="muted mt-2" style={{ marginBottom: 0 }}>{l.explanation}</p>}
      </Card>

      <div className="grid grid-4">
        <StatCard label="Score moyen" value={num(l.average_score)} unit="/100" percent={l.average_score}
          hint={ref.average_score != null ? `Moyenne promotion : ${num(ref.average_score)}` : null} />
        <StatCard label="Taux de complétion" value={num(l.completion_rate)} unit="%" percent={l.completion_rate}
          hint={`${l.completed_courses} cours terminés sur ${l.total_courses || '—'}`} />
        <StatCard label="Temps d'apprentissage" value={num(l.time_spent_hours)} unit="h"
          hint={ref.average_time_spent != null ? `Moyenne promotion : ${num(ref.average_time_spent)} h` : null} />
        <StatCard label="Satisfaction" value={num(l.satisfaction_score, 1)} unit="/5" percent={l.satisfaction_score * 20} />
      </div>

      <div className="grid grid-4">
        <StatCard label="Quiz tentés" value={l.quiz_attempts} />
        <StatCard label="Quiz échoués" value={l.failed_quizzes}
          hint={l.failed_quizzes >= 3 ? 'Seuil de vigilance atteint' : null} />
        <StatCard label="Connexions / semaine" value={l.login_frequency}
          hint={l.login_frequency <= 1 ? 'Activité faible' : null} />
        <StatCard label="Recommandations actives" value={activeRecos.length} />
      </div>

      <div className="grid grid-2">
        <Card title="Progression dans les quiz" subtitle="Résultats calculés automatiquement après chaque passage">
          {quizzes.length === 0 ? (
            <Empty title="Aucun quiz passé">
              Passez votre premier quiz depuis <Link to="/apprenant/quiz">Mes quiz</Link> pour voir votre progression.
            </Empty>
          ) : (
            <ResponsiveContainer width="100%" height={230}>
              <LineChart data={quizzes} margin={{ top: 8, right: 12, bottom: 4, left: -18 }}>
                <CartesianGrid stroke={GRID} vertical={false} />
                <XAxis dataKey="label" tick={AXIS} axisLine={{ stroke: GRID }} tickLine={false} />
                <YAxis domain={[0, 100]} tick={AXIS} axisLine={false} tickLine={false} />
                <Tooltip
                  contentStyle={{ fontSize: 12, borderRadius: 8, border: '1px solid #e5e7eb' }}
                  formatter={(v) => [`${v}/100`, 'Score']}
                  labelFormatter={(_, p) => p?.[0]?.payload?.titre || ''}
                />
                <Line type="monotone" dataKey="score" stroke="#16a34a" strokeWidth={2} dot={{ r: 3 }} name="Score" />
              </LineChart>
            </ResponsiveContainer>
          )}
        </Card>

        <Card title="Vous et la promotion" subtitle="Comparaison avec la moyenne de tous les apprenants">
          <ResponsiveContainer width="100%" height={230}>
            <BarChart data={comparison} margin={{ top: 8, right: 12, bottom: 4, left: -18 }}>
              <CartesianGrid stroke={GRID} vertical={false} />
              <XAxis dataKey="indicateur" tick={{ ...AXIS, fontSize: 10 }} axisLine={{ stroke: GRID }} tickLine={false} />
              <YAxis tick={AXIS} axisLine={false} tickLine={false} />
              <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8, border: '1px solid #e5e7eb' }} formatter={(v) => num(v)} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Bar dataKey="vous" name="Vous" fill="#16a34a" radius={[3, 3, 0, 0]} />
              <Bar dataKey="promotion" name="Promotion" fill="#d1d5db" radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Card>
      </div>

      <div className="grid grid-2">
        <Card
          title="Recommandations en cours"
          subtitle={activeRecos.length ? activeRecos[0]?.reason : null}
          actions={<Link className="btn btn-sm" to="/apprenant/recommandations">Tout voir</Link>}
        >
          {activeRecos.length === 0 ? (
            <Empty title="Aucune recommandation active">Toutes vos ressources ont été marquées comme suivies.</Empty>
          ) : (
            <div className="stack" style={{ gap: 8 }}>
              {activeRecos.slice(0, 5).map((r) => (
                <div className="reco" key={r.id}>
                  <span className="badge badge-green">•</span>
                  <div style={{ flex: 1 }}>
                    <div className="reco-title">{r.content}</div>
                    {r.priority && <span className="badge small mt-1">Priorité {r.priority.toLowerCase()}</span>}
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>

        <Card title="Historique des analyses" subtitle="Chaque exécution des modèles est horodatée">
          {history.length <= 1 ? (
            <div className="stack" style={{ gap: 8 }}>
              {(l.profile_history || []).map((p) => (
                <div className="kv" key={p.id}>
                  <span>{formatDate(p.created_at)}</span>
                  <span><ProfileBadge profile={p.profile} /></span>
                </div>
              ))}
              <p className="small muted mt-1" style={{ marginBottom: 0 }}>
                Une seule analyse enregistrée pour l'instant. Le graphique apparaît dès la deuxième.
              </p>
            </div>
          ) : (
            <>
              <ResponsiveContainer width="100%" height={200}>
                <LineChart data={history} margin={{ top: 8, right: 12, bottom: 4, left: -18 }}>
                  <CartesianGrid stroke={GRID} vertical={false} />
                  <XAxis dataKey="index" tick={AXIS} axisLine={{ stroke: GRID }} tickLine={false} />
                  <YAxis domain={[0, 100]} tick={AXIS} axisLine={false} tickLine={false} />
                  <Tooltip
                    contentStyle={{ fontSize: 12, borderRadius: 8, border: '1px solid #e5e7eb' }}
                    formatter={(v) => [`${v} %`, 'Confiance du modèle']}
                    labelFormatter={(_, p) => `${p?.[0]?.payload?.profil} — ${p?.[0]?.payload?.date}`}
                  />
                  <Line type="monotone" dataKey="confiance" stroke="#2563eb" strokeWidth={2} dot={{ r: 3 }} name="Confiance" />
                </LineChart>
              </ResponsiveContainer>
              <p className="small muted mt-1" style={{ marginBottom: 0 }}>
                Confiance = probabilité attribuée par l'arbre de décision au profil retenu.
              </p>
            </>
          )}
        </Card>
      </div>
    </div>
  )
}
