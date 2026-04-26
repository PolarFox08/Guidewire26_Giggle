import { useEffect, useState } from 'react'
import { useTranslation } from '../../node_modules/react-i18next'
import { Link } from 'react-router-dom'
import Layout from '../components/Layout'
import { api } from '../config/api'
import { getAuth } from '../hooks/useAuth'

const ZONE_NAMES = {
  1: 'North Chennai', 2: 'Perambur', 3: 'T. Nagar', 4: 'Anna Nagar',
  5: 'Adyar', 6: 'Kodambakkam', 7: 'Velachery', 8: 'Mylapore',
  9: 'Tambaram', 10: 'Porur', 11: 'Chromepet', 12: 'Ambattur',
}

const TIER_COLOR = { high: 'text-red-600 bg-red-50', medium: 'text-amber-600 bg-amber-50', low: 'text-green-600 bg-green-50' }
const PLATFORM_LOGO = { zomato: '🍱', swiggy: '🛵', porter: '📦', dunzo: '🛍️' }

function InfoRow({ label, value, children }) {
  return (
    <div className="flex items-center justify-between py-3.5 border-b border-gray-50 last:border-0">
      <span className="text-sm text-gray-500 font-medium">{label}</span>
      <span className="text-sm text-gray-900 font-semibold text-right">{children || value || '—'}</span>
    </div>
  )
}

