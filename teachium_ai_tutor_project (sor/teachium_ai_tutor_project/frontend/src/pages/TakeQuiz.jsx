import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { quizApi, readError } from '../services/api'
import { Alert, Card, ConfirmDialog, Loading, ProfileBadge, num } from '../components/ui'
import TutorFeedback, { feedbackFromAnswers } from '../components/TutorFeedback'

function savedDraft(key) {
  try {
    const value = JSON.parse(localStorage.getItem(key) || 'null')
    return value && typeof value === 'object' ? value : null
  } catch {
    return null
  }
}

function saveDraft(key, value) {
  try { localStorage.setItem(key, JSON.stringify(value)) } catch { /* stockage indisponible */ }
}

function removeDraft(key) {
  try { localStorage.removeItem(key) } catch { /* stockage indisponible */ }
}

function QuestionHint({ state, onRequest, onToggle }) {
  if (!state?.data) {
    return (
      <div className="hint-actions">
        <button type="button" className="btn btn-sm btn-hint" onClick={onRequest} disabled={state?.loading}>
          {state?.loading ? <span className="spinner" /> : <span aria-hidden="true">✦</span>}
          {state?.loading ? 'Le tuteur prépare un indice…' : 'Obtenir un indice'}
        </button>
        <span className="small muted">L’indice guide votre réflexion sans révéler la réponse.</span>
        {state?.error && <span className="small field-error" role="alert">{state.error}</span>}
      </div>
    )
  }

  const { hint, concept, resources = [] } = state.data
  if (!state.open) {
    return <button type="button" className="btn-link mt-1" onClick={onToggle}>Afficher l’indice</button>
  }

  return (
    <aside className="tutor-hint" aria-live="polite">
      <div className="tutor-hint-head">
        <div>
          <span className="eyebrow">Indice de l’AI Tutor</span>
          {concept && <strong>{concept}</strong>}
        </div>
        <button type="button" className="btn-link" onClick={onToggle}>Masquer</button>
      </div>
      <p>{hint}</p>
      {resources.length > 0 && (
        <div className="hint-resources">
          <span className="small muted">Pour approfondir :</span>
          {resources.slice(0, 2).map((resource) => (
            <Link key={resource.id} to="/apprenant/cours" className="hint-resource">
              <strong>{resource.title}</strong>
              <span>{resource.level}{resource.category ? ` · ${resource.category}` : ''}</span>
              {resource.summary && <small>{resource.summary}</small>}
            </Link>
          ))}
        </div>
      )}
    </aside>
  )
}

/** Passage sécurisé : le navigateur n'obtient jamais correct_index avant soumission. */
export default function TakeQuiz() {
  const { id } = useParams()
  const navigate = useNavigate()
  const draftKey = `teachium_quiz_draft_${id}`
  const [quiz, setQuiz] = useState(null)
  const [answers, setAnswers] = useState({})
  const [hints, setHints] = useState({})
  const [activeQuestion, setActiveQuestion] = useState(null)
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [abandonOpen, setAbandonOpen] = useState(false)
  const [elapsed, setElapsed] = useState(0)
  const startedAt = useRef(null)

  useEffect(() => {
    let cancelled = false
    quizApi.take(id)
      .then(({ data }) => {
        if (cancelled) return
        const draft = savedDraft(draftKey)
        const validAnswers = {}
        const questions = Array.isArray(data.questions) ? data.questions : []
        const byId = new Map(questions.map((question) => [String(question.id), question]))
        Object.entries(draft?.answers || {}).forEach(([questionId, optionIndex]) => {
          const question = byId.get(String(questionId))
          if (question && Number.isInteger(optionIndex) && optionIndex >= 0 && optionIndex < question.options.length) {
            validAnswers[questionId] = optionIndex
          }
        })
        const savedStart = draft?.startedAt && !Number.isNaN(new Date(draft.startedAt).getTime())
          ? draft.startedAt
          : new Date().toISOString()
        startedAt.current = savedStart
        setElapsed(Math.max(0, Math.floor((Date.now() - new Date(savedStart).getTime()) / 1000)))
        setAnswers(validAnswers)
        setQuiz(data)
        setActiveQuestion(questions[0]?.id ?? null)
      })
      .catch((err) => setError(readError(err)))
      .finally(() => !cancelled && setLoading(false))
    return () => { cancelled = true }
  }, [id, draftKey])

  useEffect(() => {
    if (!quiz || result || !startedAt.current) return
    saveDraft(draftKey, { answers, startedAt: startedAt.current })
  }, [answers, draftKey, quiz, result])

  useEffect(() => {
    if (!quiz || result) return
    const update = () => setElapsed(Math.max(0, Math.floor((Date.now() - new Date(startedAt.current).getTime()) / 1000)))
    const timer = setInterval(update, 1000)
    return () => clearInterval(timer)
  }, [quiz, result])

  useEffect(() => {
    if (!quiz || result || Object.keys(answers).length === 0) return
    const warn = (event) => { event.preventDefault(); event.returnValue = '' }
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [answers, quiz, result])

  async function requestHint(questionId) {
    setHints((current) => ({ ...current, [questionId]: { loading: true, open: true } }))
    try {
      // Aucun choix ni index de correction n'est envoyé : la note reste entièrement côté serveur.
      const { data } = await quizApi.hint(quiz.id, questionId)
      setHints((current) => ({ ...current, [questionId]: { loading: false, open: true, data } }))
    } catch (err) {
      setHints((current) => ({
        ...current,
        [questionId]: { loading: false, open: true, error: readError(err) },
      }))
    }
  }

  function toggleHint(questionId) {
    setHints((current) => ({
      ...current,
      [questionId]: { ...current[questionId], open: !current[questionId]?.open },
    }))
  }

  const submit = useCallback(async () => {
    setConfirmOpen(false)
    setSubmitting(true)
    setError('')
    try {
      const payload = quiz.questions.map((question) => ({
        question_id: question.id,
        chosen_index: answers[question.id] ?? null,
      }))
      const { data } = await quizApi.submit(quiz.id, payload, startedAt.current)
      removeDraft(draftKey)
      setResult(data)
      window.scrollTo({ top: 0, behavior: 'smooth' })
    } catch (err) {
      setError(readError(err))
    } finally {
      setSubmitting(false)
    }
  }, [answers, draftKey, quiz])

  function goToQuestion(questionId) {
    setActiveQuestion(questionId)
    document.getElementById(`question-${questionId}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }

  function abandon() {
    removeDraft(draftKey)
    setAbandonOpen(false)
    navigate('/apprenant/quiz')
  }

  if (loading) return <Loading />
  if (!quiz) return <Alert type="error">{error || 'Quiz introuvable.'}</Alert>

  const answered = Object.keys(answers).length
  const total = quiz.questions.length
  const progress = total ? Math.round((answered / total) * 100) : 0

  if (result) {
    const attempt = result.attempt
    const feedback = result.tutor_feedback || attempt.tutor_feedback || feedbackFromAnswers(attempt.answers)
    const tutorQuestion = `Aide-moi à comprendre mes erreurs dans le quiz ${quiz.title}.`
    return (
      <div className="stack">
        <Card className={`result-card ${attempt.passed ? 'result-success' : 'result-retry'}`}>
          <div className="result-summary">
            <div className="result-score" aria-label={`Note ${num(attempt.score)} sur 100`}>
              <strong>{num(attempt.score, 0)}</strong><span>/100</span>
            </div>
            <div className="result-copy">
              <span className="eyebrow">{attempt.passed ? 'Objectif atteint' : 'Encore un effort'}</span>
              <h1>{attempt.passed ? 'Quiz réussi' : 'Quiz à retravailler'}</h1>
              <p>{quiz.title}</p>
              <div className="row">
                <span className="badge">{attempt.correct_count}/{attempt.total_questions} bonnes réponses</span>
                <span className="badge">Seuil : {num(quiz.passing_score, 0)}/100</span>
                {attempt.duration_seconds > 0 && (
                  <span className="badge">{Math.max(1, Math.round(attempt.duration_seconds / 60))} min</span>
                )}
              </div>
            </div>
            <Link className="btn btn-sm" to="/apprenant/quiz">Retour à mes quiz</Link>
          </div>

          <div className="result-metrics">
            <span>Moyenne actualisée <strong>{num(result.average_score)}/100</strong></span>
            <span>Complétion <strong>{num(result.completion_rate)} %</strong></span>
            <span>
              Profil <ProfileBadge profile={result.new_profile} />
            </span>
          </div>

          {result.profile_changed && (
            <div className="alert alert-success mt-2">
              Votre profil pédagogique a évolué : <ProfileBadge profile={result.previous_profile} />
              <span aria-hidden="true">→</span><ProfileBadge profile={result.new_profile} />
            </div>
          )}
        </Card>

        <TutorFeedback feedback={feedback} quizTitle={quiz.title} attemptId={attempt.id} />

        <Card title="Correction détaillée" subtitle="Comparez vos choix, puis utilisez les explications pour consolider chaque notion">
          <div className="stack correction-list">
            {attempt.answers.map((item, index) => (
              <article key={item.question_id} className={`correction-card ${item.is_correct ? 'is-correct' : 'is-incorrect'}`}>
                <div className="correction-head">
                  <div><span className="question-kicker">Question {index + 1}</span><h3>{item.question_text}</h3></div>
                  <span className={`badge ${item.is_correct ? 'badge-green' : 'badge-red'}`}>
                    {item.is_correct ? 'Correct' : 'À revoir'}
                  </span>
                </div>
                <div className="answer-review-list">
                  {item.options.map((option, optionIndex) => {
                    const isCorrect = optionIndex === item.correct_index
                    const isChosen = optionIndex === item.chosen_index
                    return (
                      <div key={optionIndex} className={`answer-review ${isCorrect ? 'is-correct' : ''} ${isChosen && !isCorrect ? 'is-wrong' : ''}`}>
                        <span>{option}</span>
                        {isCorrect && <span className="badge badge-green">Bonne réponse</span>}
                        {isChosen && !isCorrect && <span className="badge badge-red">Votre réponse</span>}
                      </div>
                    )
                  })}
                  {item.chosen_index === null && <span className="small muted">Vous n’avez pas répondu à cette question.</span>}
                </div>
                {item.explanation && <p className="question-explanation"><strong>À retenir :</strong> {item.explanation}</p>}
              </article>
            ))}
          </div>
        </Card>

        <div className="page-actions">
          <Link className="btn btn-primary" to="/apprenant/quiz">Choisir un autre quiz</Link>
          <Link className="btn" to={`/apprenant/tuteur?question=${encodeURIComponent(tutorQuestion)}&attemptId=${attempt.id}&quiz=${encodeURIComponent(quiz.title)}`}>
            Revoir cette copie avec l’AI Tutor
          </Link>
        </div>
      </div>
    )
  }

  return (
    <div className="stack">
      <Alert type="error" onClose={() => setError('')}>{error}</Alert>

      <section className="quiz-progress-card">
        <div className="quiz-progress-copy">
          <span className="eyebrow">Quiz en cours</span>
          <h1>{quiz.title}</h1>
          {quiz.description && <p>{quiz.description}</p>}
          <div className="row">
            {quiz.category && <span className="badge">{quiz.category}</span>}
            <span className="badge">{quiz.difficulty}</span>
            <span className="badge">Réussite à {num(quiz.passing_score, 0)}/100</span>
          </div>
        </div>
        <div className="quiz-timer" aria-label={`Temps écoulé ${Math.floor(elapsed / 60)} minutes ${elapsed % 60} secondes`}>
          <span>Temps écoulé</span>
          <strong>{String(Math.floor(elapsed / 60)).padStart(2, '0')}:{String(elapsed % 60).padStart(2, '0')}</strong>
        </div>
        <div className="quiz-progress-bar">
          <div><strong>{answered}/{total}</strong><span> réponses</span></div>
          <div className="meter"><span style={{ width: `${progress}%` }} /></div>
          <span className="small muted">Progression {progress} % · brouillon sauvegardé sur cet appareil</span>
        </div>
      </section>

      <div className="quiz-taking-layout">
        <aside className="card quiz-navigator" aria-label="Navigation entre les questions">
          <div className="quiz-navigator-head">
            <strong>Questions</strong>
            <span className="small muted">{answered}/{total}</span>
          </div>
          <div className="quiz-question-index">
            {quiz.questions.map((question, index) => (
              <button
                key={question.id}
                type="button"
                className={`${answers[question.id] !== undefined ? 'is-answered' : ''} ${activeQuestion === question.id ? 'is-active' : ''}`}
                onClick={() => goToQuestion(question.id)}
                aria-label={`Question ${index + 1}${answers[question.id] !== undefined ? ', répondue' : ', sans réponse'}`}
              >
                {index + 1}
              </button>
            ))}
          </div>
          <div className="quiz-navigator-legend"><i /> Réponse enregistrée</div>
        </aside>

        <div className="stack quiz-questions">
          {quiz.questions.map((question, index) => {
            const selectedAnswer = answers[question.id]
            return (
              <section
                key={question.id}
                id={`question-${question.id}`}
                className="card quiz-question-card"
                onFocus={() => setActiveQuestion(question.id)}
              >
                <fieldset>
                  <legend>
                    <span className="question-kicker">Question {index + 1} sur {total}</span>
                    <span>{question.question_text}</span>
                  </legend>
                  {question.concept && <span className="badge badge-blue question-concept">{question.concept}</span>}
                  <div className="answer-options">
                    {question.options.map((option, optionIndex) => {
                      const selected = selectedAnswer === optionIndex
                      return (
                        <label key={optionIndex} className={`answer-option ${selected ? 'is-selected' : ''}`}>
                          <input
                            type="radio"
                            name={`q-${question.id}`}
                            checked={selected}
                            onChange={() => {
                              setAnswers((current) => ({ ...current, [question.id]: optionIndex }))
                              setActiveQuestion(question.id)
                            }}
                            disabled={submitting}
                          />
                          <span className="answer-letter" aria-hidden="true">{String.fromCharCode(65 + optionIndex)}</span>
                          <span>{option}</span>
                        </label>
                      )
                    })}
                  </div>
                </fieldset>

                <div className="question-tools">
                  <QuestionHint
                    state={hints[question.id]}
                    onRequest={() => requestHint(question.id)}
                    onToggle={() => toggleHint(question.id)}
                  />
                  {selectedAnswer !== undefined && (
                    <button type="button" className="btn-link" onClick={() => setAnswers((current) => {
                      const next = { ...current }
                      delete next[question.id]
                      return next
                    })}>
                      Effacer ma réponse
                    </button>
                  )}
                </div>
              </section>
            )
          })}

          <Card className="quiz-submit-card">
            <div className="row-between">
              <div>
                <strong>{answered}/{total} question{total > 1 ? 's' : ''} répondue{answered > 1 ? 's' : ''}</strong>
                {answered < total && <div className="small muted">Les réponses manquantes seront comptées comme fausses.</div>}
              </div>
              <div className="row">
                <button type="button" className="btn" onClick={() => setAbandonOpen(true)}>Quitter</button>
                <button type="button" className="btn btn-primary" onClick={() => setConfirmOpen(true)} disabled={submitting || answered === 0}>
                  {submitting && <span className="spinner" />} Envoyer ma copie
                </button>
              </div>
            </div>
          </Card>
        </div>
      </div>

      <ConfirmDialog
        open={confirmOpen}
        title="Envoyer votre copie ?"
        message={answered < total
          ? `Vous avez répondu à ${answered} question(s) sur ${total}. Les questions sans réponse seront comptées comme fausses.`
          : 'Toutes les questions ont une réponse. La correction est immédiate et vos indicateurs seront mis à jour.'}
        confirmLabel="Envoyer et voir ma correction"
        busy={submitting}
        onConfirm={submit}
        onCancel={() => setConfirmOpen(false)}
      />
      <ConfirmDialog
        open={abandonOpen}
        title="Quitter ce quiz ?"
        message="Votre brouillon est enregistré automatiquement. Si vous confirmez l’abandon, les réponses enregistrées sur cet appareil seront effacées."
        confirmLabel="Quitter et effacer"
        onConfirm={abandon}
        onCancel={() => setAbandonOpen(false)}
      />
    </div>
  )
}
