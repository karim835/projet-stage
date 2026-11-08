import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { learnerApi, readError } from '../services/api'
import { Alert, Card, Empty, Loading, ProfileBadge, num } from '../components/ui'

const PROFILES = ['Avancé', 'Moyen', 'Débutant', 'En difficulté', 'Peu actif']
const PAGE_SIZE = 20

const COLUMNS = [
  { key: 'student_id', label: 'Identifiant', sortable: true },
  { key: 'name', label: 'Nom', sortable: false },
  { key: 'profile', label: 'Profil', sortable: false },
  { key: 'average_score', label: 'Score', sortable: true, right: true },
  { key: 'completion_rate', label: 'Complétion', sortable: true, right: true },
  { key: 'time_spent_hours', label: 'Temps', sortable: true, right: true },
  { key: 'failed_quizzes', label: 'Échecs', sortable: true, right: true },
  { key: 'login_frequency', label: 'Connexions', sortable: false, right: true },
]

export default function LearnerList() {
  const [params, setParams] = useSearchParams()
  const navigate = useNavigate()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const [search, setSearch] = useState(params.get('search') || '')
  const [profile, setProfile] = useState(params.get('profile') || '')
  const [minScore, setMinScore] = useState(params.get('min_score') || '')
  const [maxScore, setMaxScore] = useState(params.get('max_score') || '')
  const [minCompletion, setMinCompletion] = useState(params.get('min_completion') || '')
  const [maxCompletion, setMaxCompletion] = useState(params.get('max_completion') || '')
  const [maxLogin, setMaxLogin] = useState(params.get('max_login') || '')
  const [sortBy, setSortBy] = useState('average_score')
  const [sortDir, setSortDir] = useState('desc')
  const [page, setPage] = useState(1)

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const query = {
        page,
        page_size: PAGE_SIZE,
        sort_by: sortBy,
        sort_dir: sortDir,
        ...(search.trim() ? { search: search.trim() } : {}),
        ...(profile ? { profile } : {}),
        ...(minScore !== '' ? { min_score: minScore } : {}),
        ...(maxScore !== '' ? { max_score: maxScore } : {}),
        ...(minCompletion !== '' ? { min_completion: minCompletion } : {}),
        ...(maxCompletion !== '' ? { max_completion: maxCompletion } : {}),
        ...(maxLogin !== '' ? { max_login_frequency: maxLogin } : {}),
      }
      const { data: result } = await learnerApi.list(query)
      setData(result)
    } catch (err) {
      setError(readError(err))
      setData(null)
    } finally {
      setLoading(false)
    }
  }, [page, sortBy, sortDir, search, profile, minScore, maxScore, minCompletion, maxCompletion, maxLogin])

  // Debounce : évite un appel réseau à chaque frappe.
  useEffect(() => {
    const timer = setTimeout(load, 250)
    return () => clearTimeout(timer)
  }, [load])

  useEffect(() => { setPage(1) }, [search, profile, minScore, maxScore, minCompletion, maxCompletion, maxLogin])

  function reset() {
    setSearch(''); setProfile(''); setMinScore(''); setMaxScore('')
    setMinCompletion(''); setMaxCompletion(''); setMaxLogin(''); setPage(1)
    setParams({}, { replace: true })
  }

  function sort(key) {
    if (sortBy === key) setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    else { setSortBy(key); setSortDir('desc') }
    setPage(1)
  }

  const total = data?.total ?? 0
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE))
  const hasFilters = search || profile || minScore || maxScore || minCompletion || maxCompletion || maxLogin

  return (
    <div className="stack">
      <Alert type="error" onClose={() => setError('')}>{error}</Alert>

      <Card title="Filtres" actions={hasFilters && <button type="button" className="btn btn-sm" onClick={reset}>Réinitialiser</button>}>
        <div className="filters">
          <div className="field">
            <label htmlFor="q">Recherche</label>
            <input id="q" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Nom, e-mail ou STU0001" />
          </div>
          <div className="field">
            <label htmlFor="p">Profil</label>
            <select id="p" value={profile} onChange={(e) => setProfile(e.target.value)}>
              <option value="">Tous les profils</option>
              {PROFILES.map((p) => <option key={p} value={p}>{p}</option>)}
            </select>
          </div>
          <div className="field">
            <label htmlFor="ms">Score minimum</label>
            <input id="ms" type="number" min="0" max="100" value={minScore} onChange={(e) => setMinScore(e.target.value)} />
          </div>
          <div className="field">
            <label htmlFor="xs">Score maximum</label>
            <input id="xs" type="number" min="0" max="100" value={maxScore} onChange={(e) => setMaxScore(e.target.value)} />
          </div>
          <div className="field">
            <label htmlFor="mc">Complétion min. %</label>
            <input id="mc" type="number" min="0" max="100" value={minCompletion} onChange={(e) => setMinCompletion(e.target.value)} />
          </div>
          <div className="field">
            <label htmlFor="xc">Complétion max. %</label>
            <input id="xc" type="number" min="0" max="100" value={maxCompletion} onChange={(e) => setMaxCompletion(e.target.value)} />
          </div>
          <div className="field">
            <label htmlFor="ml">Connexions/sem. max.</label>
            <input id="ml" type="number" min="0" max="100" value={maxLogin} onChange={(e) => setMaxLogin(e.target.value)} />
          </div>
        </div>
      </Card>

      <Card
        title={`Apprenants (${total})`}
        subtitle="Cliquez sur une ligne pour ouvrir la fiche détaillée"
        bodyClass=""
      >
        {loading ? <Loading /> : !data || data.items.length === 0 ? (
          <Empty title="Aucun apprenant ne correspond">Modifiez ou réinitialisez les filtres.</Empty>
        ) : (
          <>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    {COLUMNS.map((c) => (
                      <th
                        key={c.key}
                        className={`${c.sortable ? 'sortable' : ''} ${c.right ? 'text-right' : ''}`}
                        onClick={c.sortable ? () => sort(c.key) : undefined}
                      >
                        {c.label}
                        {c.sortable && sortBy === c.key && (sortDir === 'asc' ? ' ▲' : ' ▼')}
                      </th>
                    ))}
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {data.items.map((l) => (
                    <tr key={l.id} className="clickable" onClick={() => navigate(`/formateur/apprenants/${l.id}`)}>
                      <td className="mono">{l.student_id}</td>
                      <td>
                        {l.name}
                        {l.email && <div className="small muted">{l.email}</div>}
                      </td>
                      <td><ProfileBadge profile={l.profile} /></td>
                      <td className="text-right num">{num(l.average_score)}</td>
                      <td className="text-right num">{num(l.completion_rate)} %</td>
                      <td className="text-right num">{num(l.time_spent_hours)} h</td>
                      <td className="text-right num">{l.failed_quizzes}</td>
                      <td className="text-right num">{l.login_frequency}</td>
                      <td className="text-right">
                        <span className="btn btn-sm">Ouvrir</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="pagination">
              <span className="muted">
                Page {data.page} sur {pages} — {total} apprenant{total > 1 ? 's' : ''}
              </span>
              <div className="row">
                <button type="button" className="btn btn-sm" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>Précédent</button>
                <button type="button" className="btn btn-sm" disabled={page >= pages} onClick={() => setPage((p) => p + 1)}>Suivant</button>
              </div>
            </div>
          </>
        )}
      </Card>
    </div>
  )
}
