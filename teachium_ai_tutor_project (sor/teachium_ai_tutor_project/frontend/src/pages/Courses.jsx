import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { courseApi, readError } from '../services/api'
import { useAuth } from '../context/AuthContext'
import { Alert, Card, ConfirmDialog, Empty, Loading, formatDate, num } from '../components/ui'

const LEVELS = ['Débutant', 'Intermédiaire', 'Avancé']
const LEVEL_TONE = { Débutant: 'badge-green', Intermédiaire: 'badge-blue', Avancé: 'badge-amber' }
const EMPTY = { title: '', category: '', level: 'Débutant', summary: '', keywords: '', content: '' }

function LessonContent({ content }) {
  const paragraphs = String(content || '').split(/\n\s*\n/).map((part) => part.trim()).filter(Boolean)
  return (
    <div className="lesson-content">
      {paragraphs.map((paragraph, index) => <p key={`${paragraph.slice(0, 28)}-${index}`}>{paragraph}</p>)}
    </div>
  )
}

function CourseTile({ course, canEdit, opening, onOpen, onDelete }) {
  return (
    <article className={`course-tile ${course.completed ? 'is-completed' : ''}`}>
      <div className="course-tile-accent" aria-hidden="true">{course.category?.slice(0, 1).toUpperCase()}</div>
      <div className="course-tile-body">
        <div className="course-tile-badges">
          <span className="badge">{course.category}</span>
          <span className={`badge ${LEVEL_TONE[course.level] || ''}`}>{course.level}</span>
          {course.completed && <span className="badge badge-green"><span aria-hidden="true">✓</span> Terminée</span>}
        </div>
        <h3>{course.title}</h3>
        <p>{course.summary || 'Ouvrez cette leçon pour consulter son contenu.'}</p>
      </div>
      <div className="course-tile-footer">
        <span className="small muted">Mis à jour le {formatDate(course.updated_at, false)}</span>
        <div className="row">
          <button type="button" className="btn btn-sm btn-primary" onClick={() => onOpen(course.id)} disabled={opening}>
            {opening ? <span className="spinner" /> : null}{course.completed ? 'Relire' : 'Lire la leçon'}
          </button>
          {canEdit && <button type="button" className="btn btn-sm btn-danger" onClick={() => onDelete(course)}>Supprimer</button>}
        </div>
      </div>
    </article>
  )
}

export default function Courses() {
  const { isLearner } = useAuth()
  const canEdit = !isLearner
  const [courses, setCourses] = useState([])
  const [categories, setCategories] = useState([])
  const [opened, setOpened] = useState(null)
  const [openingId, setOpeningId] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [category, setCategory] = useState('')
  const [search, setSearch] = useState('')
  const [hits, setHits] = useState(null)
  const [searching, setSearching] = useState(false)
  const [editing, setEditing] = useState(null)
  const [form, setForm] = useState(EMPTY)
  const [saving, setSaving] = useState(false)
  const [completing, setCompleting] = useState(false)
  const [completion, setCompletion] = useState(null)
  const [toDelete, setToDelete] = useState(null)

  const load = useCallback(async () => {
    try {
      setError('')
      const [list, cats] = await Promise.all([
        courseApi.list(category ? { category } : {}),
        courseApi.categories(),
      ])
      setCourses(Array.isArray(list.data) ? list.data : [])
      setCategories(Array.isArray(cats.data) ? cats.data : [])
    } catch (err) {
      setError(readError(err))
    } finally {
      setLoading(false)
    }
  }, [category])

  useEffect(() => { load() }, [load])
  const completedCount = useMemo(() => courses.filter((course) => course.completed).length, [courses])

  async function runSearch(event) {
    event.preventDefault()
    const q = search.trim()
    if (q.length < 2) { setHits(null); return }
    setSearching(true)
    setError('')
    try {
      const { data } = await courseApi.search(q, category || undefined)
      setHits(Array.isArray(data) ? data : [])
    } catch (err) {
      setError(readError(err))
    } finally {
      setSearching(false)
    }
  }

  async function openCourse(id) {
    setError('')
    setSuccess('')
    setCompletion(null)
    setOpeningId(id)
    try {
      const { data } = await courseApi.detail(id)
      setOpened(data)
      setCompletion(data.completed ? {
        course_id: data.id,
        completed_at: data.completed_at,
        newly_completed: false,
        recommended_quiz: data.recommended_quiz || null,
      } : null)
      window.scrollTo({ top: 0, behavior: 'smooth' })
    } catch (err) {
      setError(readError(err))
    } finally {
      setOpeningId(null)
    }
  }

  async function completeLesson() {
    if (!opened || opened.completed || completing) return
    setCompleting(true)
    setError('')
    setSuccess('')
    try {
      const { data } = await courseApi.complete(opened.id)
      const completedAt = data.completed_at || new Date().toISOString()
      setOpened((current) => ({ ...current, completed: true, completed_at: completedAt }))
      setCourses((current) => current.map((course) => (
        course.id === opened.id ? { ...course, completed: true, completed_at: completedAt } : course
      )))
      setCompletion(data)
      setSuccess(data.message || 'Leçon terminée. Votre prochain quiz est prêt.')
    } catch (err) {
      setError(readError(err))
    } finally {
      setCompleting(false)
    }
  }

  function startEdit(course) {
    if (course) {
      setEditing(course.id)
      setForm({ title: course.title, category: course.category, level: course.level, summary: course.summary || '', keywords: course.keywords || '', content: course.content })
    } else {
      setEditing('new')
      setForm(EMPTY)
    }
    setOpened(null)
    setCompletion(null)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  async function save(event) {
    event.preventDefault()
    setError(''); setSuccess('')
    if (form.title.trim().length < 3) return setError('Le titre doit contenir au moins 3 caractères.')
    if (form.category.trim().length < 2) return setError('Renseignez une filière.')
    if (form.content.trim().length < 20) return setError('Le contenu doit contenir au moins 20 caractères.')
    setSaving(true)
    try {
      const payload = { title: form.title.trim(), category: form.category.trim(), level: form.level, summary: form.summary.trim() || null, keywords: form.keywords.trim() || null, content: form.content.trim() }
      if (editing === 'new') {
        const { data } = await courseApi.create(payload)
        setSuccess(`Fiche « ${data.title} » ajoutée. L’AI Tutor peut désormais s’en servir.`)
      } else {
        const { data } = await courseApi.update(editing, payload)
        setSuccess(`Fiche « ${data.title} » mise à jour.`)
      }
      setEditing(null)
      setHits(null)
      await load()
    } catch (err) {
      setError(readError(err))
    } finally {
      setSaving(false)
    }
  }

  async function confirmDelete() {
    setSaving(true)
    try {
      const { data } = await courseApi.remove(toDelete.id)
      setSuccess(data.message)
      setToDelete(null)
      if (opened?.id === toDelete.id) setOpened(null)
      await load()
    } catch (err) {
      setError(readError(err))
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <Loading />
  const recommendation = completion?.recommended_quiz

  return (
    <div className="stack courses-page">
      <Alert type="error" onClose={() => setError('')}>{error}</Alert>
      <Alert type="success" onClose={() => setSuccess('')}>{success}</Alert>

      {!canEdit && (
        <section className="courses-hero">
          <div><span className="eyebrow">Apprendre · valider · progresser</span><h1>Votre bibliothèque d’apprentissage</h1><p>Lisez une leçon à votre rythme, confirmez quand elle est terminée, puis vérifiez vos acquis avec le quiz proposé.</p></div>
          <div className="course-progress-summary" aria-label={`${completedCount} leçons terminées sur ${courses.length}${category ? ` dans la filière ${category}` : ''}`}><strong>{completedCount}<span>/{courses.length}</span></strong><span>{category ? 'dans cette filière' : 'leçons terminées'}</span></div>
        </section>
      )}

      {opened && (
        <article className="lesson-reader">
          <header className="lesson-reader-head">
            <div className="lesson-reader-meta"><span className="badge">{opened.category}</span><span className={`badge ${LEVEL_TONE[opened.level] || ''}`}>{opened.level}</span>{opened.completed && <span className="badge badge-green"><span aria-hidden="true">✓</span> Leçon terminée</span>}</div>
            <div className="lesson-reader-actions">{canEdit && <button type="button" className="btn btn-sm" onClick={() => startEdit(opened)}>Modifier</button>}<button type="button" className="btn btn-sm" onClick={() => { setOpened(null); setCompletion(null) }}>Fermer</button></div>
          </header>
          <div className="lesson-reader-layout">
            <div className="lesson-main">
              <span className="eyebrow">Leçon</span><h1>{opened.title}</h1>
              {opened.summary && <p className="lesson-lead">{opened.summary}</p>}
              <LessonContent content={opened.content} />
              {opened.keywords && <div className="lesson-keywords"><span>Notions clés</span><div className="row">{opened.keywords.split(',').map((keyword) => <span className="badge" key={keyword}>{keyword.trim()}</span>)}</div></div>}
            </div>
            {!canEdit && (
              <aside className={`lesson-completion ${opened.completed ? 'is-completed' : ''}`}>
                <div className="completion-icon" aria-hidden="true">{opened.completed ? '✓' : '→'}</div>
                <span className="eyebrow">Étape suivante</span>
                <h2>{opened.completed ? 'Leçon validée' : 'Vous avez terminé ?'}</h2>
                <p>{opened.completed ? `Terminée${opened.completed_at ? ` le ${formatDate(opened.completed_at, false)}` : ''}. Vous pouvez maintenant mettre vos acquis en pratique.` : 'Confirmez uniquement après avoir lu la leçon. Un quiz adapté vous sera proposé immédiatement.'}</p>
                {!opened.completed ? <button type="button" className="btn btn-primary btn-block" onClick={completeLesson} disabled={completing}>{completing && <span className="spinner" />} J’ai terminé cette leçon</button> : !completion ? <Link className="btn btn-primary btn-block" to="/apprenant/quiz">Voir mes quiz</Link> : null}
                {!opened.completed && <span className="completion-note">Cette action enregistre votre progression.</span>}
              </aside>
            )}
          </div>

          {!canEdit && completion && (
            <section className="lesson-next-step" aria-live="polite">
              <div className="lesson-next-step-copy"><span className="eyebrow">Leçon terminée · quiz débloqué</span><h2>{recommendation ? 'Vérifiez maintenant vos acquis' : 'Votre progression est enregistrée'}</h2><p>{recommendation ? 'Ce quiz existant correspond le mieux à la leçon que vous venez de terminer.' : 'Aucun quiz correspondant n’est publié pour le moment. Retrouvez vos autres quiz disponibles.'}</p></div>
              {recommendation ? (
                <article className="recommended-quiz-card"><div><div className="row"><span className="badge badge-blue">Quiz recommandé</span><span className="badge">{recommendation.difficulty}</span></div><h3>{recommendation.title}</h3>{recommendation.description && <p>{recommendation.description}</p>}<span className="small muted">{recommendation.question_count} question{recommendation.question_count > 1 ? 's' : ''} · seuil {num(recommendation.passing_score, 0)}/100</span></div><Link className="btn btn-primary" to={`/apprenant/quiz/${recommendation.id}`}>Commencer le quiz</Link></article>
              ) : <Link className="btn btn-primary" to="/apprenant/quiz">Voir mes quiz</Link>}
            </section>
          )}
        </article>
      )}

      {canEdit && editing && (
        <Card title={editing === 'new' ? 'Nouvelle fiche de cours' : 'Modifier la fiche'}>
          <form onSubmit={save}>
            <div className="filters"><div className="field"><label htmlFor="t">Titre</label><input id="t" value={form.title} maxLength={200} onChange={(e) => setForm((current) => ({ ...current, title: e.target.value }))} /></div><div className="field"><label htmlFor="c">Filière</label><input id="c" value={form.category} maxLength={60} placeholder="Python, Data, Web…" onChange={(e) => setForm((current) => ({ ...current, category: e.target.value }))} /></div><div className="field"><label htmlFor="l">Niveau</label><select id="l" value={form.level} onChange={(e) => setForm((current) => ({ ...current, level: e.target.value }))}>{LEVELS.map((level) => <option key={level} value={level}>{level}</option>)}</select></div></div>
            <div className="field"><label htmlFor="s">Résumé <span className="muted">(une phrase)</span></label><input id="s" value={form.summary} maxLength={1000} onChange={(e) => setForm((current) => ({ ...current, summary: e.target.value }))} /></div>
            <div className="field"><label htmlFor="k">Mots-clés <span className="muted">(séparés par des virgules)</span></label><input id="k" value={form.keywords} maxLength={500} placeholder="boucle, for, while, range" onChange={(e) => setForm((current) => ({ ...current, keywords: e.target.value }))} /><span className="field-hint">Les mots-clés améliorent la recherche de l’AI Tutor.</span></div>
            <div className="field"><label htmlFor="ct">Contenu</label><textarea id="ct" rows={12} value={form.content} maxLength={20000} onChange={(e) => setForm((current) => ({ ...current, content: e.target.value }))} /><span className="field-hint">Séparez les paragraphes par une ligne vide pour faciliter la lecture et les citations du tuteur.</span></div>
            <div className="row"><button type="submit" className="btn btn-primary" disabled={saving}>{saving && <span className="spinner" />} Enregistrer</button><button type="button" className="btn" onClick={() => setEditing(null)}>Annuler</button></div>
          </form>
        </Card>
      )}

      <Card title="Trouver une leçon" subtitle="Recherchez un titre, une notion ou une question">
        <form onSubmit={runSearch} className="course-search-form">
          <div className="field"><label htmlFor="q">Recherche</label><input id="q" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Ex. à quoi sert la normalisation avant K-Means ?" maxLength={300} /></div>
          <div className="field"><label htmlFor="cat">Filière</label><select id="cat" value={category} onChange={(e) => setCategory(e.target.value)}><option value="">Toutes les filières</option>{categories.map((item) => <option key={item.category} value={item.category}>{item.category} ({item.count})</option>)}</select></div>
          <button type="submit" className="btn btn-primary" disabled={searching || search.trim().length < 2}>{searching && <span className="spinner" />} Rechercher</button>
        </form>
        {hits && <div className="course-search-results">{hits.length === 0 ? <Empty title="Aucune leçon pertinente">Essayez d’autres mots-clés ou choisissez une autre filière.</Empty> : hits.map((hit) => <article className="course-search-hit" key={hit.id}><div><div className="row"><span className="badge">{hit.category}</span><span className={`badge ${LEVEL_TONE[hit.level] || ''}`}>{hit.level}</span><span className="badge">Pertinence {num(hit.score * 100, 0)} %</span></div><h3>{hit.title}</h3><p>{hit.passage}</p></div><button type="button" className="btn btn-sm" onClick={() => openCourse(hit.id)}>Ouvrir</button></article>)}<button type="button" className="btn-link" onClick={() => { setHits(null); setSearch('') }}>Effacer la recherche</button></div>}
      </Card>

      <section className="course-library-head"><div><span className="eyebrow">Bibliothèque</span><h2>{category ? `Leçons · ${category}` : 'Toutes les leçons'}</h2></div>{canEdit && !editing && <button type="button" className="btn btn-sm btn-primary" onClick={() => startEdit(null)}>Nouvelle fiche</button>}</section>
      {courses.length === 0 ? <Card><Empty title="Bibliothèque vide">{canEdit ? 'Ajoutez la première fiche.' : 'Aucune leçon n’est disponible dans cette filière.'}</Empty></Card> : <div className="course-grid">{courses.map((course) => <CourseTile key={course.id} course={course} canEdit={canEdit} opening={openingId === course.id} onOpen={openCourse} onDelete={setToDelete} />)}</div>}

      <ConfirmDialog open={Boolean(toDelete)} title="Supprimer cette fiche ?" message={`La fiche « ${toDelete?.title} » sera retirée de la bibliothèque. L’AI Tutor ne pourra plus s’en servir pour répondre.`} confirmLabel="Supprimer" busy={saving} onConfirm={confirmDelete} onCancel={() => setToDelete(null)} />
    </div>
  )
}
