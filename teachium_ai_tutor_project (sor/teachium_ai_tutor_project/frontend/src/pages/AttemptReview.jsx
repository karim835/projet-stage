import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { quizApi, readError } from '../services/api'
import { Alert, Card, Loading, formatDate, num } from '../components/ui'
import TutorFeedback, { feedbackFromAnswers } from '../components/TutorFeedback'

/** Relecture d'une copie déjà corrigée : bonnes réponses et explications. */
export default function AttemptReview() {
  const { attemptId } = useParams()
  const [attempt, setAttempt] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    quizApi.attempt(attemptId)
      .then(({ data }) => setAttempt(data))
      .catch((err) => setError(readError(err)))
      .finally(() => setLoading(false))
  }, [attemptId])

  if (loading) return <Loading />
  if (!attempt) return <Alert type="error">{error || 'Copie introuvable.'}</Alert>

  const feedback = attempt.tutor_feedback || feedbackFromAnswers(attempt.answers)

  return (
    <div className="stack">
      <Card
        title={attempt.passed ? 'Quiz réussi' : 'Quiz échoué'}
        subtitle={`Copie rendue le ${formatDate(attempt.submitted_at)}`}
        actions={<Link className="btn btn-sm" to="/apprenant/quiz">Retour à mes quiz</Link>}
      >
        <div className="row" style={{ gap: 8 }}>
          <span className={`badge badge-lg ${attempt.passed ? 'badge-green' : 'badge-red'}`}>
            {num(attempt.score)}/100
          </span>
          <span className="badge">{attempt.correct_count}/{attempt.total_questions} bonnes réponses</span>
          {attempt.duration_seconds > 0 && (
            <span className="badge">Durée : {Math.max(1, Math.round(attempt.duration_seconds / 60))} min</span>
          )}
        </div>
      </Card>

      <TutorFeedback feedback={feedback} attemptId={attempt.id} />

      <Card title="Correction détaillée">
        <div className="stack" style={{ gap: 14 }}>
          {attempt.answers.map((item, index) => (
            <div key={item.question_id} className="card" style={{ boxShadow: 'none' }}>
              <div className="card-body">
                <div className="row-between" style={{ alignItems: 'flex-start' }}>
                  <h3 style={{ flex: 1 }}>{index + 1}. {item.question_text}</h3>
                  <span className={`badge ${item.is_correct ? 'badge-green' : 'badge-red'}`}>
                    {item.is_correct ? 'Correct' : 'Incorrect'}
                  </span>
                </div>
                <div className="stack mt-2" style={{ gap: 6 }}>
                  {item.options.map((option, optionIndex) => {
                    const isCorrect = optionIndex === item.correct_index
                    const isChosen = optionIndex === item.chosen_index
                    let tone = 'var(--border)'
                    let background = 'var(--surface)'
                    if (isCorrect) { tone = 'var(--green-border)'; background = 'var(--green-soft)' }
                    else if (isChosen) { tone = 'var(--red-border)'; background = 'var(--red-soft)' }
                    return (
                      <div key={optionIndex} style={{
                        border: `1px solid ${tone}`, background,
                        borderRadius: 'var(--radius-sm)', padding: '8px 11px', fontSize: 13.5,
                      }}>
                        {option}
                        {isCorrect && <span className="badge badge-green" style={{ marginLeft: 8 }}>Bonne réponse</span>}
                        {isChosen && !isCorrect && <span className="badge badge-red" style={{ marginLeft: 8 }}>Votre réponse</span>}
                      </div>
                    )
                  })}
                  {item.chosen_index === null && (
                    <span className="small muted">Vous n'avez pas répondu à cette question.</span>
                  )}
                </div>
                {item.explanation && (
                  <p className="metric-explain mt-2" style={{ marginBottom: 0 }}>
                    <strong>Explication :</strong> {item.explanation}
                  </p>
                )}
              </div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  )
}
