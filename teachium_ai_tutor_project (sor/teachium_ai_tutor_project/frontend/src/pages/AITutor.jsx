import { useCallback, useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { learnerApi, readError, tutorApi } from '../services/api'
import { Alert, Card, ConfirmDialog, Loading, ProfileBadge, RiskBadge, formatDate, num } from '../components/ui'

const SUGGESTIONS = [
  'Quel est mon profil ?',
  'Pourquoi ai-je reçu cette recommandation ?',
  'Comment puis-je progresser ?',
  'Quel cours dois-je revoir ?',
  'Quel est mon score moyen ?',
]

function InlineTutorText({ text }) {
  const parts = String(text || '').split(/(\*\*[^*]+\*\*|`[^`]+`)/g).filter(Boolean)
  return parts.map((part, index) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong key={`${part}-${index}`}>{part.slice(2, -2)}</strong>
    }
    if (part.startsWith('`') && part.endsWith('`')) {
      return <code key={`${part}-${index}`}>{part.slice(1, -1)}</code>
    }
    return <span key={`${part}-${index}`}>{part}</span>
  })
}

/** Affichage volontairement limité : aucun HTML injecté, même si le texte vient du moteur. */
function TutorMessage({ text }) {
  return (
    <div className="tutor-message-content">
      {String(text || '').split('\n').map((line, index) => {
        const trimmed = line.trim()
        if (!trimmed) return <span className="tutor-message-gap" key={`gap-${index}`} />
        if (/^[-*]\s+/.test(trimmed)) {
          return <div className="tutor-message-list-item" key={`item-${index}`}><span aria-hidden="true">•</span><span><InlineTutorText text={trimmed.replace(/^[-*]\s+/, '')} /></span></div>
        }
        const heading = trimmed.match(/^#{1,3}\s+(.+)/)
        if (heading) return <strong className="tutor-message-heading" key={`heading-${index}`}><InlineTutorText text={heading[1]} /></strong>
        return <span className="tutor-message-line" key={`line-${index}`}><InlineTutorText text={line} /></span>
      })}
    </div>
  )
}

export default function AITutor() {
  const [searchParams] = useSearchParams()
  const promptContext = useRef({
    question: searchParams.get('question')?.trim() || '',
    quiz: searchParams.get('quiz')?.trim() || '',
    attemptId: searchParams.get('attemptId') || '',
  })
  const [messages, setMessages] = useState([])
  const [learner, setLearner] = useState(null)
  const [question, setQuestion] = useState('')
  const [loading, setLoading] = useState(true)
  const [sending, setSending] = useState(false)
  const [error, setError] = useState('')
  const [confirmClear, setConfirmClear] = useState(false)
  const logRef = useRef(null)
  const questionRef = useRef(null)

  const load = useCallback(async () => {
    try {
      setError('')
      const [history, dashboard] = await Promise.all([tutorApi.history(), learnerApi.myDashboard()])
      setMessages(history.data.messages)
      setLearner(dashboard.data.learner)
    } catch (err) {
      setError(readError(err))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  useEffect(() => {
    if (promptContext.current.question) {
      setQuestion(promptContext.current.question)
      window.requestAnimationFrame(() => questionRef.current?.focus())
    }
  }, [])

  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight
  }, [messages, sending])

  async function send(text) {
    const content = (text ?? question).trim()
    if (!content) {
      setError('Écrivez une question avant d\'envoyer.')
      return
    }
    if (sending) return

    setError('')
    setSending(true)
    setQuestion('')

    // Affichage optimiste du message utilisateur.
    const optimistic = { id: `tmp-${Date.now()}`, role: 'user', message: content, created_at: new Date().toISOString() }
    setMessages((m) => [...m, optimistic])

    try {
      const { data } = await tutorApi.ask(content)
      setMessages((m) => [
        ...m,
        { id: `a-${Date.now()}`, role: 'assistant', message: data.answer, created_at: new Date().toISOString() },
      ])
    } catch (err) {
      // On retire le message optimiste : rien n'a été enregistré côté serveur.
      setMessages((m) => m.filter((msg) => msg.id !== optimistic.id))
      setQuestion(content)
      setError(readError(err))
    } finally {
      setSending(false)
    }
  }

  async function clearConversation() {
    try {
      await tutorApi.clear()
      setMessages([])
    } catch (err) {
      setError(readError(err))
    } finally {
      setConfirmClear(false)
    }
  }

  function onKeyDown(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      send()
    }
  }

  if (loading) return <Loading />

  return (
    <div className="stack">
      {learner && (
        <Card>
          <div className="row-between">
            <div className="row" style={{ gap: 8 }}>
              <ProfileBadge profile={learner.profile} large />
              <RiskBadge level={learner.risk_level} />
              <span className="badge">Score {num(learner.average_score)}/100</span>
              <span className="badge">Complétion {num(learner.completion_rate)} %</span>
              {learner.cluster != null && <span className="badge">Cluster {learner.cluster}</span>}
            </div>
            <button type="button" className="btn btn-sm" onClick={() => setConfirmClear(true)} disabled={!messages.length}>
              Effacer la conversation
            </button>
          </div>
        </Card>
      )}

      <Alert type="error" onClose={() => setError('')}>{error}</Alert>

      {promptContext.current.question && (
        <section className="tutor-prompt-context" aria-label="Question préparée depuis votre correction">
          <div className="tutor-prompt-icon" aria-hidden="true">✦</div>
          <div>
            <span className="eyebrow">Question préparée{promptContext.current.quiz ? ` · ${promptContext.current.quiz}` : ''}</span>
            <strong>Votre erreur peut devenir une piste de progression.</strong>
            <p>Relisez la question ci-dessous, ajustez-la si besoin, puis envoyez-la au tuteur.</p>
          </div>
          <button
            type="button"
            className="btn btn-sm"
            onClick={() => setQuestion(promptContext.current.question)}
            disabled={sending || question === promptContext.current.question}
          >
            Restaurer la question
          </button>
        </section>
      )}

      {/* Structure volontairement sans <Card> : la colonne flex doit être directe
          pour que la zone de messages occupe toute la hauteur disponible. */}
      <section className="card chat-shell">
        <div className="chat-log" ref={logRef}>
          {messages.length === 0 && (
            <div className="empty">
              <strong>Posez votre première question</strong>
              L'AI Tutor connaît votre profil, vos indicateurs et vos recommandations en cours.
            </div>
          )}

          {messages.map((m) => (
            <div key={m.id} className={`msg ${m.role === 'user' ? 'msg-user' : ''}`}>
              <div className="msg-avatar">{m.role === 'user' ? 'Moi' : 'AI'}</div>
              <div>
                <div className="msg-bubble"><TutorMessage text={m.message} /></div>
                <div className="msg-time">{formatDate(m.created_at)}</div>
              </div>
            </div>
          ))}

          {sending && (
            <div className="msg">
              <div className="msg-avatar">AI</div>
              <div className="msg-bubble row" style={{ gap: 8 }}>
                <span className="spinner" /> <span className="muted">Analyse de votre profil...</span>
              </div>
            </div>
          )}
        </div>

        <div className="chat-input">
          <div className="chat-suggestions">
            {SUGGESTIONS.map((s) => (
              <button key={s} type="button" className="chip" onClick={() => send(s)} disabled={sending}>
                {s}
              </button>
            ))}
          </div>
          <div className="chat-input-row">
            <textarea
              ref={questionRef}
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={onKeyDown}
              placeholder="Posez votre question à l'AI Tutor... (Entrée pour envoyer, Maj+Entrée pour un retour à la ligne)"
              rows={2}
              disabled={sending}
            />
            <button type="button" className="btn btn-primary" onClick={() => send()} disabled={sending || !question.trim()}>
              {sending && <span className="spinner" />} Envoyer
            </button>
          </div>
        </div>
      </section>

      <ConfirmDialog
        open={confirmClear}
        title="Effacer la conversation ?"
        message="Tous les messages échangés avec l'AI Tutor seront définitivement supprimés de la base de données. Votre profil et vos recommandations ne sont pas affectés."
        confirmLabel="Effacer"
        onConfirm={clearConversation}
        onCancel={() => setConfirmClear(false)}
      />
    </div>
  )
}
