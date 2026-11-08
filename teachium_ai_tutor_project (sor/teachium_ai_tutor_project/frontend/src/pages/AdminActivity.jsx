import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { adminApi, readError } from '../services/api'
import { Alert, Card, Empty, Loading, ProfileBadge, formatDate } from '../components/ui'

const TYPE_LABEL = {
  profile_analysis: { label: 'Analyse de profil', tone: 'badge-green' },
  chat_message: { label: 'Question AI Tutor', tone: 'badge-blue' },
}

export default function AdminActivity() {
  const [events, setEvents] = useState([])
  const [recos, setRecos] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    Promise.allSettled([adminApi.activity(), adminApi.recentRecommendations()])
      .then(([a, r]) => {
        if (a.status === 'fulfilled') setEvents(a.value.data)
        else setError(readError(a.reason))
        if (r.status === 'fulfilled') setRecos(r.value.data)
      })
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <Loading />

  return (
    <div className="stack">
      <Alert type="error" onClose={() => setError('')}>{error}</Alert>

      <Card title="Derniers événements" subtitle="Analyses de profil et questions posées à l'AI Tutor, lues en base">
        {events.length === 0 ? (
          <Empty title="Aucun événement enregistré">
            Les événements apparaissent dès qu'une analyse est lancée ou qu'une question est posée au tuteur.
          </Empty>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr><th>Date</th><th>Type</th><th>Événement</th><th>Apprenant</th></tr>
              </thead>
              <tbody>
                {events.map((e, i) => {
                  const meta = TYPE_LABEL[e.type] || { label: e.type, tone: '' }
                  return (
                    <tr key={`${e.type}-${e.learner_id}-${i}`}>
                      <td className="nowrap small muted">{formatDate(e.created_at)}</td>
                      <td><span className={`badge ${meta.tone}`}>{meta.label}</span></td>
                      <td>{e.label}</td>
                      <td>
                        <Link className="mono" to={`/formateur/apprenants/${e.learner_id}`}>{e.learner}</Link>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <Card title="Recommandations récentes" subtitle="Sorties du moteur de recommandation">
        {recos.length === 0 ? <Empty title="Aucune recommandation" /> : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr><th>Date</th><th>Ressource</th><th>Profil</th><th>Priorité</th><th>État</th></tr>
              </thead>
              <tbody>
                {recos.map((r) => (
                  <tr key={r.id}>
                    <td className="nowrap small muted">{formatDate(r.created_at)}</td>
                    <td>{r.content}</td>
                    <td><ProfileBadge profile={r.profile} /></td>
                    <td>{r.priority || '—'}</td>
                    <td>{r.completed ? <span className="badge badge-green">Suivie</span> : <span className="badge">En cours</span>}</td>
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
