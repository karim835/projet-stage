import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { AuthProvider, homeRouteFor, useAuth } from './context/AuthContext'
import Layout from './components/Layout'
import { Loading } from './components/ui'

import Login from './pages/Login'
import Register from './pages/Register'
import LearnerDashboard from './pages/LearnerDashboard'
import AITutor from './pages/AITutor'
import Recommendations from './pages/Recommendations'
import MyQuizzes from './pages/MyQuizzes'
import TakeQuiz from './pages/TakeQuiz'
import QuizManager from './pages/QuizManager'
import Courses from './pages/Courses'
import AttemptReview from './pages/AttemptReview'
import TrainerDashboard from './pages/TrainerDashboard'
import LearnerList from './pages/LearnerList'
import LearnerDetail from './pages/LearnerDetail'
import ModelEvaluation from './pages/ModelEvaluation'
import AdminDashboard from './pages/AdminDashboard'
import AdminUsers from './pages/AdminUsers'
import AdminActivity from './pages/AdminActivity'
import Simulator from './pages/Simulator'

/** Route protégée : exige une session valide et, si précisé, un rôle autorisé. */
function Protected({ roles, children }) {
  const { user, loading } = useAuth()
  const location = useLocation()

  if (loading) return <Loading label="Vérification de la session..." />
  if (!user) return <Navigate to="/connexion" state={{ from: location }} replace />
  if (roles && !roles.includes(user.role)) return <Navigate to={homeRouteFor(user.role)} replace />

  return children
}

function RootRedirect() {
  const { user, loading } = useAuth()
  if (loading) return <Loading />
  return <Navigate to={user ? homeRouteFor(user.role) : '/connexion'} replace />
}

function NotFound() {
  const { user } = useAuth()
  return (
    <div className="auth-page">
      <div className="auth-card card">
        <div className="card-body" style={{ textAlign: 'center' }}>
          <h1>Page introuvable</h1>
          <p className="muted">L'adresse demandée n'existe pas dans l'application.</p>
          <a className="btn btn-primary" href={user ? homeRouteFor(user.role) : '/connexion'}>
            Retour à l'accueil
          </a>
        </div>
      </div>
    </div>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/" element={<RootRedirect />} />
        <Route path="/connexion" element={<Login />} />
        <Route path="/inscription" element={<Register />} />

        {/* Espace apprenant */}
        <Route element={<Protected roles={['learner']}><Layout /></Protected>}>
          <Route path="/apprenant" element={<LearnerDashboard />} />
          <Route path="/apprenant/tuteur" element={<AITutor />} />
          <Route path="/apprenant/recommandations" element={<Recommendations />} />
          <Route path="/apprenant/quiz" element={<MyQuizzes />} />
          <Route path="/apprenant/quiz/copie/:attemptId" element={<AttemptReview />} />
          <Route path="/apprenant/quiz/:id" element={<TakeQuiz />} />
          <Route path="/apprenant/cours" element={<Courses />} />
        </Route>

        {/* Espace formateur, également accessible aux administrateurs */}
        <Route element={<Protected roles={['trainer', 'administrator']}><Layout /></Protected>}>
          <Route path="/formateur" element={<TrainerDashboard />} />
          <Route path="/formateur/apprenants" element={<LearnerList />} />
          <Route path="/formateur/apprenants/:id" element={<LearnerDetail />} />
          <Route path="/formateur/quiz" element={<QuizManager />} />
          <Route path="/formateur/cours" element={<Courses />} />
          <Route path="/formateur/modele" element={<ModelEvaluation />} />
          <Route path="/simulateur" element={<Simulator />} />
        </Route>

        {/* Espace administrateur */}
        <Route element={<Protected roles={['administrator']}><Layout /></Protected>}>
          <Route path="/admin" element={<AdminDashboard />} />
          <Route path="/admin/utilisateurs" element={<AdminUsers />} />
          <Route path="/admin/activite" element={<AdminActivity />} />
        </Route>

        <Route path="*" element={<NotFound />} />
      </Routes>
    </AuthProvider>
  )
}
