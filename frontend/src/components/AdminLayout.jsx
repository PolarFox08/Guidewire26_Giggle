/**
 * Admin Dashboard Layout
 * Completely separate from the user Layout. 
 * No language switcher, no Live pill, no avatar dropdown.
 * Purpose-built for the Giggle operations team.
 */
import { Link, useNavigate, useLocation } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { api } from '../config/api'
import { clearAuth, clearAdmin } from '../hooks/useAuth'

const NAV_ITEMS = [
  { to: '#overview', label: 'Overview', icon: <path d="M2 10h5V2H2v8zm0 4h5v-3H2v3zm6 0h6v-8h-6v8zm0-12v3h6V2h-6z" fill="currentColor" /> },
  { to: '#workers', label: 'Workers', icon: <><circle cx="6" cy="5" r="3" fill="currentColor" /><path d="M1 14c0-3.3 2.7-5 5-5s5 1.7 5 5" fill="currentColor" /><circle cx="12" cy="5" r="2.5" fill="currentColor" /><path d="M11 14c0-2.2 1.3-4 3-4" fill="currentColor" /></> },
  { to: '#triggers', label: 'Triggers', icon: <><path d="M8 1L9.8 4.7 14 5.5l-3 2.9.7 4.1L8 10.4l-3.7 2.1.7-4.1-3-2.9 4.2-.8z" fill="currentColor" /></> },
  { to: '#claims', label: 'Claims Review', icon: <><rect x="2" y="2" width="12" height="12" rx="2" fill="none" stroke="currentColor" strokeWidth="1.5" /><path d="M5 8l2 2 4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" /></> },
  { to: '#model', label: 'Model Health', icon: <><path d="M2 12l4-4 3 3 5-7" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" fill="none" /></> },
]

export default function AdminLayout({ children, activeTab, onTabChange, pendingCount = 0 }) {
  const nav = useNavigate()
  const [health, setHealth] = useState(null)
  const [time, setTime] = useState(new Date())

  useEffect(() => {
    api.get('/api/v1/health').then(r => setHealth(r.data)).catch(() => setHealth(null))
    const t = setInterval(() => setTime(new Date()), 60000)
    return () => clearInterval(t)
  }, [])

  const onLogout = () => { clearAuth(); clearAdmin(); nav('/login?role=admin') }

  const isOk = health?.database === 'ok' || health?.database === 'connected'
  const dbStatus = health?.database || 'checking'

  const tabs = [
    { id: 'overview', label: 'Overview' },
    { id: 'workers', label: 'Workers' },
    { id: 'triggers', label: 'Triggers' },
    { id: 'claims', label: `Claims Review${pendingCount > 0 ? ` (${pendingCount})` : ''}` },
    { id: 'model', label: 'System Health' },
  ]

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 flex flex-col">

      {/* ── Top Header Bar ── */}
      <header className="bg-gray-900 border-b border-gray-800 min-h-14 flex flex-col md:flex-row items-center px-6 py-2 md:py-0 shrink-0 gap-4">
        <div className="flex items-center justify-between w-full md:w-auto gap-3">
          {/* Logo mark */}
          <Link to="/" className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-md bg-primary-600 flex items-center justify-center">
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                <path d="M7 1L13 4.5V9.5L7 13L1 9.5V4.5L7 1Z" fill="white" opacity="0.9" />
                <circle cx="7" cy="7" r="2" fill="#4ade80" />
              </svg>
            </div>
            <span className="font-heading font-bold text-white text-base tracking-tight">Giggle</span>
          </Link>
          <span className="text-gray-600 text-xs md:text-sm font-medium">/ Admin Console</span>

          {/* Mobile Sign Out (visible only on mobile) */}
          <button onClick={onLogout} className="md:hidden text-gray-500 hover:text-red-400">
            <svg className="w-5 h-5" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
              <path d="M6 14H3a1 1 0 01-1-1V3a1 1 0 011-1h3M11 11l3-3-3-3M14 8H6" />
            </svg>
          </button>
        </div>

        {/* Centre: tab navigation (Scrollable on mobile) */}
        <nav className="flex items-center gap-1 overflow-x-auto no-scrollbar w-full md:w-auto pb-1 md:pb-0">
          {tabs.map(tab => (
            <button
              key={tab.id}
              onClick={() => onTabChange(tab.id)}
              className={`px-3 md:px-4 py-1.5 rounded-lg text-xs md:text-sm font-medium transition-all whitespace-nowrap ${activeTab === tab.id
                ? 'bg-primary-900/60 text-primary-300 border border-primary-700/50'
                : 'text-gray-500 hover:text-gray-300 hover:bg-gray-800'
                }`}>
              {tab.label}
            </button>
          ))}
        </nav>

        {/* Right: system status (Desktop only or compact on mobile) */}
        <div className="hidden md:flex items-center gap-3 ml-auto">
          <div className="flex items-center gap-2 text-xs">
            <span className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md font-medium ${isOk ? 'bg-green-950 text-green-400 border border-green-900' :
              health ? 'bg-red-950 text-red-400 border border-red-900' :
                'bg-gray-800 text-gray-500 border border-gray-700'
              }`}>
              <span className={`w-1.5 h-1.5 rounded-full ${isOk ? 'bg-green-400' : 'bg-red-400'}`} />
              DB {dbStatus}
            </span>
            <span className="text-gray-600 font-mono">
              {time.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })}
            </span>
          </div>

          <div className="w-px h-4 bg-gray-700" />

          <button
            onClick={onLogout}
            className="flex items-center gap-2 text-xs text-gray-500 hover:text-red-400 font-medium transition-colors px-2 py-1.5 rounded-md hover:bg-red-950/30">
            <svg className="w-3.5 h-3.5" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
              <path d="M6 14H3a1 1 0 01-1-1V3a1 1 0 011-1h3M11 11l3-3-3-3M14 8H6" />
            </svg>
            Sign Out
          </button>
        </div>
      </header>

      {/* ── Page Content ── */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-6 py-6">
        {children}
      </main>
    </div>
  )
}
