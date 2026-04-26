import { useState } from 'react'
import { useNavigate, useSearchParams, Link } from 'react-router-dom'
import { api } from '../config/api'
import { setAuth, setAdmin } from '../hooks/useAuth'
import { DEMO_ACCOUNTS } from '../config/constants'
import i18n from 'i18next'

export default function Login() {
  const nav = useNavigate()
  const [params] = useSearchParams()
  const isAdminMode = params.get('role') === 'admin'

  const [workerId, setWorkerId] = useState('')
  const [password, setPassword] = useState('')
  const [adminUser, setAdminUser] = useState('')
  const [adminPass, setAdminPass] = useState('')
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState('')

  const loginWorker = async (wid) => {
    setLoading(true); setErr('')
    try {
      const { data } = await api.get(`/api/v1/onboarding/status/${wid}`)
      setAuth({
        worker_id: wid,
        policy_status: data.policy_status,
        zone_cluster_id: null,
        language_preference: 'ta',
      })
      i18n.changeLanguage('ta')
      nav('/dashboard')
    } catch {
      setErr('Worker not found. Check the ID.')
    } finally { setLoading(false) }
  }

  const loginDemo = async (acc) => {
    setLoading(true); setErr('')
    try {
      const { data } = await api.get(`/api/v1/onboarding/by-partner/${acc.partner_id}`)
      const wid = data.worker_id
      const status = await api.get(`/api/v1/onboarding/status/${wid}`)
      setAuth({
        worker_id: wid,
        policy_status: status.data.policy_status,
        platform: acc.platform,
        language_preference: acc.lang,
        label: acc.label,
      })
      i18n.changeLanguage(acc.lang)
      nav('/dashboard')
    } catch {
      setErr(`Demo account ${acc.partner_id} not found. Run seed_demo_data.py first.`)
    } finally { setLoading(false) }
  }

  const loginAdmin = () => {
    if (adminUser === 'admin' && adminPass === 'admin') {
      setAdmin(); nav('/admin')
    } else {
      setErr('Invalid admin credentials')
    }
  }

  return (
    <div className="min-h-screen bg-surface flex items-center justify-center px-4">
      <div className="w-full max-w-md fade-up">
        <Link to="/" className="flex items-center gap-2 justify-center mb-8">
                    <span className="font-heading font-bold text-xl text-primary-900">Giggle</span>
        </Link>

        {!isAdminMode ? (
          <>
            <form onSubmit={(e) => { e.preventDefault(); if (workerId) loginWorker(workerId) }} className="card mb-4">
              <h1 className="font-heading font-bold text-xl text-primary-900 mb-1">Worker Sign In</h1>
              <p className="text-sm text-gray-500 mb-5">Enter your Worker ID to access your dashboard</p>
              <label className="label">Worker ID</label>
              <input id="worker-id-input" className="input-field mb-4" value={workerId}
                onChange={e => setWorkerId(e.target.value)}
                placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" />
              <label className="label">Password (demo — any value)</label>
              <input className="input-field mb-5" type="password" value={password}
                onChange={e => setPassword(e.target.value)} placeholder="••••••" />
              {err && <p className="text-red-500 text-sm mb-3">{err}</p>}
              <button type="submit" className="btn-primary w-full" disabled={loading || !workerId}>
                {loading ? <span className="spinner" /> : 'Sign In'}
              </button>
            </form>

            {/* Demo accounts */}
            <div className="card">
              <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-3">Quick Demo Login</p>
              <div className="flex flex-col gap-2">
                {DEMO_ACCOUNTS.map(acc => (
                  <button key={acc.partner_id} id={`demo-${acc.partner_id}`}
                    onClick={() => loginDemo(acc)} disabled={loading}
                    className="text-left px-4 py-3 rounded-xl border border-gray-200 hover:border-primary-300 hover:bg-primary-50 transition-all text-sm">
                    <span className="font-medium text-primary-900">{acc.label}</span>
                    <span className="ml-2 text-xs text-gray-400">{acc.partner_id}</span>
                  </button>
                ))}
              </div>
            </div>
          </>
        ) : (
          <form onSubmit={(e) => { e.preventDefault(); loginAdmin() }} className="card">
            <h1 className="font-heading font-bold text-xl text-primary-900 mb-5">Admin Login</h1>
            <label className="label">Username</label>
            <input className="input-field mb-3" value={adminUser} onChange={e => setAdminUser(e.target.value)} placeholder="admin" />
            <label className="label">Password</label>
            <input className="input-field mb-5" type="password" value={adminPass} onChange={e => setAdminPass(e.target.value)} placeholder="admin" />
            {err && <p className="text-red-500 text-sm mb-3">{err}</p>}
            <button type="submit" className="btn-primary w-full">Enter Admin Dashboard</button>
            <p className="text-xs text-center text-gray-400 mt-3">Default: admin / admin</p>
          </form>
        )}

        <p className="text-center text-sm text-gray-500 mt-6">
          No account? <Link to="/register" className="text-primary-700 font-medium hover:underline">Register here</Link>
          {!isAdminMode && <span> · <Link to="/login?role=admin" className="text-gray-400 hover:text-gray-600">Admin</Link></span>}
        </p>
      </div>
    </div>
  )
}
