import { useCallback, useEffect, useState } from 'react'
import { learnerApi, quizApi, readError } from '../services/api'
import { Alert, Card, ConfirmDialog, Empty, Loading, formatDate, num } from '../components/ui'

const EMPTY_QUESTION = { question_text: '', options: ['', ''], correct_index: 0, explanation: '' }

const DIFFICULTIES = ['Facile', 'Moyen', 'Difficile']

/** Espace formateur : créer, publier, attribuer les quiz et consulter les résultats. */
export default function QuizManager() {
  const [quizzes, setQuizzes] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  const [creating, setCreating] = useState(false)
  const [form, setForm] = useState({
    title: '', description: '', category: '', difficulty: 'Moyen', passing_score: 60,
    is_published: true, questions: [{ ...EMPTY_QUESTION, options: ['', ''] }],
  })
  const [saving, setSaving] = useState(false)

  const [selected, setSelected] = useState(null)
  const [results, setResults] = useState(null)
  const [toDelete, setToDelete] = useState(null)
  const [busy, setBusy] = useState(false)

  const [learners, setLearners] = useState([])
  const [assignSearch, setAssignSearch] = useState('')
  const [chosen, setChosen] = useState([])

  const load = useCallback(async () => {
    try {
      setError('')
      const { data } = await quizApi.list()
      setQuizzes(data)
    } catch (err) {
      setError(readError(err))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  /* ---------------- Création ---------------- */

  function updateQuestion(index, patch) {
    setForm((f) => ({
      ...f,
      questions: f.questions.map((q, i) => (i === index ? { ...q, ...patch } : q)),
    }))
  }

  function updateOption(qIndex, oIndex, value) {
    setForm((f) => ({
      ...f,
      questions: f.questions.map((q, i) =>
        i === qIndex ? { ...q, options: q.options.map((o, j) => (j === oIndex ? value : o)) } : q,
      ),
    }))
  }

  async function createQuiz(event) {
    event.preventDefault()
    setError(''); setSuccess('')

    if (form.title.trim().length < 3) return setError('Le titre doit contenir au moins 3 caractères.')
    for (const [i, q] of form.questions.entries()) {
      if (q.question_text.trim().length < 5) return setError(`Question ${i + 1} : l'énoncé est trop court.`)
      const options = q.options.map((o) => o.trim()).filter(Boolean)
      if (options.length < 2) return setError(`Question ${i + 1} : il faut au moins deux propositions.`)
      if (new Set(options).size !== options.length) return setError(`Question ${i + 1} : deux propositions sont identiques.`)
      if (q.correct_index >= options.length) return setError(`Question ${i + 1} : désignez la bonne réponse.`)
    }

    setSaving(true)
    try {
      const payload = {
        title: form.title.trim(),
        description: form.description.trim() || null,
        category: form.category.trim() || null,
        difficulty: form.difficulty,
        passing_score: Number(form.passing_score),
        is_published: form.is_published,
        questions: form.questions.map((q) => ({
          question_text: q.question_text.trim(),
          options: q.options.map((o) => o.trim()).filter(Boolean),
          correct_index: q.correct_index,
          points: 1,
          explanation: q.explanation.trim() || null,
        })),
      }
      const { data } = await quizApi.create(payload)
      setSuccess(`Quiz « ${data.title} » créé avec ${data.question_count} question(s).`)
      setCreating(false)
      setForm({
        title: '', description: '', category: '', difficulty: 'Moyen', passing_score: 60,
        is_published: true, questions: [{ ...EMPTY_QUESTION, options: ['', ''] }],
      })
      await load()
    } catch (err) {
      setError(readError(err))
    } finally {
      setSaving(false)
    }
  }

  /* ---------------- Publication / suppression ---------------- */

  async function togglePublish(quiz) {
    setBusy(true); setError(''); setSuccess('')
    try {
      await quizApi.update(quiz.id, { is_published: !quiz.is_published })
      setSuccess(`Quiz « ${quiz.title} » ${quiz.is_published ? 'dépublié' : 'publié'}.`)
      await load()
    } catch (err) {
      setError(readError(err))
    } finally {
      setBusy(false)
    }
  }

  async function confirmDelete() {
    setBusy(true)
    try {
      const { data } = await quizApi.remove(toDelete.id)
      setSuccess(data.message)
      setToDelete(null)
      if (selected?.id === toDelete.id) { setSelected(null); setResults(null) }
      await load()
    } catch (err) {
      setError(readError(err))
    } finally {
      setBusy(false)
    }
  }

  /* ---------------- Attribution et résultats ---------------- */

  // Ne réinitialise pas les messages : cette fonction est aussi appelée juste
  // après une attribution, dont le message de confirmation doit rester visible.
  async function openQuiz(quiz) {
    setSelected(quiz); setResults(null); setChosen([]); setAssignSearch('')
    try {
      const [res, list] = await Promise.all([
        quizApi.results(quiz.id),
        learnerApi.list({ page_size: 50, sort_by: 'average_score', sort_dir: 'asc' }),
      ])
      setResults(res.data)
      setLearners(list.data.items)
    } catch (err) {
      setError(readError(err))
    }
  }

  async function searchLearners(value) {
    setAssignSearch(value)
    try {
      const { data } = await learnerApi.list({
        page_size: 50, ...(value.trim() ? { search: value.trim() } : {}),
      })
      setLearners(data.items)
    } catch (err) {
      setError(readError(err))
    }
  }

  async function assign() {
    if (!chosen.length) return setError('Sélectionnez au moins un apprenant.')
    setBusy(true); setError(''); setSuccess('')
    try {
      const { data } = await quizApi.assign(selected.id, chosen)
      setSuccess(
        `${data.assigned} attribution(s) créée(s)` +
        (data.already_assigned ? `, ${data.already_assigned} déjà attribuée(s)` : '') + '.',
      )
      setChosen([])
      await openQuiz(selected)
      await load()
    } catch (err) {
      setError(readError(err))
    } finally {
      setBusy(false)
    }
  }

  async function unassign(learnerId) {
    setBusy(true); setError('')
    try {
      await quizApi.unassign(selected.id, learnerId)
      await openQuiz(selected)
      await load()
    } catch (err) {
      setError(readError(err))
    } finally {
      setBusy(false)
    }
  }

  if (loading) return <Loading />

  return (
    <div className="stack">
      <Alert type="error" onClose={() => setError('')}>{error}</Alert>
      <Alert type="success" onClose={() => setSuccess('')}>{success}</Alert>

      <Card
        title={`Quiz (${quizzes.length})`}
        actions={
          <button type="button" className="btn btn-sm btn-primary" onClick={() => setCreating((v) => !v)}>
            {creating ? 'Annuler la création' : 'Nouveau quiz'}
          </button>
        }
        bodyClass=""
      >
        {quizzes.length === 0 ? (
          <Empty title="Aucun quiz">Créez le premier quiz avec le bouton ci-dessus.</Empty>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Titre</th>
                  <th>Filière</th>
                  <th>Difficulté</th>
                  <th className="text-right">Questions</th>
                  <th className="text-right">Attribué à</th>
                  <th className="text-right">Copies</th>
                  <th className="text-right">Moyenne</th>
                  <th>État</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {quizzes.map((q) => (
                  <tr key={q.id} className={selected?.id === q.id ? '' : 'clickable'}>
                    <td onClick={() => { setError(''); setSuccess(''); openQuiz(q) }}>{q.title}</td>
                    <td>{q.category || '—'}</td>
                    <td>{q.difficulty}</td>
                    <td className="text-right num">{q.question_count}</td>
                    <td className="text-right num">{q.assigned_count}</td>
                    <td className="text-right num">{q.attempts_count}</td>
                    <td className="text-right num">{q.average_score != null ? num(q.average_score) : '—'}</td>
                    <td>
                      {q.is_published
                        ? <span className="badge badge-green">Publié</span>
                        : <span className="badge">Brouillon</span>}
                    </td>
                    <td>
                      <div className="row" style={{ gap: 6, flexWrap: 'nowrap' }}>
                        <button type="button" className="btn btn-sm"
                          onClick={() => { setError(''); setSuccess(''); openQuiz(q) }}>Gérer</button>
                        <button type="button" className="btn btn-sm" disabled={busy} onClick={() => togglePublish(q)}>
                          {q.is_published ? 'Dépublier' : 'Publier'}
                        </button>
                        <button type="button" className="btn btn-sm btn-danger" onClick={() => setToDelete(q)}>
                          Supprimer
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {creating && (
        <Card title="Nouveau quiz" subtitle="Les apprenants ne verront jamais la bonne réponse avant d'avoir rendu leur copie">
          <form onSubmit={createQuiz}>
            <div className="filters">
              <div className="field">
                <label htmlFor="title">Titre</label>
                <input id="title" value={form.title} onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))} maxLength={200} />
              </div>
              <div className="field">
                <label htmlFor="cat">Filière</label>
                <input id="cat" value={form.category} onChange={(e) => setForm((f) => ({ ...f, category: e.target.value }))}
                  placeholder="Python, Data, Web..." maxLength={60} />
                <span className="field-hint">Le quiz devient visible pour les apprenants de cette filière.</span>
              </div>
              <div className="field">
                <label htmlFor="diff">Difficulté</label>
                <select id="diff" value={form.difficulty} onChange={(e) => setForm((f) => ({ ...f, difficulty: e.target.value }))}>
                  {DIFFICULTIES.map((d) => <option key={d} value={d}>{d}</option>)}
                </select>
              </div>
              <div className="field">
                <label htmlFor="pass">Note de réussite /100</label>
                <input id="pass" type="number" min="0" max="100" step="any" value={form.passing_score}
                  onChange={(e) => setForm((f) => ({ ...f, passing_score: e.target.value }))} />
              </div>
            </div>

            <div className="field">
              <label htmlFor="desc">Description <span className="muted">(facultatif)</span></label>
              <textarea id="desc" rows={2} value={form.description}
                onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))} maxLength={2000} />
            </div>

            <label className="checkbox mb-2">
              <input type="checkbox" checked={form.is_published}
                onChange={(e) => setForm((f) => ({ ...f, is_published: e.target.checked }))} />
              Publier immédiatement (obligatoire pour pouvoir l'attribuer)
            </label>

            <h3 className="mt-2">Questions ({form.questions.length})</h3>

            <div className="stack mt-1" style={{ gap: 12 }}>
              {form.questions.map((q, qi) => (
                <div className="card question-editor" key={qi} style={{ boxShadow: 'none' }}>
                  <div className="card-body">
                    <div className="row-between mb-1">
                      <strong>Question {qi + 1}</strong>
                      {form.questions.length > 1 && (
                        <button type="button" className="btn-link"
                          onClick={() => setForm((f) => ({ ...f, questions: f.questions.filter((_, i) => i !== qi) }))}>
                          Retirer
                        </button>
                      )}
                    </div>

                    <div className="field">
                      <label>Énoncé</label>
                      <textarea rows={2} value={q.question_text} maxLength={1000}
                        onChange={(e) => updateQuestion(qi, { question_text: e.target.value })} />
                    </div>

                    <label style={{ fontSize: 12.5, fontWeight: 500, color: 'var(--text-muted)' }}>
                      Propositions — cochez la bonne réponse
                    </label>
                    <div className="stack mt-1" style={{ gap: 6 }}>
                      {q.options.map((option, oi) => (
                        <div className="row" key={oi} style={{ gap: 8, flexWrap: 'nowrap' }}>
                          <input type="radio" name={`correct-${qi}`} checked={q.correct_index === oi}
                            onChange={() => updateQuestion(qi, { correct_index: oi })}
                            style={{ width: 'auto' }} aria-label={`Bonne réponse ${oi + 1}`} />
                          <input value={option} maxLength={300} placeholder={`Proposition ${oi + 1}`}
                            onChange={(e) => updateOption(qi, oi, e.target.value)} />
                          {q.options.length > 2 && (
                            <button type="button" className="btn btn-sm"
                              onClick={() => updateQuestion(qi, {
                                options: q.options.filter((_, i) => i !== oi),
                                correct_index: q.correct_index >= q.options.length - 1 ? 0 : q.correct_index,
                              })}>
                              ×
                            </button>
                          )}
                        </div>
                      ))}
                    </div>
                    {q.options.length < 6 && (
                      <button type="button" className="btn btn-sm mt-1"
                        onClick={() => updateQuestion(qi, { options: [...q.options, ''] })}>
                        Ajouter une proposition
                      </button>
                    )}

                    <div className="field mt-2">
                      <label>Explication affichée après correction <span className="muted">(facultatif)</span></label>
                      <input value={q.explanation} maxLength={1000}
                        onChange={(e) => updateQuestion(qi, { explanation: e.target.value })} />
                    </div>
                  </div>
                </div>
              ))}
            </div>

            <div className="row mt-2">
              <button type="button" className="btn"
                onClick={() => setForm((f) => ({ ...f, questions: [...f.questions, { ...EMPTY_QUESTION, options: ['', ''] }] }))}>
                Ajouter une question
              </button>
              <button type="submit" className="btn btn-primary" disabled={saving}>
                {saving && <span className="spinner" />} Créer le quiz
              </button>
            </div>
          </form>
        </Card>
      )}

      {selected && results && (
        <>
          <Card
            title={`Résultats — ${results.title}`}
            actions={<button type="button" className="btn btn-sm" onClick={() => { setSelected(null); setResults(null) }}>Fermer</button>}
          >
            <div className="grid grid-4">
              <div className="kv"><span>Attribué à</span><span>{results.assigned_count} apprenant(s)</span></div>
              <div className="kv"><span>Participants</span><span>{results.participants}</span></div>
              <div className="kv"><span>Moyenne</span><span>{results.average_score != null ? `${num(results.average_score)}/100` : '—'}</span></div>
              <div className="kv"><span>Taux de réussite</span><span>{results.pass_rate != null ? `${num(results.pass_rate)} %` : '—'}</span></div>
            </div>

            {results.rows.length === 0 ? (
              <Empty title="Aucun apprenant">Attribuez ce quiz ci-dessous.</Empty>
            ) : (
              <div className="table-wrap mt-2">
                <table>
                  <thead>
                    <tr>
                      <th>Apprenant</th>
                      <th className="text-right">Tentatives</th>
                      <th className="text-right">Meilleure note</th>
                      <th>Résultat</th>
                      <th>Dernier passage</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {results.rows.map((row) => (
                      <tr key={row.learner_id}>
                        <td>{row.name} <span className="mono small muted">{row.student_id}</span></td>
                        <td className="text-right num">{row.attempts}</td>
                        <td className="text-right num">{row.best_score != null ? num(row.best_score) : '—'}</td>
                        <td>
                          {row.best_score == null
                            ? <span className="badge">Non passé</span>
                            : row.passed
                              ? <span className="badge badge-green">Réussi</span>
                              : <span className="badge badge-red">Échoué</span>}
                        </td>
                        <td className="nowrap small muted">
                          {row.last_attempt_at ? formatDate(row.last_attempt_at, false) : '—'}
                        </td>
                        <td className="text-right">
                          {row.assigned_at && (
                            <button type="button" className="btn btn-sm" disabled={busy}
                              onClick={() => unassign(row.learner_id)}>
                              Retirer
                            </button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {results.question_stats.length > 0 && (
              <>
                <h3 className="mt-3">Taux de réussite par question</h3>
                <p className="small muted">Les questions les plus manquées apparaissent en premier : ce sont les notions à retravailler avec le groupe.</p>
                <div className="table-wrap">
                  <table>
                    <thead><tr><th>Question</th><th className="text-right">Réponses</th><th className="text-right">Réussite</th></tr></thead>
                    <tbody>
                      {results.question_stats.map((q) => (
                        <tr key={q.question_id}>
                          <td>{q.question_text}</td>
                          <td className="text-right num">{q.answers}</td>
                          <td className="text-right num">
                            <span className={`badge ${q.success_rate >= 70 ? 'badge-green' : q.success_rate >= 40 ? 'badge-amber' : 'badge-red'}`}>
                              {num(q.success_rate)} %
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}
          </Card>

          <Card title="Attribuer ce quiz" subtitle="Sélectionnez les apprenants concernés">
            <div className="field">
              <label htmlFor="search-learner">Rechercher un apprenant</label>
              <input id="search-learner" value={assignSearch} placeholder="Nom, e-mail ou STU0001"
                onChange={(e) => searchLearners(e.target.value)} />
            </div>

            <div className="table-wrap" style={{ maxHeight: 280, overflowY: 'auto' }}>
              <table>
                <thead>
                  <tr><th /><th>Apprenant</th><th>Profil</th><th className="text-right">Score</th></tr>
                </thead>
                <tbody>
                  {learners.map((l) => (
                    <tr key={l.id}>
                      <td>
                        <input type="checkbox" style={{ width: 'auto' }} checked={chosen.includes(l.id)}
                          onChange={(e) => setChosen((c) => e.target.checked ? [...c, l.id] : c.filter((x) => x !== l.id))} />
                      </td>
                      <td>{l.name} <span className="mono small muted">{l.student_id}</span></td>
                      <td>{l.profile || '—'}</td>
                      <td className="text-right num">{num(l.average_score)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="row mt-2">
              <button type="button" className="btn btn-primary" onClick={assign} disabled={busy || !chosen.length}>
                {busy && <span className="spinner" />} Attribuer à {chosen.length} apprenant(s)
              </button>
              {chosen.length > 0 && (
                <button type="button" className="btn" onClick={() => setChosen([])}>Tout désélectionner</button>
              )}
            </div>
          </Card>
        </>
      )}

      <ConfirmDialog
        open={Boolean(toDelete)}
        title="Supprimer ce quiz ?"
        message={`Le quiz « ${toDelete?.title} », ses questions, ses attributions et toutes les copies déjà corrigées seront définitivement supprimés.`}
        confirmLabel="Supprimer définitivement"
        requireText={toDelete?.title}
        busy={busy}
        onConfirm={confirmDelete}
        onCancel={() => setToDelete(null)}
      />
    </div>
  )
}
