import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { authApi, api, getToken, setToken, readError } from '../services/api'

const AuthContext = createContext(null)

/** Route d'accueil correspondant au rôle. */
export function homeRouteFor(role) {
  if (role === 'administrator') return '/admin'
  if (role === 'trainer') return '/formateur'
  return '/apprenant'
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()
  const sessionVersion = useRef(0)

  const logout = useCallback(() => {
    sessionVersion.current += 1
    setToken(null)
    setUser(null)
    setLoading(false)
    navigate('/connexion', { replace: true })
  }, [navigate])

  // Une réponse 401 du serveur termine la session côté client.
  useEffect(() => {
    const id = api.interceptors.response.use(
      (response) => response,
      (error) => {
        const url = error?.config?.url || ''
        const isLoginAttempt = url.includes('/api/auth/login') || url.includes('/api/auth/register')
        if (error?.response?.status === 401 && !isLoginAttempt) logout()
        return Promise.reject(error)
      },
    )
    return () => api.interceptors.response.eject(id)
  }, [logout])

  // Restauration de la session au chargement.
  useEffect(() => {
    let cancelled = false
    const version = sessionVersion.current
    const isCurrent = () => !cancelled && version === sessionVersion.current
    async function restore() {
      if (!getToken()) {
        setLoading(false)
        return
      }
      try {
        const { data } = await authApi.me()
        if (isCurrent()) setUser(data)
      } catch {
        if (isCurrent()) setToken(null)
      } finally {
        if (isCurrent()) setLoading(false)
      }
    }
    restore()
    return () => { cancelled = true }
  }, [])

  const login = useCallback(async (email, password) => {
    const version = ++sessionVersion.current
    try {
      const { data } = await authApi.login(email, password)
      if (version !== sessionVersion.current) return { ok: false, error: 'Connexion annulée.' }
      setToken(data.access_token)
      setUser(data.user)
      return { ok: true, user: data.user }
    } catch (error) {
      return { ok: false, error: readError(error) }
    }
  }, [])

  const register = useCallback(async (payload) => {
    const version = ++sessionVersion.current
    try {
      const { data } = await authApi.register(payload)
      if (version !== sessionVersion.current) return { ok: false, error: 'Inscription annulée.' }
      setToken(data.access_token)
      setUser(data.user)
      return { ok: true, user: data.user }
    } catch (error) {
      return { ok: false, error: readError(error) }
    }
  }, [])

  const value = useMemo(
    () => ({
      user,
      loading,
      login,
      register,
      logout,
      isLearner: user?.role === 'learner',
      isTrainer: user?.role === 'trainer',
      isAdmin: user?.role === 'administrator',
    }),
    [user, loading, login, register, logout],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth doit être utilisé à l\'intérieur de <AuthProvider>')
  return ctx
}
