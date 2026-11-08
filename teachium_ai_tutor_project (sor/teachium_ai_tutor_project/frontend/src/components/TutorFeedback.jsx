import { Link } from 'react-router-dom'
import { Card } from './ui'

function FeedbackList({ items, empty }) {
  const values = Array.isArray(items) ? items.filter(Boolean) : []
  if (!values.length) return empty ? <p className="small muted">{empty}</p> : null
  return (
    <ul className="feedback-list">
      {values.map((item, index) => <li key={`${item}-${index}`}>{item}</li>)}
    </ul>
  )
}

export function feedbackFromAnswers(answers = []) {
  const incorrect = Array.isArray(answers) ? answers.filter((answer) => !answer.is_correct) : []
  if (!incorrect.length) return null
  const topics = [...new Set(incorrect.map((answer) => answer.concept).filter(Boolean))]
  const questions = incorrect.slice(0, 3).map((answer) => {
    if (answer.concept) return `Peux-tu m’expliquer la notion « ${answer.concept} » et m’aider à comprendre mon erreur ?`
    const prompt = String(answer.question_text || '').replace(/\s+/g, ' ').slice(0, 140)
    return `Peux-tu m’aider à raisonner sur cette question : « ${prompt} » ?`
  })
  return {
    summary: `${incorrect.length} réponse${incorrect.length > 1 ? 's' : ''} mérite${incorrect.length > 1 ? 'nt' : ''} d’être reprise avec le tuteur.`,
    strengths: [],
    focus_topics: topics,
    next_steps: ['Relisez les explications de la correction.', 'Posez une question ciblée à l’AI Tutor avant de repasser le quiz.'],
    suggested_questions: questions,
  }
}

/** Coaching produit côté serveur à partir de la copie corrigée. */
export default function TutorFeedback({ feedback, quizTitle = '', attemptId = null }) {
  if (!feedback) return null

  const suggestions = Array.isArray(feedback.suggested_questions)
    ? feedback.suggested_questions.filter(Boolean)
    : []

  const tutorLink = (question) => {
    const params = new URLSearchParams()
    if (question) params.set('question', question)
    if (quizTitle) params.set('quiz', quizTitle)
    if (attemptId) params.set('attemptId', String(attemptId))
    return `/apprenant/tuteur?${params.toString()}`
  }

  return (
    <Card
      className="tutor-feedback"
      title="Conseils personnalisés de l’AI Tutor"
      subtitle="Une synthèse construite à partir de cette copie et de votre progression"
      actions={<span className="badge badge-blue">Coaching</span>}
    >
      {feedback.summary && <p className="feedback-summary">{feedback.summary}</p>}

      <div className="feedback-grid">
        <section className="feedback-block feedback-strengths">
          <div className="feedback-label">Points acquis</div>
          <FeedbackList items={feedback.strengths} empty="Continuez à consolider les notions réussies." />
        </section>
        <section className="feedback-block feedback-focus">
          <div className="feedback-label">À revoir en priorité</div>
          <FeedbackList items={feedback.focus_topics} empty="Aucune difficulté prioritaire détectée." />
        </section>
        <section className="feedback-block feedback-next">
          <div className="feedback-label">Prochaines étapes</div>
          <FeedbackList items={feedback.next_steps} />
        </section>
      </div>

      <div className="feedback-actions">
        {suggestions.length > 0 && <div className="feedback-action-label">Questions à poser à l’AI Tutor</div>}
        {suggestions.slice(0, 3).map((question) => (
          <Link key={question} className="chip chip-action" to={tutorLink(question)}>
            <span aria-hidden="true">→</span>{question}
          </Link>
        ))}
        <Link
          className="btn btn-sm btn-primary"
          to={tutorLink(suggestions[0] || `Que dois-je revoir après le quiz ${quizTitle} ?`)}
        >
          Continuer avec le tuteur
        </Link>
      </div>
    </Card>
  )
}
