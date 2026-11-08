import { useEffect, useState } from 'react'
import {
  Bar, BarChart, CartesianGrid, Cell, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { readError, statsApi } from '../services/api'
import { Alert, Card, Empty, Loading, PROFILE_COLOR, StatCard, num } from '../components/ui'

const AXIS = { fontSize: 11, fill: '#6b7280' }
const GRID = '#eef0f3'
const TOOLTIP = { fontSize: 12, borderRadius: 8, border: '1px solid #e5e7eb' }

const FEATURE_LABELS = {
  average_score: 'Score moyen',
  time_spent_hours: 'Temps passé',
  completion_rate: 'Taux de complétion',
  quiz_attempts: 'Quiz tentés',
  failed_quizzes: 'Quiz échoués',
  login_frequency: 'Connexions',
  satisfaction_score: 'Satisfaction',
}

export default function ModelEvaluation() {
  const [metrics, setMetrics] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    statsApi.modelEvaluation()
      .then(({ data }) => setMetrics(data))
      .catch((err) => setError(readError(err)))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <Loading />
  if (error) return <Alert type="error">{error}</Alert>
  if (!metrics) return null

  if (metrics.message && metrics.accuracy === undefined) {
    return (
      <Alert type="warn">
        Les résultats d’évaluation ne sont pas disponibles pour le moment.
      </Alert>
    )
  }

  const report = metrics.classification_report || {}
  const perClass = Object.entries(report)
    .filter(([k, v]) => typeof v === 'object' && !['accuracy', 'macro avg', 'weighted avg'].includes(k))
    .map(([profile, v]) => ({
      profile,
      precision: Math.round((v.precision || 0) * 100),
      recall: Math.round((v.recall || 0) * 100),
      f1: Math.round((v['f1-score'] || 0) * 100),
      support: v.support,
    }))

  const importances = (metrics.feature_importances || []).map((f) => ({
    ...f,
    label: FEATURE_LABELS[f.feature] || f.feature,
    pct: Math.round(f.importance * 1000) / 10,
  }))

  const confusion = metrics.confusion_matrix

  return (
    <div className="stack">
      <div className="grid grid-4">
        <StatCard label="Exactitude (Accuracy)" value={num(metrics.accuracy * 100)} unit="%" percent={metrics.accuracy * 100}
          hint="Pourcentage de prédictions correctes" />
        <StatCard label="Précision pondérée" value={num(metrics.precision_weighted * 100)} unit="%" percent={metrics.precision_weighted * 100}
          hint="Fiabilité des profils annoncés" />
        <StatCard label="Rappel pondéré" value={num(metrics.recall_weighted * 100)} unit="%" percent={metrics.recall_weighted * 100}
          hint="Capacité à détecter les vrais cas" />
        <StatCard label="F1-score pondéré" value={num(metrics.f1_weighted * 100)} unit="%" percent={metrics.f1_weighted * 100}
          hint="Équilibre précision / rappel" />
      </div>

      <Card title="Que signifient ces indicateurs ?">
        <div className="grid grid-2">
          <div>
            <h3>Exactitude (accuracy)</h3>
            <p className="metric-explain">
              {metrics.glossary?.accuracy} Exemple : {num(metrics.accuracy * 100)} % signifie qu'environ
              {' '}{Math.round(metrics.accuracy * 100)} apprenants sur 100 reçoivent le bon profil.
            </p>
            <h3 className="mt-2">Précision (precision)</h3>
            <p className="metric-explain">{metrics.glossary?.precision}</p>
          </div>
          <div>
            <h3>Rappel (recall)</h3>
            <p className="metric-explain">{metrics.glossary?.recall}</p>
            <h3 className="mt-2">F1-score</h3>
            <p className="metric-explain">{metrics.glossary?.f1_score}</p>
          </div>
        </div>
      </Card>

      <div className="grid grid-2">
        <Card title="Performance par profil" subtitle="Précision, rappel et F1-score de chaque classe">
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={perClass} margin={{ top: 8, right: 12, bottom: 4, left: -18 }}>
              <CartesianGrid stroke={GRID} vertical={false} />
              <XAxis dataKey="profile" tick={{ ...AXIS, fontSize: 10 }} axisLine={{ stroke: GRID }} tickLine={false} />
              <YAxis domain={[0, 100]} tick={AXIS} axisLine={false} tickLine={false} />
              <Tooltip contentStyle={TOOLTIP} formatter={(v) => `${v} %`} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Bar dataKey="precision" name="Précision" fill="#16a34a" radius={[3, 3, 0, 0]} />
              <Bar dataKey="recall" name="Rappel" fill="#2563eb" radius={[3, 3, 0, 0]} />
              <Bar dataKey="f1" name="F1-score" fill="#d1d5db" radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Card>

        <Card title="Importance des variables" subtitle="Poids réel de chaque variable dans l'arbre de décision">
          {importances.length === 0 ? <Empty title="Modèle non chargé" /> : (
            <>
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={importances} layout="vertical" margin={{ top: 8, right: 20, bottom: 4, left: 90 }}>
                  <CartesianGrid stroke={GRID} horizontal={false} />
                  <XAxis type="number" tick={AXIS} axisLine={false} tickLine={false} />
                  <YAxis type="category" dataKey="label" tick={{ ...AXIS, fontSize: 10 }} axisLine={false} tickLine={false} width={90} />
                  <Tooltip contentStyle={TOOLTIP} formatter={(v) => [`${v} %`, 'Importance']} />
                  <Bar dataKey="pct" fill="#16a34a" radius={[0, 3, 3, 0]} name="Importance" />
                </BarChart>
              </ResponsiveContainer>
              <p className="small muted mt-1" style={{ marginBottom: 0 }}>
                Lu directement depuis <span className="mono">feature_importances_</span> du modèle chargé en mémoire.
              </p>
            </>
          )}
        </Card>
      </div>

      <div className="grid grid-2">
        <Card title="Détail par profil">
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Profil</th>
                  <th className="text-right">Précision</th>
                  <th className="text-right">Rappel</th>
                  <th className="text-right">F1-score</th>
                  <th className="text-right">Effectif test</th>
                </tr>
              </thead>
              <tbody>
                {perClass.map((c) => (
                  <tr key={c.profile}>
                    <td>
                      <span className="badge" style={{ borderColor: PROFILE_COLOR[c.profile], color: PROFILE_COLOR[c.profile] }}>
                        {c.profile}
                      </span>
                    </td>
                    <td className="text-right num">{c.precision} %</td>
                    <td className="text-right num">{c.recall} %</td>
                    <td className="text-right num">{c.f1} %</td>
                    <td className="text-right num">{c.support}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>

        <Card title="Prédictions correctes par profil" subtitle="Diagonale de la matrice de confusion">
          {!confusion ? <Empty title="Matrice indisponible" /> : (
            <>
              <ResponsiveContainer width="100%" height={230}>
                <BarChart data={confusion.rows} margin={{ top: 8, right: 12, bottom: 4, left: -18 }}>
                  <CartesianGrid stroke={GRID} vertical={false} />
                  <XAxis dataKey="profile" tick={{ ...AXIS, fontSize: 10 }} axisLine={{ stroke: GRID }} tickLine={false} />
                  <YAxis tick={AXIS} axisLine={false} tickLine={false} />
                  <Tooltip contentStyle={TOOLTIP} />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Bar dataKey="correct" stackId="a" name="Bien classés" radius={[0, 0, 0, 0]}>
                    {confusion.rows.map((r) => <Cell key={r.profile} fill={PROFILE_COLOR[r.profile] || '#16a34a'} />)}
                  </Bar>
                  <Bar dataKey="incorrect" stackId="a" name="Mal classés" fill="#e5e7eb" radius={[3, 3, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
              <p className="small muted mt-1" style={{ marginBottom: 0 }}>{confusion.note}</p>
            </>
          )}
        </Card>
      </div>

      <Card title="Modèles chargés" subtitle="État réel des artefacts scikit-learn utilisés par l'API">
        <div className="grid grid-2">
          <div>
            <div className="kv"><span>Classificateur</span><span>{metrics.decision_tree?.type || '—'}</span></div>
            <div className="kv"><span>Profondeur maximale</span><span>{metrics.decision_tree?.max_depth ?? '—'}</span></div>
            <div className="kv"><span>Profondeur effective</span><span>{metrics.decision_tree?.effective_depth ?? '—'}</span></div>
            <div className="kv"><span>Nombre de feuilles</span><span>{metrics.decision_tree?.n_leaves ?? '—'}</span></div>
            <div className="kv"><span>Classes prédites</span><span>{metrics.decision_tree?.classes?.join(', ') || '—'}</span></div>
          </div>
          <div>
            <div className="kv">
              <span>profile_classifier.joblib</span>
              <span>{metrics.artifacts?.profile_classifier ? <span className="badge badge-green">Chargé</span> : <span className="badge badge-red">Absent</span>}</span>
            </div>
            <div className="kv">
              <span>cluster_model.joblib (K-Means)</span>
              <span>{metrics.artifacts?.cluster_model ? <span className="badge badge-green">Chargé</span> : <span className="badge badge-red">Absent</span>}</span>
            </div>
            <div className="kv">
              <span>scaler.joblib (StandardScaler)</span>
              <span>{metrics.artifacts?.scaler ? <span className="badge badge-green">Chargé</span> : <span className="badge badge-red">Absent</span>}</span>
            </div>
            <div className="kv">
              <span>Clusters K-Means nommés</span>
              <span>{metrics.cluster_names ? Object.entries(metrics.cluster_names).map(([k, v]) => `${k}=${v}`).join(', ') : '—'}</span>
            </div>
            <div className="kv">
              <span>figures/confusion_matrix.png</span>
              <span>{metrics.confusion_matrix_figure_available ? 'Disponible dans le dépôt' : 'Non générée'}</span>
            </div>
          </div>
        </div>
      </Card>
    </div>
  )
}
