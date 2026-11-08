import { useEffect, useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

const NAV = {
  learner: [
    { group: 'Espace apprenant' },
    { to: '/apprenant', label: 'Tableau de bord', icon: 'dashboard', end: true },
    { to: '/apprenant/tuteur', label: 'AI Tutor', icon: 'tutor' },
    { to: '/apprenant/recommandations', label: 'Recommandations', icon: 'recommendations' },
    { to: '/apprenant/quiz', label: 'Mes quiz', icon: 'quiz' },
    { to: '/apprenant/cours', label: 'Cours', icon: 'courses' },
  ],
  trainer: [
    { group: 'Espace formateur' },
    { to: '/formateur', label: 'Tableau de bord', icon: 'dashboard', end: true },
    { to: '/formateur/apprenants', label: 'Apprenants', icon: 'users' },
    { to: '/formateur/quiz', label: 'Quiz', icon: 'quiz' },
    { to: '/formateur/cours', label: 'Cours', icon: 'courses' },
    { to: '/formateur/modele', label: 'Évaluation du modèle', icon: 'model' },
    { to: '/simulateur', label: 'Simulateur de profil', icon: 'settings' },
  ],
  administrator: [
    { group: 'Administration' },
    { to: '/admin', label: 'Vue d\'ensemble', icon: 'dashboard', end: true },
    { to: '/admin/utilisateurs', label: 'Comptes', icon: 'users' },
    { to: '/admin/activite', label: 'Activité système', icon: 'activity' },
    { group: 'Pédagogie' },
    { to: '/formateur/apprenants', label: 'Apprenants', icon: 'users' },
    { to: '/formateur/quiz', label: 'Quiz', icon: 'quiz' },
    { to: '/formateur/cours', label: 'Cours', icon: 'courses' },
    { to: '/formateur', label: 'Statistiques', icon: 'model', end: true },
    { to: '/formateur/modele', label: 'Évaluation du modèle', icon: 'model' },
    { to: '/simulateur', label: 'Simulateur de profil', icon: 'settings' },
  ],
}

const ICON_PATHS = {
  dashboard: <><rect x="3" y="3" width="7" height="7" rx="1" /><rect x="14" y="3" width="7" height="7" rx="1" /><rect x="3" y="14" width="7" height="7" rx="1" /><rect x="14" y="14" width="7" height="7" rx="1" /></>,
  tutor: <><path d="M8 15H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v3" /><path d="m7 19-3 2v-6" /><path d="m19 12 .7 1.8L22 14.5l-2.3.7L19 17l-.7-1.8-2.3-.7 2.3-.7L19 12Z" /></>,
  recommendations: <><path d="M4 6h16M4 12h10M4 18h7" /><path d="m17 17 2 2 3-4" /></>,
  quiz: <><rect x="4" y="3" width="16" height="18" rx="2" /><path d="m8 8 1.5 1.5L12 7M8 14h8M8 18h6" /></>,
  courses: <><path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H11v17H6.5A2.5 2.5 0 0 0 4 22V5.5ZM20 5.5A2.5 2.5 0 0 0 17.5 3H13v17h4.5A2.5 2.5 0 0 1 20 22V5.5Z" /></>,
  users: <><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" /><circle cx="9" cy="7" r="4" /><path d="M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75" /></>,
  model: <><path d="M4 19V9M10 19V5M16 19v-7M22 19V3" /><path d="M2 21h22" /></>,
  settings: <><path d="M4 6h10M18 6h2M4 12h2M10 12h10M4 18h6M14 18h6" /><circle cx="16" cy="6" r="2" /><circle cx="8" cy="12" r="2" /><circle cx="12" cy="18" r="2" /></>,
  activity: <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>,
}

function NavIcon({ name }) {
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{ICON_PATHS[name] || ICON_PATHS.dashboard}</svg>
}

const ROLE_LABEL = {
  learner: 'Apprenant',
  trainer: 'Formateur',
  administrator: 'Administrateur',
}

function initials(name = '') {
  return name
    .split(/[\s—-]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0])
    .join('')
    .toUpperCase() || '?'
}

