import { useCallback, useEffect, useState } from 'react'
import { learnerApi, readError, recommendationApi } from '../services/api'
import { Alert, Card, Empty, Loading, ProfileBadge, formatDate } from '../components/ui'

export default function Recommendations() {
  const [current, setCurrent] = useState([])
  const [history, setHistory] = useState([])
  const [learner, setLearner] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [busyId, setBusyId] = useState(null)
  const [regenerating, setRegenerating] = useState(false)

  const load = useCallback(async () => {
    try {
      setError('')
      const [mine, hist, dashboard] = await Promise.all([
        recommendationApi.mine(),
        recommendationApi.history(),
        learnerApi.myDashboard(),
      ])
      setCurrent(mine.data)
      setHistory(hist.data)
      setLearner(dashboard.data.learner)
    } catch (err) {
      setError(readError(err))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  async function toggle(reco) {
    setBusyId(reco.id)
    setError('')
    try {
      const { data } = await recommendationApi.complete(reco.id, !reco.completed)
      setCurrent((list) => list.map((r) => (r.id === data.id ? data : r)))
      setHistory((list) => list.map((r) => (r.id === data.id ? data : r)))
    } catch (err) {
      setError(readError(err))
    } finally {
      setBusyId(null)
    }
  }

  async function regenerate() {
    setRegenerating(true)
    setError('')
    try {
      await learnerApi.analyzeMe()
      await load()
    } catch (err) {
      setError(readError(err))
    } finally {
      setRegenerating(false)
    }
  }

  if (loading) return <Loading />

  const currentIds = new Set(current.map((r) => r.id))
  const older = history.filter((r) => !currentIds.has(r.id))
  const done = current.filter((r) => r.completed).length

  return (
    <div className="stack">
      <Alert type="error" onClose={() => setError('')}>{error}</Alert>

      {learner && (
        <Card title="Base de la recommandation" subtitle="Ce que le moteur a pris en compte">
          <div className="row" style={{ gap: 8 }}>
            <ProfileBadge profile={learner.profile} large />
            <span className="badge">Score {learner.average_score?.toFixed(1)}/100</span>
            <span className="badge">Complétion {learner.completion_rate?.toFixed(1)} %</span>
            <span className="badge">{learner.failed_quizzes} quiz échoué(s)</span>
            <span className="badge">Satisfaction {learner.satisfaction_score?.toFixed(1)}/5</span>
          </div>
          {current[0]?.reason && <p className="muted mt-2" style={{ marginBottom: 0 }}>{current[0].reason}</p>}
        </Card>
      )}

      <Card
        title={`Recommandations actuelles (${done}/${current.length} suivies)`}
        subtitle={current[0] ? `Générées le ${formatDate(current[0].created_at)}` : null}
        actions={
          <button type="button" className="btn btn-sm" onClick={regenerate} disabled={regenerating}>
            {regenerating && <span className="spinner" />} Régénérer
          </button>
        }
      >
        {current.length === 0 ? (
          <Empty title="Aucune recommandation">Lancez une analyse pour générer vos ressources.</Empty>
        ) : (
          <div className="stack" style={{ gap: 9 }}>
            {current.map((r) => (
              <div className={`reco ${r.completed ? 'done' : ''}`} key={r.id}>
                <div style={{ flex: 1 }}>
                  <div className="reco-title">{r.content}</div>
                  <div className="row" style={{ gap: 6, marginTop: 6 }}>
                    {r.priority && (
                      <span className={`badge ${r.priority === 'Haute' ? 'badge-red' : r.priority === 'Moyenne' ? 'badge-amber' : ''}`}>
                        Priorité {r.priority.toLowerCase()}
                      </span>
                    )}
                    {r.profile && <span className="badge">{r.profile}</span>}
                    {r.completed && r.completed_at && (
                      <span className="badge badge-green">Suivie le {formatDate(r.completed_at, false)}</span>
                    )}
                  </div>
                </div>
                <button
                  type="button"
                  className={`btn btn-sm ${r.completed ? '' : 'btn-primary'}`}
                  onClick={() => toggle(r)}
                  disabled={busyId === r.id}
                >
                  {busyId === r.id && <span className="spinner" />}
                  {r.completed ? 'Annuler' : 'Marquer comme suivie'}
                </button>
              </div>
            ))}
          </div>
        )}
      </Card>

      {older.length > 0 && (
        <Card title="Recommandations précédentes" subtitle="Générées lors d'analyses antérieures">
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Ressource</th>
                  <th>Profil</th>
                  <th>Priorité</th>
                  <th>Date</th>
                  <th>État</th>
                </tr>
              </thead>
              <tbody>
                {older.map((r) => (
                  <tr key={r.id}>
                    <td>{r.content}</td>
                    <td><ProfileBadge profile={r.profile} /></td>
                    <td>{r.priority || '—'}</td>
                    <td className="nowrap">{formatDate(r.created_at, false)}</td>
                    <td>
                      {r.completed
                        ? <span className="badge badge-green">Suivie</span>
                        : <span className="badge">Non suivie</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  )
}
