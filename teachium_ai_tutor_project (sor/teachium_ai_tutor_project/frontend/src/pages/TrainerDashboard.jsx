import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  Bar, BarChart, Cell, CartesianGrid, Legend, Pie, PieChart, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from 'recharts'
import { readError, statsApi } from '../services/api'
import { Alert, Card, Empty, Loading, PROFILE_COLOR, StatCard, num } from '../components/ui'

const AXIS = { fontSize: 11, fill: '#6b7280' }
const GRID = '#eef0f3'
const TOOLTIP = { fontSize: 12, borderRadius: 8, border: '1px solid #e5e7eb' }

export default function TrainerDashboard() {
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    statsApi.dashboard()
      .then(({ data }) => setStats(data))
      .catch((err) => setError(readError(err)))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <Loading />
  if (error) return <Alert type="error">{error}</Alert>
  if (!stats) return null

  const profileData = Object.entries(stats.learners_by_profile || {}).map(([name, value]) => ({ name, value }))
  const perf = stats.performance_by_profile || []
  const risk = stats.risk_indicators || {}

  return (
    <div className="stack">
      {stats.source === 'csv_fallback' && (
        <Alert type="warn">
          Aucun apprenant enregistré : les chiffres affichés sont des données de démonstration.
        </Alert>
      )}

      <div className="grid grid-4">
        <StatCard label="Apprenants suivis" value={stats.total_learners} />
        <StatCard label="Score moyen" value={num(stats.average_score)} unit="/100" percent={stats.average_score} />
        <StatCard label="Complétion moyenne" value={num(stats.average_completion_rate)} unit="%" percent={stats.average_completion_rate} />
        <StatCard label="Satisfaction moyenne" value={num(stats.average_satisfaction, 2)} unit="/5" percent={stats.average_satisfaction * 20} />
      </div>

      <div className="grid grid-4">
        <StatCard label="En difficulté" value={stats.learners_in_difficulty}
          hint={stats.total_learners ? `${num((stats.learners_in_difficulty / stats.total_learners) * 100)} % de la promotion` : null} />
        <StatCard label="Peu actifs" value={stats.inactive_learners}
          hint={stats.total_learners ? `${num((stats.inactive_learners / stats.total_learners) * 100)} % de la promotion` : null} />
        <StatCard label="Avancés" value={stats.advanced_learners}
          hint={stats.total_learners ? `${num((stats.advanced_learners / stats.total_learners) * 100)} % de la promotion` : null} />
        <StatCard label="Temps moyen" value={num(stats.average_time_spent)} unit="h" />
      </div>

      <div className="grid grid-2">
        <Card title="Répartition des profils" subtitle="Profil courant calculé par l'arbre de décision">
          {profileData.length === 0 ? <Empty title="Aucun profil calculé" /> : (
            <>
              <ResponsiveContainer width="100%" height={250}>
                <PieChart>
                  <Pie data={profileData} dataKey="value" nameKey="name" cx="50%" cy="50%"
                    innerRadius={55} outerRadius={90} paddingAngle={2}>
                    {profileData.map((entry) => (
                      <Cell key={entry.name} fill={PROFILE_COLOR[entry.name] || '#9ca3af'} />
                    ))}
                  </Pie>
                  <Tooltip contentStyle={TOOLTIP} formatter={(v, n) => [`${v} apprenants`, n]} />
                </PieChart>
              </ResponsiveContainer>
              <div className="legend">
                {profileData.map((p) => (
                  <span key={p.name}>
                    <i style={{ background: PROFILE_COLOR[p.name] || '#9ca3af' }} />
                    {p.name} — {p.value}
                  </span>
                ))}
              </div>
            </>
          )}
        </Card>

        <Card title="Distribution des scores" subtitle="Nombre d'apprenants par tranche de score">
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={stats.score_histogram || []} margin={{ top: 8, right: 12, bottom: 4, left: -18 }}>
              <CartesianGrid stroke={GRID} vertical={false} />
              <XAxis dataKey="range" tick={AXIS} axisLine={{ stroke: GRID }} tickLine={false} />
              <YAxis tick={AXIS} axisLine={false} tickLine={false} />
              <Tooltip contentStyle={TOOLTIP} formatter={(v) => [`${v} apprenants`, 'Effectif']} />
              <Bar dataKey="count" fill="#16a34a" radius={[3, 3, 0, 0]} name="Apprenants" />
            </BarChart>
          </ResponsiveContainer>
        </Card>
      </div>

      <Card title="Performance par profil" subtitle="Moyennes réelles calculées en base pour chaque groupe">
        {perf.length === 0 ? <Empty title="Aucune donnée" /> : (
          <>
            <ResponsiveContainer width="100%" height={270}>
              <BarChart data={perf} margin={{ top: 8, right: 12, bottom: 4, left: -18 }}>
                <CartesianGrid stroke={GRID} vertical={false} />
                <XAxis dataKey="profile" tick={AXIS} axisLine={{ stroke: GRID }} tickLine={false} />
                <YAxis tick={AXIS} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={TOOLTIP} formatter={(v) => num(v)} />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Bar dataKey="average_score" name="Score moyen /100" fill="#16a34a" radius={[3, 3, 0, 0]} />
                <Bar dataKey="average_completion" name="Complétion %" fill="#2563eb" radius={[3, 3, 0, 0]} />
                <Bar dataKey="average_time_spent" name="Temps (h)" fill="#d1d5db" radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>

            <div className="table-wrap mt-2">
              <table>
                <thead>
                  <tr>
                    <th>Profil</th>
                    <th className="text-right">Apprenants</th>
                    <th className="text-right">Score moyen</th>
                    <th className="text-right">Complétion</th>
                    <th className="text-right">Satisfaction</th>
                    <th className="text-right">Temps moyen</th>
                  </tr>
                </thead>
                <tbody>
                  {perf.map((p) => (
                    <tr key={p.profile}>
                      <td>
                        <span className="badge" style={{ borderColor: PROFILE_COLOR[p.profile], color: PROFILE_COLOR[p.profile] }}>
                          {p.profile}
                        </span>
                      </td>
                      <td className="text-right num">{p.learners}</td>
                      <td className="text-right num">{num(p.average_score)}</td>
                      <td className="text-right num">{num(p.average_completion)} %</td>
                      <td className="text-right num">{num(p.average_satisfaction, 2)}/5</td>
                      <td className="text-right num">{num(p.average_time_spent)} h</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </Card>

      <Card title="Indicateurs de risque" subtitle="Comptages directs en base — cliquez pour filtrer la liste des apprenants">
        <div className="grid grid-4">
          <Link to="/formateur/apprenants?max_score=50" style={{ textDecoration: 'none', color: 'inherit' }}>
            <StatCard label="Score inférieur à 50" value={risk.low_score_count ?? 0} hint="Voir la liste →" />
          </Link>
          <Link to="/formateur/apprenants?max_completion=40" style={{ textDecoration: 'none', color: 'inherit' }}>
            <StatCard label="Complétion inférieure à 40 %" value={risk.low_completion_count ?? 0} hint="Voir la liste →" />
          </Link>
          <Link to="/formateur/apprenants?profile=En%20difficult%C3%A9" style={{ textDecoration: 'none', color: 'inherit' }}>
            <StatCard label="3 quiz échoués ou plus" value={risk.high_failed_quizzes_count ?? 0} hint="Voir les apprenants en difficulté →" />
          </Link>
          <Link to="/formateur/apprenants?max_login=1" style={{ textDecoration: 'none', color: 'inherit' }}>
            <StatCard label="1 connexion / semaine ou moins" value={risk.rarely_connected_count ?? 0} hint="Voir la liste →" />
          </Link>
        </div>
      </Card>
    </div>
  )
}
