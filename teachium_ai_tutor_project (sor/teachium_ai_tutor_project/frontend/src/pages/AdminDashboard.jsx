import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { adminApi, readError, statsApi } from '../services/api'
import { Alert, Card, Empty, Loading, ProfileBadge, StatCard, formatDate, num } from '../components/ui'

const AXIS = { fontSize: 11, fill: '#6b7280' }
const GRID = '#eef0f3'

const ROLE_LABEL = { learner: 'Apprenants', trainer: 'Formateurs', administrator: 'Administrateurs' }

export default function AdminDashboard() {
  const [overview, setOverview] = useState(null)
  const [stats, setStats] = useState(null)
  const [recos, setRecos] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    Promise.allSettled([
      adminApi.overview(),
      statsApi.dashboard(),
      adminApi.recentRecommendations(),
    ])
      .then(([o, s, r]) => {
        if (o.status === 'fulfilled') setOverview(o.value.data)
        else setError(readError(o.reason))
        if (s.status === 'fulfilled') setStats(s.value.data)
        if (r.status === 'fulfilled') setRecos(r.value.data)
      })
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <Loading />
  if (error && !overview) return <Alert type="error">{error}</Alert>
  if (!overview) return null

  const roleData = Object.entries(overview.users_by_role || {}).map(([role, count]) => ({
    role: ROLE_LABEL[role] || role,
    count,
  }))

  return (
    <div className="stack">
      <Alert type="error" onClose={() => setError('')}>{error}</Alert>

      <div className="grid grid-4">
        <StatCard label="Comptes utilisateurs" value={overview.users_total} hint={`${overview.users_active} actifs`} />
        <StatCard label="Fiches apprenants" value={overview.learners_total} hint={`${overview.learners_with_account} avec un compte`} />
        <StatCard label="Analyses de profil" value={overview.profiles_computed} hint={`${overview.analyses_last_7_days} sur 7 jours`} />
        <StatCard label="Recommandations" value={overview.recommendations_total} hint={`${overview.recommendations_completed} marquées suivies`} />
      </div>

      <div className="grid grid-4">
        <StatCard label="Messages AI Tutor" value={overview.chat_messages_total} hint={`${overview.messages_last_7_days} sur 7 jours`} />
        <StatCard label="Score moyen promotion" value={num(stats?.average_score)} unit="/100" />
        <StatCard label="Apprenants en difficulté" value={stats?.learners_in_difficulty ?? '—'} />
        <StatCard label="Apprenants peu actifs" value={stats?.inactive_learners ?? '—'} />
      </div>

      <div className="grid grid-2">
        <Card
          title="Comptes par rôle"
          actions={<Link className="btn btn-sm" to="/admin/utilisateurs">Gérer les comptes</Link>}
        >
          {roleData.length === 0 ? <Empty title="Aucun compte" /> : (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={roleData} margin={{ top: 8, right: 12, bottom: 4, left: -18 }}>
                <CartesianGrid stroke={GRID} vertical={false} />
                <XAxis dataKey="role" tick={AXIS} axisLine={{ stroke: GRID }} tickLine={false} />
                <YAxis allowDecimals={false} tick={AXIS} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8, border: '1px solid #e5e7eb' }} />
                <Bar dataKey="count" fill="#16a34a" radius={[3, 3, 0, 0]} name="Comptes" />
              </BarChart>
            </ResponsiveContainer>
          )}
        </Card>

        <Card
          title="Dernières recommandations générées"
          subtitle="Produites par le moteur de recommandation"
          actions={<Link className="btn btn-sm" to="/admin/activite">Activité complète</Link>}
        >
          {recos.length === 0 ? <Empty title="Aucune recommandation" /> : (
            <div className="table-wrap" style={{ maxHeight: 240, overflowY: 'auto' }}>
              <table>
                <thead><tr><th>Ressource</th><th>Profil</th><th>Date</th></tr></thead>
                <tbody>
                  {recos.slice(0, 12).map((r) => (
                    <tr key={r.id}>
                      <td>{r.content}</td>
                      <td><ProfileBadge profile={r.profile} /></td>
                      <td className="nowrap small muted">{formatDate(r.created_at, false)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </div>
    </div>
  )
}
