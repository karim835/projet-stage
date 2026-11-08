/**
 * Client HTTP unique de l'application.
 *
 * - Ajoute automatiquement le jeton JWT sur chaque requête.
 * - Traduit toute erreur réseau ou serveur en message lisible en français.
 * - Ne journalise jamais de trace technique dans l'interface utilisateur.
 */
import axios from 'axios'

const TOKEN_KEY = 'teachium_token'

// Vide => on passe par le proxy Vite (/api -> 127.0.0.1:8000), pratique en développement.
const baseURL = import.meta.env.VITE_API_URL || ''

export const api = axios.create({ baseURL, timeout: 45000 })

export function getToken() {
  try {
    return localStorage.getItem(TOKEN_KEY)
  } catch {
    return null
  }
}

export function setToken(token) {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token)
    else localStorage.removeItem(TOKEN_KEY)
  } catch {
    /* stockage indisponible (navigation privée) : la session reste valable pour l'onglet */
  }
}

api.interceptors.request.use((config) => {
  const token = getToken()
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

/** Convertit une erreur Axios en message compréhensible. */
export function readError(error) {
  if (!error) return "Une erreur inconnue s'est produite."

  if (error.code === 'ECONNABORTED') {
    return "Le serveur met trop de temps à répondre. Réessayez dans un instant."
  }
  if (!error.response) {
    return "Impossible de joindre l'API. Vérifiez que le backend est démarré sur http://127.0.0.1:8000."
  }

  const { status, data } = error.response
  const detail = data?.detail

  if (typeof detail === 'string' && detail.trim()) return detail
  if (Array.isArray(detail) && detail.length) {
    return detail.map((d) => d.msg || JSON.stringify(d)).join(' ; ')
  }

  switch (status) {
    case 401: return 'Session expirée ou identifiants invalides. Reconnectez-vous.'
    case 403: return "Vous n'avez pas les droits nécessaires pour cette action."
    case 404: return 'Ressource introuvable.'
    case 409: return 'Ce contenu existe déjà.'
    case 422: return 'Les données envoyées sont invalides.'
    case 503: return "Service momentanément indisponible (base de données injoignable)."
    default: return `Erreur ${status}. Réessayez ou contactez l'administrateur.`
  }
}

/* --- Points d'entrée de l'API ------------------------------------------- */

export const authApi = {
  login: (email, password) => api.post('/api/auth/login', { email, password }),
  register: (payload) => api.post('/api/auth/register', payload),
  me: () => api.get('/api/auth/me'),
  changePassword: (current_password, new_password) =>
    api.post('/api/auth/change-password', { current_password, new_password }),
}

export const learnerApi = {
  myDashboard: () => api.get('/api/learners/me'),
  analyzeMe: () => api.post('/api/learners/me/analyze'),
  updateMe: (payload) => api.patch('/api/learners/me', payload),
  myActivity: () => api.get('/api/learners/me/activity'),
  list: (params) => api.get('/api/learners', { params }),
  detail: (id) => api.get(`/api/learners/${id}`),
  update: (id, payload) => api.patch(`/api/learners/${id}`, payload),
  analyze: (id) => api.post(`/api/learners/${id}/analyze`),
}

export const tutorApi = {
  ask: (question) => api.post('/api/chat/ask', { question }),
  history: () => api.get('/api/chat/history'),
  clear: () => api.delete('/api/chat/history'),
  engine: () => api.get('/api/tutor/engine'),
}

export const recommendationApi = {
  mine: () => api.get('/api/recommendations/me'),
  history: () => api.get('/api/recommendations/me/history'),
  complete: (id, completed) => api.post(`/api/recommendations/${id}/complete`, { completed }),
}

export const statsApi = {
  dashboard: () => api.get('/api/dashboard/stats'),
  modelEvaluation: () => api.get('/api/model/evaluate'),
  health: () => api.get('/health'),
}

export const adminApi = {
  overview: () => api.get('/api/admin/overview'),
  users: (params) => api.get('/api/admin/users', { params }),
  updateUser: (id, payload) => api.patch(`/api/admin/users/${id}`, payload),
  deleteUser: (id, confirmEmail) =>
    api.post(`/api/admin/users/${id}/delete`, { confirm_email: confirmEmail }),
  activity: () => api.get('/api/admin/activity'),
  recentRecommendations: () => api.get('/api/admin/recommendations', { params: { limit: 30 } }),
}

/**
 * Quiz.
 *
 * Côté apprenant, aucune méthode ne transporte de note : `submit` n'envoie que
 * des index de réponses. La correction est faite par le serveur.
 */
export const quizApi = {
  // --- Apprenant ---
  mine: () => api.get('/api/quizzes/me'),
  myAttempts: () => api.get('/api/quizzes/me/attempts'),
  take: (id) => api.get(`/api/quizzes/${id}/take`),
  // Un indice ne contient jamais la bonne réponse. Le serveur contrôle que la
  // question appartient bien à un quiz accessible à l'apprenant.
  hint: (quizId, questionId) =>
    api.get(`/api/quizzes/${quizId}/questions/${questionId}/hint`),
  submit: (id, answers, startedAt) =>
    api.post(`/api/quizzes/${id}/submit`, { answers, started_at: startedAt }),
  attempt: (attemptId) => api.get(`/api/quizzes/attempts/${attemptId}`),

  // --- Formateur / administrateur ---
  list: (params) => api.get('/api/quizzes', { params }),
  detail: (id) => api.get(`/api/quizzes/${id}`),
  create: (payload) => api.post('/api/quizzes', payload),
  update: (id, payload) => api.patch(`/api/quizzes/${id}`, payload),
  remove: (id) => api.delete(`/api/quizzes/${id}`),
  assign: (id, learnerIds, dueDate = null) => api.post(`/api/quizzes/${id}/assign`, {
    learner_ids: learnerIds,
    due_date: dueDate || null,
  }),
  unassign: (id, learnerId) => api.delete(`/api/quizzes/${id}/assign/${learnerId}`),
  results: (id) => api.get(`/api/quizzes/${id}/results`),
  recordEvaluation: (learnerId, payload) =>
    api.post(`/api/learners/${learnerId}/evaluations`, payload),
}

/** Bibliothèque de cours : lecture pour tous, écriture réservée aux formateurs. */
export const courseApi = {
  list: (params) => api.get('/api/courses', { params }),
  categories: () => api.get('/api/courses/categories'),
  detail: (id) => api.get(`/api/courses/${id}`),
  complete: (id) => api.post(`/api/courses/${id}/complete`),
  search: (q, category) => api.get('/api/courses/search', { params: { q, category } }),
  create: (payload) => api.post('/api/courses', payload),
  update: (id, payload) => api.patch(`/api/courses/${id}`, payload),
  remove: (id) => api.delete(`/api/courses/${id}`),
}

/** Endpoints ML sans état — utiles pour la page « Simulateur ». */
export const mlApi = {
  analyzeProfile: (payload) => api.post('/api/profile/analyze', payload),
  recommend: (payload) => api.post('/api/recommendations', payload),
}
