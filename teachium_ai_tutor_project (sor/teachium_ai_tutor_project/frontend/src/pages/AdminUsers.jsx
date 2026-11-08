import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { adminApi, readError } from '../services/api'
import { useAuth } from '../context/AuthContext'
import { Alert, Card, ConfirmDialog, Empty, Loading, formatDate } from '../components/ui'

const ROLES = [
  { value: 'learner', label: 'Apprenant' },
  { value: 'trainer', label: 'Formateur' },
  { value: 'administrator', label: 'Administrateur' },
]
const ROLE_LABEL = Object.fromEntries(ROLES.map((r) => [r.value, r.label]))
const PAGE_SIZE = 20

export default function AdminUsers() {
  const { user: me } = useAuth()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [busyId, setBusyId] = useState(null)
  const [toDelete, setToDelete] = useState(null)
  const [deleting, setDeleting] = useState(false)

  const [search, setSearch] = useState('')
  const [role, setRole] = useState('')
  const [active, setActive] = useState('')
  const [page, setPage] = useState(1)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const { data: result } = await adminApi.users({
        page,
        page_size: PAGE_SIZE,
        ...(search.trim() ? { search: search.trim() } : {}),
        ...(role ? { role } : {}),
        ...(active !== '' ? { is_active: active === 'true' } : {}),
      })
      setData(result)
      setError('')
    } catch (err) {
      setError(readError(err))
    } finally {
      setLoading(false)
    }
  }, [page, search, role, active])

  useEffect(() => {
    const timer = setTimeout(load, 250)
    return () => clearTimeout(timer)
  }, [load])

  useEffect(() => { setPage(1) }, [search, role, active])

  async function patch(user, payload, message) {
    setBusyId(user.id)
    setError('')
    setSuccess('')
    try {
      const { data: updated } = await adminApi.updateUser(user.id, payload)
      setData((d) => ({ ...d, items: d.items.map((u) => (u.id === updated.id ? updated : u)) }))
      setSuccess(message)
    } catch (err) {
      setError(readError(err))
    } finally {
      setBusyId(null)
    }
  }

  async function confirmDelete() {
    if (!toDelete) return
    setDeleting(true)
    setError('')
    try {
      const { data: result } = await adminApi.deleteUser(toDelete.id, toDelete.email)
      setSuccess(result.message)
      setToDelete(null)
      await load()
    } catch (err) {
      setError(readError(err))
    } finally {
      setDeleting(false)
    }
  }

  const total = data?.total ?? 0
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  return (
    <div className="stack">
      <Alert type="error" onClose={() => setError('')}>{error}</Alert>
      <Alert type="success" onClose={() => setSuccess('')}>{success}</Alert>

      <Card title="Filtres">
        <div className="filters">
          <div className="field">
            <label htmlFor="s">Recherche</label>
            <input id="s" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Nom ou e-mail" />
          </div>
          <div className="field">
            <label htmlFor="r">Rôle</label>
            <select id="r" value={role} onChange={(e) => setRole(e.target.value)}>
              <option value="">Tous les rôles</option>
              {ROLES.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
            </select>
          </div>
          <div className="field">
            <label htmlFor="a">État</label>
            <select id="a" value={active} onChange={(e) => setActive(e.target.value)}>
              <option value="">Tous</option>
              <option value="true">Actifs</option>
              <option value="false">Désactivés</option>
            </select>
          </div>
        </div>
      </Card>

      <Card title={`Comptes (${total})`} bodyClass="">
        {loading ? <Loading /> : !data || data.items.length === 0 ? (
          <Empty title="Aucun compte trouvé">Modifiez les filtres de recherche.</Empty>
        ) : (
          <>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Nom</th>
                    <th>E-mail</th>
                    <th>Rôle</th>
                    <th>Fiche apprenant</th>
                    <th>Créé le</th>
                    <th>État</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {data.items.map((u) => {
                    const isMe = u.id === me?.id
                    return (
                      <tr key={u.id}>
                        <td>{u.name}{isMe && <span className="badge badge-green" style={{ marginLeft: 6 }}>vous</span>}</td>
                        <td className="small">{u.email}</td>
                        <td>
                          <select
                            value={u.role}
                            disabled={busyId === u.id || isMe}
                            onChange={(e) => patch(u, { role: e.target.value }, `Rôle de ${u.name} modifié.`)}
                            style={{ minWidth: 130 }}
                          >
                            {ROLES.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
                          </select>
                        </td>
                        <td>
                          {u.learner_id
                            ? <Link to={`/formateur/apprenants/${u.learner_id}`} className="mono">{u.student_id}</Link>
                            : <span className="muted">—</span>}
                        </td>
                        <td className="nowrap small muted">{formatDate(u.created_at, false)}</td>
                        <td>
                          {u.is_active
                            ? <span className="badge badge-green">Actif</span>
                            : <span className="badge badge-red">Désactivé</span>}
                        </td>
                        <td>
                          <div className="row" style={{ gap: 6, flexWrap: 'nowrap' }}>
                            <button
                              type="button" className="btn btn-sm" disabled={busyId === u.id || isMe}
                              onClick={() => patch(u, { is_active: !u.is_active },
                                `Compte ${u.email} ${u.is_active ? 'désactivé' : 'réactivé'}.`)}
                            >
                              {busyId === u.id && <span className="spinner" />}
                              {u.is_active ? 'Désactiver' : 'Réactiver'}
                            </button>
                            <button
                              type="button" className="btn btn-sm btn-danger" disabled={isMe}
                              onClick={() => setToDelete(u)}
                            >
                              Supprimer
                            </button>
                          </div>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>

            <div className="pagination">
              <span className="muted">Page {data.page} sur {pages}</span>
              <div className="row">
                <button type="button" className="btn btn-sm" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>Précédent</button>
                <button type="button" className="btn btn-sm" disabled={page >= pages} onClick={() => setPage((p) => p + 1)}>Suivant</button>
              </div>
            </div>
          </>
        )}
      </Card>

      <div className="alert alert-info small">
        La désactivation est réversible et bloque immédiatement la connexion. La suppression est
        définitive : elle efface aussi la fiche apprenant, les profils, recommandations et messages
        associés. Votre propre compte et le dernier administrateur actif ne peuvent pas être supprimés.
      </div>

      <ConfirmDialog
        open={Boolean(toDelete)}
        title="Supprimer définitivement ce compte ?"
        message={`Le compte ${toDelete?.email} et toutes ses données liées (fiche apprenant, profils, recommandations, conversation) seront effacés de la base. Cette action est irréversible.`}
        confirmLabel="Supprimer définitivement"
        requireText={toDelete?.email}
        busy={deleting}
        onConfirm={confirmDelete}
        onCancel={() => setToDelete(null)}
      />
    </div>
  )
}
