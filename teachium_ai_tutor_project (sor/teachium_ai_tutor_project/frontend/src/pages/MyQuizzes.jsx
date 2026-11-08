import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { quizApi, readError } from '../services/api'
import { Alert, Card, Empty, Loading, StatCard, formatDate, num } from '../components/ui'

const DIFFICULTY_TONE = { Facile: 'badge-green', Moyen: 'badge-blue', Difficile: 'badge-amber' }

function quizStatus(quiz) {
  if (quiz.passed) return 'passed'
  if (quiz.attempts_count > 0) return 'retry'
  return 'new'
}

function QuizCard({ quiz }) {
  const status = quizStatus(quiz)
  const due = quiz.due_date ? new Date(quiz.due_date) : null
  const overdue = due && !Number.isNaN(due.getTime()) && due.getTime() < Date.now() && !quiz.passed
  const statusLabel = status === 'passed' ? 'Réussi' : status === 'retry' ? 'À reprendre' : 'À commencer'
  const statusTone = status === 'passed' ? 'badge-green' : status === 'retry' ? 'badge-amber' : 'badge-blue'

  return (
    <article className={`quiz-card quiz-card-${status}`}>
      <div className="quiz-card-top">
        <div className="row quiz-card-badges">
          <span className={`badge ${statusTone}`}>{statusLabel}</span>
          <span className={`badge ${DIFFICULTY_TONE[quiz.difficulty] || ''}`}>{quiz.difficulty}</span>
          {quiz.assigned && <span className="badge">Attribué</span>}
        </div>
        {quiz.category && <span className="quiz-category">{quiz.category}</span>}
      </div>

      <div>
        <h3 className="quiz-card-title">{quiz.title}</h3>
        {quiz.description && <p className="quiz-card-description">{quiz.description}</p>}
      </div>

      <div className="quiz-card-meta">
        <span><strong>{quiz.question_count}</strong> question{quiz.question_count > 1 ? 's' : ''}</span>
        <span>Seuil <strong>{num(quiz.passing_score, 0)}/100</strong></span>
        {quiz.attempts_count > 0 && (
          <span><strong>{quiz.attempts_count}</strong> tentative{quiz.attempts_count > 1 ? 's' : ''}</span>
        )}
      </div>

      {due && !Number.isNaN(due.getTime()) && (
        <div className={`quiz-due ${overdue ? 'is-overdue' : ''}`}>
          {overdue ? 'Échéance dépassée' : 'À terminer avant'} : {formatDate(quiz.due_date, false)}
        </div>
      )}

      <div className="quiz-card-footer">
        <div>
          {quiz.best_score != null ? (
            <><span className="small muted">Meilleur score</span><div className="quiz-best-score">{num(quiz.best_score)}/100</div></>
          ) : (
            <span className="small muted">Pas encore de résultat</span>
          )}
        </div>
        <Link className={`btn btn-sm ${status === 'new' ? 'btn-primary' : ''}`} to={`/apprenant/quiz/${quiz.id}`}>
          {status === 'new' ? 'Commencer' : status === 'retry' ? 'Reprendre' : 'Repasser'}
        </Link>
      </div>
    </article>
  )
}

export default function MyQuizzes() {
  const [quizzes, setQuizzes] = useState([])
  const [attempts, setAttempts] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [filters, setFilters] = useState({ search: '', status: 'all', category: 'all', difficulty: 'all' })

  const load = useCallback(async () => {
    try {
      setError('')
      const [list, history] = await Promise.all([quizApi.mine(), quizApi.myAttempts()])
      setQuizzes(Array.isArray(list.data) ? list.data : [])
      setAttempts(Array.isArray(history.data) ? history.data : [])
    } catch (err) {
      setError(readError(err))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const categories = useMemo(
    () => [...new Set(quizzes.map((quiz) => quiz.category).filter(Boolean))].sort(),
    [quizzes],
  )

  const shown = useMemo(() => {
    const query = filters.search.trim().toLocaleLowerCase('fr')
    return quizzes
      .filter((quiz) => {
        const haystack = `${quiz.title} ${quiz.description || ''} ${quiz.category || ''}`.toLocaleLowerCase('fr')
        return (!query || haystack.includes(query))
          && (filters.status === 'all' || quizStatus(quiz) === filters.status)
          && (filters.category === 'all' || quiz.category === filters.category)
          && (filters.difficulty === 'all' || quiz.difficulty === filters.difficulty)
      })
      .sort((a, b) => {
        const rank = { retry: 0, new: 1, passed: 2 }
        const statusDiff = rank[quizStatus(a)] - rank[quizStatus(b)]
        if (statusDiff) return statusDiff
        const aDue = a.due_date ? new Date(a.due_date).getTime() : Number.MAX_SAFE_INTEGER
        const bDue = b.due_date ? new Date(b.due_date).getTime() : Number.MAX_SAFE_INTEGER
        return aDue - bDue || a.title.localeCompare(b.title, 'fr')
      })
  }, [quizzes, filters])

  if (loading) return <Loading />

  const newCount = quizzes.filter((quiz) => quizStatus(quiz) === 'new').length
  const retryCount = quizzes.filter((quiz) => quizStatus(quiz) === 'retry').length
  const passedCount = quizzes.filter((quiz) => quizStatus(quiz) === 'passed').length
  const attempted = quizzes.filter((quiz) => quiz.best_score != null)
  const averageBest = attempted.length
    ? attempted.reduce((sum, quiz) => sum + Number(quiz.best_score), 0) / attempted.length
    : null

  const updateFilter = (key) => (event) => setFilters((current) => ({ ...current, [key]: event.target.value }))

  return (
    <div className="stack">
      <Alert type="error" onClose={() => setError('')}>{error}</Alert>

      <section className="quiz-hero">
        <div>
          <span className="eyebrow">Votre parcours</span>
          <h1>Progressez quiz après quiz</h1>
          <p>Les corrections sont automatiques. Chaque résultat affine votre profil et les conseils de l’AI Tutor.</p>
        </div>
        <Link className="btn btn-hero" to="/apprenant/tuteur?question=Quel+quiz+dois-je+passer+ensuite+%3F">
          Demander conseil au tuteur
        </Link>
      </section>

      <div className="grid grid-4">
        <StatCard label="Quiz disponibles" value={quizzes.length} />
        <StatCard label="À commencer" value={newCount} />
        <StatCard label="À reprendre" value={retryCount} hint={retryCount ? 'Commencez par vos notions les plus fragiles' : null} />
        <StatCard label="Réussis" value={passedCount} hint={averageBest != null ? `Meilleure moyenne : ${num(averageBest)}/100` : null} />
      </div>

      <Card title="Mes quiz" subtitle={`${shown.length} résultat${shown.length > 1 ? 's' : ''} affiché${shown.length > 1 ? 's' : ''}`}>
        <div className="quiz-filters">
          <div className="field">
            <label htmlFor="quiz-search">Rechercher</label>
            <input id="quiz-search" value={filters.search} onChange={updateFilter('search')} placeholder="Titre, thème ou filière" />
          </div>
          <div className="field">
            <label htmlFor="quiz-status">État</label>
            <select id="quiz-status" value={filters.status} onChange={updateFilter('status')}>
              <option value="all">Tous</option>
              <option value="new">À commencer</option>
              <option value="retry">À reprendre</option>
              <option value="passed">Réussis</option>
            </select>
          </div>
          <div className="field">
            <label htmlFor="quiz-category">Filière</label>
            <select id="quiz-category" value={filters.category} onChange={updateFilter('category')}>
              <option value="all">Toutes</option>
              {categories.map((category) => <option key={category} value={category}>{category}</option>)}
            </select>
          </div>
          <div className="field">
            <label htmlFor="quiz-difficulty">Difficulté</label>
            <select id="quiz-difficulty" value={filters.difficulty} onChange={updateFilter('difficulty')}>
              <option value="all">Toutes</option>
              {Object.keys(DIFFICULTY_TONE).map((difficulty) => (
                <option key={difficulty} value={difficulty}>{difficulty}</option>
              ))}
            </select>
          </div>
        </div>

        {shown.length === 0 ? (
          <Empty title={quizzes.length ? 'Aucun quiz ne correspond aux filtres' : 'Aucun quiz disponible'}>
            {quizzes.length
              ? 'Modifiez les filtres pour retrouver un quiz.'
              : 'Votre formateur peut vous attribuer des quiz adaptés à votre filière.'}
          </Empty>
        ) : (
          <div className="quiz-grid">
            {shown.map((quiz) => <QuizCard key={quiz.id} quiz={quiz} />)}
          </div>
        )}
      </Card>

      <Card title={`Historique des copies (${attempts.length})`} subtitle="Toutes vos tentatives, de la plus récente à la plus ancienne">
        {attempts.length === 0 ? (
          <Empty title="Aucune copie">Passez votre premier quiz pour alimenter votre profil.</Empty>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Quiz</th>
                  <th className="text-right">Note</th>
                  <th className="text-right">Bonnes réponses</th>
                  <th className="text-right">Durée</th>
                  <th>Résultat</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {attempts.map((attempt) => (
                  <tr key={attempt.id}>
                    <td className="nowrap small muted">{formatDate(attempt.submitted_at)}</td>
                    <td>{attempt.quiz_title}</td>
                    <td className="text-right num"><strong>{num(attempt.score)}/100</strong></td>
                    <td className="text-right num">{attempt.correct_count}/{attempt.total_questions}</td>
                    <td className="text-right num">
                      {attempt.duration_seconds ? `${Math.max(1, Math.round(attempt.duration_seconds / 60))} min` : '—'}
                    </td>
                    <td>
                      <span className={`badge ${attempt.passed ? 'badge-green' : 'badge-red'}`}>
                        {attempt.passed ? 'Réussi' : 'À retravailler'}
                      </span>
                    </td>
                    <td className="text-right">
                      <Link className="btn btn-sm" to={`/apprenant/quiz/copie/${attempt.id}`}>Voir la correction</Link>
                    </td>
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