const PAGE_TITLES = [
  [/^\/apprenant$/, 'Tableau de bord', 'Votre profil pédagogique et vos indicateurs'],
  [/^\/apprenant\/tuteur/, 'AI Tutor', 'Assistant pédagogique personnalisé'],
  [/^\/apprenant\/recommandations/, 'Recommandations', 'Ressources adaptées à votre profil'],
  [/^\/apprenant\/quiz\/copie/, 'Correction', 'Détail de votre copie'],
  [/^\/apprenant\/quiz\/\d+/, 'Passer un quiz', 'Correction automatique par le serveur'],
  [/^\/apprenant\/quiz/, 'Mes quiz', 'Quiz attribués par votre formateur'],
  [/^\/apprenant\/cours/, 'Cours', 'Lisez, validez vos acquis et poursuivez avec un quiz adapté'],
  [/^\/formateur\/quiz/, 'Quiz', 'Création, attribution et résultats'],
  [/^\/formateur\/cours/, 'Bibliothèque de cours', 'Base de connaissances de l\'AI Tutor'],
  [/^\/formateur$/, 'Tableau de bord formateur', 'Vue d\'ensemble de la promotion'],
  [/^\/formateur\/apprenants\/\d+/, 'Fiche apprenant', 'Détail, profil et recommandations'],
  [/^\/formateur\/apprenants/, 'Apprenants', 'Liste, filtres et suivi individuel'],
  [/^\/formateur\/modele/, 'Évaluation du modèle', 'Performances de l\'arbre de décision'],
  [/^\/admin$/, 'Administration', 'Vue d\'ensemble du système'],
  [/^\/admin\/utilisateurs/, 'Comptes utilisateurs', 'Gestion des apprenants, formateurs et administrateurs'],
  [/^\/admin\/activite/, 'Activité système', 'Derniers événements enregistrés'],
  [/^\/simulateur/, 'Simulateur de profil', 'Tester les modèles sur des valeurs libres'],
]

function titleFor(pathname) {
  const match = PAGE_TITLES.find(([pattern]) => pattern.test(pathname))
  return match ? { title: match[1], subtitle: match[2] } : { title: 'TEACHIUM AI Tutor', subtitle: '' }
}

export default function Layout() {
  const { user, logout } = useAuth()
  const [open, setOpen] = useState(false)
  const location = useLocation()
  const { title, subtitle } = titleFor(location.pathname)

  useEffect(() => { setOpen(false) }, [location.pathname])

  useEffect(() => {
    const closeOnEscape = (event) => { if (event.key === 'Escape') setOpen(false) }
    window.addEventListener('keydown', closeOnEscape)
    return () => window.removeEventListener('keydown', closeOnEscape)
  }, [])

  const items = NAV[user?.role] || []

  return (
    <div className="app-shell">
      <button type="button" className={`backdrop ${open ? 'show' : ''}`} onClick={() => setOpen(false)} aria-label="Fermer le menu" />

      <aside className={`sidebar ${open ? 'open' : ''}`}>
        <div className="sidebar-brand">
          <div className="brand-mark">T</div>
          <div>
            <div className="brand-name">TEACHIUM</div>
            <div className="brand-sub">AI Tutor</div>
          </div>
        </div>

        <nav className="sidebar-nav">
          {items.map((item, i) =>
            item.group ? (
              <div className="nav-group-title" key={`g-${i}`}>{item.group}</div>
            ) : (
              <NavLink key={item.to} to={item.to} end={item.end} className="nav-link">
                <span className="nav-icon"><NavIcon name={item.icon} /></span>
                {item.label}
              </NavLink>
            ),
          )}
        </nav>

        <div className="sidebar-footer">
          <div className="row" style={{ marginBottom: 10 }}>
            <div className="avatar">{initials(user?.name)}</div>
            <div style={{ minWidth: 0, flex: 1 }}>
              <div className="small" style={{ fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {user?.name}
              </div>
              <div className="small muted">{ROLE_LABEL[user?.role]}</div>
            </div>
          </div>
          <button type="button" className="btn btn-sm btn-block" onClick={logout}>Se déconnecter</button>
        </div>
      </aside>

      <div className="main-area">
        <header className="header">
          <div className="row">
            <button type="button" className="menu-toggle" onClick={() => setOpen((v) => !v)} aria-label="Ouvrir le menu" aria-expanded={open}>
              <span aria-hidden="true">☰</span>
            </button>
            <div>
              <div className="header-title">{title}</div>
              {subtitle && <div className="header-sub">{subtitle}</div>}
            </div>
          </div>
          <div className="header-right">
            <span className="role-pill"><span className="role-dot" />{ROLE_LABEL[user?.role]}</span>
          </div>
        </header>
        <main className="page">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