export default function Profile() {
  const { t } = useTranslation()
  const auth = getAuth()
  const wid = auth?.worker_id

  const [profile, setProfile] = useState(null)
  const [loading, setLoading] = useState(true)
  const [editing, setEditing] = useState(false)
  const [saving, setSaving] = useState(false)
  const [saveMsg, setSaveMsg] = useState(null)

  const [form, setForm] = useState({ upi_vpa: '', language_preference: 'ta', pincode: '' })

  useEffect(() => {
    if (!wid) return
    api.get(`/api/v1/worker/${wid}`)
      .then(r => {
        setProfile(r.data)
        setForm({
          upi_vpa: r.data.upi_vpa || '',
          language_preference: r.data.language_preference || 'ta',
          pincode: String(r.data.pincode || ''),
        })
      })
      .catch(() => { })
      .finally(() => setLoading(false))
  }, [wid])

  const handleSave = async () => {
    setSaving(true)
    setSaveMsg(null)
    try {
      const { data } = await api.patch(`/api/v1/worker/${wid}`, {
        upi_vpa: form.upi_vpa,
        language_preference: form.language_preference,
        pincode: parseInt(form.pincode) || undefined,
      })
      setProfile(data)
      setEditing(false)
      setSaveMsg({ type: 'success', text: 'Profile updated successfully!' })
      setTimeout(() => setSaveMsg(null), 4000)
    } catch (e) {
      setSaveMsg({ type: 'error', text: e.response?.data?.detail || 'Update failed.' })
    } finally {
      setSaving(false)
    }
  }

  if (loading) return (
    <Layout>
      <div className="flex items-center justify-center h-64 gap-3">
        <span className="spinner" /> <span className="text-gray-500">Loading profile...</span>
      </div>
    </Layout>
  )

  if (!profile) return (
    <Layout>
      <div className="card text-center py-16">
        <p className="text-gray-400">Profile not found. Please log in again.</p>
        <Link to="/login" className="btn-primary mt-4 inline-block">Go to Login</Link>
      </div>
    </Layout>
  )

  const workerName = auth?.label ? auth.label.split('—')[0].trim() : (profile.platform?.toUpperCase() + ' Worker')
  const enrollDate = new Date(profile.enrollment_date + (profile.enrollment_date.includes('Z') ? '' : 'Z')).toLocaleDateString('en-IN', { day: 'numeric', month: 'long', year: 'numeric', timeZone: 'Asia/Kolkata' })
  const initials = workerName.split(' ').map(n => n[0]).join('').slice(0, 2).toUpperCase()

  return (
    <Layout>
      <div className="max-w-2xl mx-auto">

        {/* Hero Card */}
        <div className="card mb-6 fade-up bg-gradient-to-br from-primary-900 to-primary-700 text-white border-0">
          <div className="flex items-center gap-5">
            <div className="w-16 h-16 rounded-2xl bg-white/20 flex items-center justify-center text-2xl font-bold font-heading text-white backdrop-blur-sm shrink-0">
              {initials}
            </div>
            <div className="flex-1 min-w-0">
              <h1 className="text-xl font-bold font-heading truncate">{workerName}</h1>
              <div className="flex flex-wrap gap-2 mt-1.5">
                <span className="text-xs bg-white/15 px-2.5 py-1 rounded-full font-medium">
                  {PLATFORM_LOGO[profile.platform]} {profile.platform?.charAt(0).toUpperCase() + profile.platform?.slice(1)} Rider
                </span>
                <span className="text-xs bg-white/15 px-2.5 py-1 rounded-full font-medium">
                  {profile.zone_name || `Zone ${profile.zone_cluster_id}`}
                </span>
                <span className={`text-xs px-2.5 py-1 rounded-full font-medium ${profile.is_active ? 'bg-green-400/20 text-green-200' : 'bg-red-400/20 text-red-200'
                  }`}>
                  {profile.is_active ? '● Active' : '● Inactive'}
                </span>
              </div>
            </div>
            {!editing && (
              <button
                onClick={() => setEditing(true)}
                className="shrink-0 px-4 py-2 rounded-xl bg-white/15 hover:bg-white/25 text-white text-sm font-semibold transition-colors border border-white/20"
              >
                Edit
              </button>
            )}
          </div>
        </div>

        {/* Save message */}
        {saveMsg && (
          <div className={`mb-4 px-4 py-3 rounded-xl text-sm font-medium fade-up border ${saveMsg.type === 'success'
              ? 'bg-green-50 border-green-200 text-green-800'
              : 'bg-red-50 border-red-200 text-red-800'
            }`}>
            {saveMsg.text}
          </div>
        )}

        {/* Identity & Account */}
        <div className="card mb-4 fade-up">
          <h2 className="font-heading font-semibold text-primary-900 mb-1 text-base">Identity & Account</h2>
          <p className="text-xs text-gray-400 mb-4">These details are verified and cannot be changed.</p>
          <InfoRow label="Worker ID" value={String(profile.worker_id).slice(-12).toUpperCase()} />
          <InfoRow label="Platform ID" value={profile.partner_id} />
          <InfoRow label="Platform" value={`${PLATFORM_LOGO[profile.platform] || ''} ${profile.platform?.charAt(0).toUpperCase() + profile.platform?.slice(1)}`} />
          <InfoRow label="Enrolled On" value={enrollDate} />
          <InfoRow label="Coverage Weeks" value={`Week #${profile.enrollment_week}`} />
          <InfoRow label="Flood Risk Zone">
            <span className={`text-xs font-bold px-2.5 py-1 rounded-full ${TIER_COLOR[profile.flood_hazard_tier] || 'bg-gray-100 text-gray-600'}`}>
              {profile.flood_hazard_tier?.toUpperCase()} RISK
            </span>
          </InfoRow>
          <InfoRow label="Zone" value={`${profile.zone_name} (Zone ${profile.zone_cluster_id})`} />
        </div>

        {/* Editable Settings */}
        <div className="card mb-4 fade-up">
          <div className="flex items-center justify-between mb-1">
            <h2 className="font-heading font-semibold text-primary-900 text-base">Payment & Preferences</h2>
            {editing && (
              <button onClick={() => { setEditing(false); setSaveMsg(null) }}
                className="text-xs text-gray-400 hover:text-gray-600 font-medium">
                Cancel
              </button>
            )}
          </div>
          <p className="text-xs text-gray-400 mb-4">
            {editing ? 'Edit your details below and click Save Changes.' : 'Your UPI ID is where Giggle sends your payouts.'}
          </p>

          {editing ? (
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-semibold text-gray-700 mb-1.5">UPI ID (GPay / PhonePe / Paytm)</label>
                <input
                  type="text"
                  value={form.upi_vpa}
                  onChange={e => setForm(f => ({ ...f, upi_vpa: e.target.value }))}
                  placeholder="yourname@okaxis"
                  className="input-field w-full font-mono text-sm"
                />
                <p className="text-xs text-gray-400 mt-1">This must be a valid UPI address (contains '@').</p>
              </div>
              <div>
                <label className="block text-sm font-semibold text-gray-700 mb-1.5">Preferred Language</label>
                <select
                  value={form.language_preference}
                  onChange={e => setForm(f => ({ ...f, language_preference: e.target.value }))}
                  className="input-field w-full"
                >
                  <option value="ta">Tamil (தமிழ்)</option>
                  <option value="hi">Hindi (हिंदी)</option>
                  <option value="en">English</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-semibold text-gray-700 mb-1.5">Pincode</label>
                <input
                  type="number"
                  value={form.pincode}
                  onChange={e => setForm(f => ({ ...f, pincode: e.target.value }))}
                  placeholder="600042"
                  className="input-field w-full"
                />
              </div>
              <button
                onClick={handleSave}
                disabled={saving}
                className="w-full py-3 rounded-xl bg-primary-900 hover:bg-primary-700 text-white font-bold text-sm transition-colors"
              >
                {saving ? 'Saving...' : 'Save Changes'}
              </button>
            </div>
          ) : (
            <div>
              <InfoRow label="UPI ID">
                <span className="font-mono">{profile.upi_vpa}</span>
              </InfoRow>
              <InfoRow label="Language">
                {profile.language_preference === 'ta' ? 'Tamil (தமிழ்)' : profile.language_preference === 'hi' ? 'Hindi (हिंदी)' : 'English'}
              </InfoRow>
              <InfoRow label="Pincode" value={String(profile.pincode)} />
              <InfoRow label="Mandate Status">
                <span className={`text-xs font-bold px-2.5 py-1 rounded-full ${profile.upi_mandate_active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'
                  }`}>
                  {profile.upi_mandate_active ? '● Mandate Active' : '● Not Activated'}
                </span>
              </InfoRow>
            </div>
          )}
        </div>

        {/* Back link */}
        <div className="text-center pb-8">
          <Link to="/dashboard" className="text-sm text-gray-400 hover:text-gray-600 font-medium transition-colors">
            ← Back to Dashboard
          </Link>
        </div>
      </div>
    </Layout>
  )
}
