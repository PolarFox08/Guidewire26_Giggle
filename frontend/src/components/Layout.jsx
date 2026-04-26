/**
 * User Dashboard Layout
 * Used only for worker-facing pages: Dashboard, Profile, etc.
 * Admin has its own AdminLayout.
 */
import { Link, useNavigate, useLocation } from 'react-router-dom'
import { useTranslation } from '../../node_modules/react-i18next'
import { useState, useEffect } from 'react'
import { api } from '../config/api'
import { getAuth, clearAuth, clearAdmin, setAuth } from '../hooks/useAuth'
import i18n from 'i18next'

export default function Layout({ children }) {
  const { t } = useTranslation()
  const nav = useNavigate()
  const loc = useLocation()
  const auth = getAuth()
  const [health, setHealth] = useState(null)
  const [lang, setLang] = useState(i18n.language || 'ta')

  useEffect(() => {
    api.get('/api/v1/health').then(r => setHealth(r.data)).catch(() => setHealth(null))
  }, [])

  const onLogout = () => { clearAuth(); clearAdmin(); nav('/') }

  const changeLang = async (l) => {
    setLang(l)
    i18n.changeLanguage(l)
    if (auth?.worker_id) {
      try {
        await api.patch(`/api/v1/onboarding/${auth.worker_id}/language`, { language_preference: l })
        setAuth({ ...auth, language_preference: l })
      } catch { }
    }
  }

  const isOk = health?.database === 'ok' || health?.database === 'connected'

  const name = auth?.label ? auth.label.split('—')[0].trim() : (auth?.platform?.toUpperCase() + ' Worker')
  const initials = name.split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase()

  return (
    <div className="min-h-screen bg-surface">
      <nav className="sticky top-0 z-50 bg-primary-900 shadow-md border-b border-primary-800 backdrop-blur-xl">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center gap-4">

          {/* Logo */}
          <Link to="/" className="flex items-center gap-2 shrink-0">
            <span className="font-heading font-bold text-xl text-white tracking-wide">Giggle</span>
          </Link>

          {/* ── Left-side utility bar ── */}
          <div className="flex items-center gap-2 md:gap-3 ml-0 md:ml-2">
            {/* Live status */}
            <span className="flex items-center gap-1.5 text-[10px] md:text-xs text-white/70 font-medium bg-white/5 px-2 md:px-2.5 py-1 rounded-full border border-white/10">
              <span className={`w-1.5 h-1.5 rounded-full ${isOk ? 'bg-green-400 pulse-dot' : health ? 'bg-red-400' : 'bg-gray-500'}`} />
              <span className="hidden xs:inline">{isOk ? t('common.live', 'Live') : health ? t('common.degraded', 'Degraded') : '...'}</span>
            </span>

            {/* Lang switcher */}
            <div className="flex gap-0.5 text-[10px] md:text-xs font-semibold rounded-lg overflow-hidden border border-white/20 bg-black/20">
              {['ta', 'hi', 'en'].map(l => (
                <button key={l} onClick={() => changeLang(l)}
                  className={`px-1.5 md:px-2.5 py-1 md:py-1.5 transition-colors ${lang === l
                    ? 'bg-white/20 text-white'
                    : 'text-white/50 hover:text-white hover:bg-white/10'
                    }`}>
                  {l === 'ta' ? 'த' : l === 'hi' ? 'हि' : 'En'}
                </button>
              ))}
            </div>
          </div>

          {/* Back button for sub-pages */}
          {loc.pathname !== '/dashboard' && loc.pathname !== '/' && (
            <button onClick={() => nav(-1)}
              className="text-[10px] md:text-xs font-medium px-2 md:px-3 py-1 md:py-1.5 rounded-lg border border-white/20 text-white/70 hover:bg-white/10 hover:text-white transition-colors">
              ← <span className="hidden xs:inline">{t('common.back', 'Back')}</span>
            </button>
          )}

          {/* ── Right: user avatar only ── */}
          {auth && (
            <div className="relative group ml-auto">
              <button className="flex items-center gap-1 md:gap-2 rounded-xl px-1.5 md:px-2 py-1 md:py-1.5 bg-white/10 hover:bg-white/20 transition-colors border border-white/20">
                <span className="w-7 h-7 rounded-lg bg-white/25 flex items-center justify-center text-xs font-bold text-white">{initials}</span>
                <span className="text-xs font-semibold text-white/90 hidden md:block max-w-[80px] truncate">{name.split(' ')[0]}</span>
                <svg className="w-3 h-3 text-white/40" viewBox="0 0 12 12" fill="currentColor">
                  <path d="M6 8L1 3h10L6 8z" />
                </svg>
              </button>
              {/* Dropdown */}
              <div className="absolute right-0 top-full mt-2 w-52 bg-white rounded-2xl shadow-xl border border-gray-100 py-1.5 opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-150 z-50">
                <div className="px-4 py-3 border-b border-gray-100">
                  <p className="text-xs font-bold text-gray-900 truncate">{name}</p>
                  <p className="text-xs text-gray-400 capitalize">{auth.platform} · Rider</p>
                </div>
                <Link to="/profile" className="flex items-center gap-3 px-4 py-2.5 text-sm text-gray-700 hover:bg-gray-50 transition-colors">
                  <svg className="w-4 h-4 text-gray-400 shrink-0" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
                    <circle cx="8" cy="5" r="3" /><path d="M2 14c0-3.3 2.7-6 6-6s6 2.7 6 6" />
                  </svg>
                  {t('nav.profile', 'My Profile')}
                </Link>
                <Link to="/dashboard" className="flex items-center gap-3 px-4 py-2.5 text-sm text-gray-700 hover:bg-gray-50 transition-colors">
                  <svg className="w-4 h-4 text-gray-400 shrink-0" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
                    <rect x="1" y="1" width="6" height="6" rx="1" /><rect x="9" y="1" width="6" height="6" rx="1" /><rect x="1" y="9" width="6" height="6" rx="1" /><rect x="9" y="9" width="6" height="6" rx="1" />
                  </svg>
                  {t('nav.dashboard', 'Dashboard')}
                </Link>
                <div className="border-t border-gray-100 mt-1 pt-1">
                  <button onClick={onLogout} className="flex items-center gap-3 w-full px-4 py-2.5 text-sm text-red-500 hover:bg-red-50 transition-colors">
                    <svg className="w-4 h-4 shrink-0" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
                      <path d="M6 14H3a1 1 0 01-1-1V3a1 1 0 011-1h3M11 11l3-3-3-3M14 8H6" />
                    </svg>
                    {t('nav.logout', 'Sign Out')}
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      </nav>

      <main className="max-w-7xl mx-auto px-6 py-8">
        {children}
      </main>
    </div>
  )
}
