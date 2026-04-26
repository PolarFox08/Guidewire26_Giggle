import { useEffect, useState } from 'react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'
import AdminLayout from '../components/AdminLayout'
import { api } from '../config/api'
import { ZONE_NAMES, STATUS_DISPLAY, ROUTING_DISPLAY } from '../config/constants'

function inr(v) { return `₹${parseFloat(v || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}` }

function KpiCard({ label, value, sub, highlight }) {
  return (
    <div className={`rounded-xl p-4 border ${highlight ? 'bg-primary-900/40 border-primary-700/50' : 'bg-gray-900 border-gray-800'}`}>
      <p className="text-xs text-gray-500 uppercase tracking-widest font-semibold mb-2">{label}</p>
      <p className={`font-heading text-2xl font-bold ${highlight ? 'text-primary-300' : 'text-gray-100'}`}>{value ?? '—'}</p>
      {sub && <p className="text-xs text-gray-600 mt-1">{sub}</p>}
    </div>
  )
}

function Section({ title, sub, children }) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
      <div className="px-5 py-4 border-b border-gray-800">
        <h2 className="font-semibold text-gray-200 text-sm">{title}</h2>
        {sub && <p className="text-xs text-gray-600 mt-0.5">{sub}</p>}
      </div>
      <div className="p-5">{children}</div>
    </div>
  )
}

function StatusPill({ ok, okLabel = 'Normal', badLabel = 'Alert' }) {
  return ok
    ? <span className="text-xs font-semibold text-green-400 bg-green-950 border border-green-900 px-2 py-0.5 rounded">{okLabel}</span>
    : <span className="text-xs font-semibold text-amber-400 bg-amber-950 border border-amber-900 px-2 py-0.5 rounded">{badLabel}</span>
}

export default function Admin() {
  const [summary, setSummary] = useState(null)
  const [lossRatio, setLossRatio] = useState([])
  const [modelHealth, setModelHealth] = useState(null)
  const [enrollment, setEnrollment] = useState(null)
  const [triggerHist, setTriggerHist] = useState([])
  const [pendingClaims, setPendingClaims] = useState([])
  const [workersList, setWorkersList] = useState([])
  const [tab, setTab] = useState('overview')
  const [loading, setLoading] = useState(true)
  const [resolveLoading, setResolveLoading] = useState(null)
  const [toast, setToast] = useState(null)
  // Simulation console state
  const [simZone, setSimZone] = useState(3)
  const [simRain, setSimRain] = useState(70)
  const [simTemp, setSimTemp] = useState(32)
  const [simSusp, setSimSusp] = useState(false)

  const fetchModelHealth = () =>
    api.get('/api/v1/admin/model-health').then(r => setModelHealth(r.data)).catch(() => {})


  useEffect(() => {
    Promise.allSettled([
      api.get('/api/v1/admin/dashboard/summary'),
      api.get('/api/v1/admin/dashboard/loss-ratio'),
      api.get('/api/v1/admin/model-health'),
      api.get('/api/v1/admin/enrollment-metrics'),
      api.get('/api/v1/trigger/history'),
      api.get('/api/v1/claims/pending'),
      api.get('/api/v1/admin/workers'),
    ]).then(([s, lr, mh, en, th, pc, wk]) => {
      if (s.value) setSummary(s.value.data)
      if (lr.value) setLossRatio(lr.value.data.items || lr.value.data || [])
      if (mh.value) setModelHealth(mh.value.data)
      if (en.value) setEnrollment(en.value.data)
      if (th.value) setTriggerHist((th.value.data.items || []).slice(0, 15))
      if (pc.value) setPendingClaims(pc.value.data.items || pc.value.data || [])
      if (wk.value) setWorkersList(wk.value.data.workers || [])
      setLoading(false)
    })
  }, [])


  const showToast = (msg, type = 'success') => {
    setToast({ msg, type })
    setTimeout(() => setToast(null), 3500)
  }

  const resolveClaim = async (claimId, resolution) => {
    setResolveLoading(claimId + resolution)
    try {
      await api.put(`/api/v1/claims/${claimId}/resolve`, { resolution })
      // Remove row immediately using string comparison to avoid UUID type mismatch
      setPendingClaims(prev => prev.filter(c => String(c.claim_id || c.id) !== String(claimId)))
      showToast(`Claim ${resolution === 'approve' ? 'approved and payout triggered' : 'rejected — worker notified'}.`, resolution === 'approve' ? 'success' : 'error')
      // Re-fetch stats so precision and counts update without page refresh
      fetchModelHealth()
      api.get('/api/v1/admin/dashboard/summary').then(r => setSummary(r.data)).catch(() => {})
    } catch (e) {
      showToast(e.response?.data?.detail || 'Action failed.', 'error')
    } finally { setResolveLoading(null) }
  }

  if (loading) return (
    <div className="min-h-screen bg-gray-950 flex items-center justify-center gap-3">
      <span className="spinner" style={{ borderTopColor: '#22c55e' }} />
      <span className="text-gray-500 text-sm">Loading admin data...</span>
    </div>
  )

  return (
    <AdminLayout activeTab={tab} onTabChange={setTab} pendingCount={pendingClaims.length}>
      {/* Toast */}
      {toast && (
        <div className={`fixed top-16 right-6 z-50 px-4 py-3 rounded-xl text-sm font-semibold shadow-xl border fade-up ${
          toast.type === 'success' ? 'bg-green-950 text-green-300 border-green-800' : 'bg-red-950 text-red-300 border-red-800'
        }`}>
          {toast.msg}
        </div>
      )}

      {/* ── OVERVIEW ── */}
      {tab === 'overview' && (
        <div className="space-y-6 fade-up">
          {/* KPIs */}
          {summary && (
            <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
              <KpiCard label="Active Policies" value={summary.active_workers} />
              <KpiCard label="Live Disruptions" value={summary.active_triggers} highlight />
              <KpiCard label="Claims This Week" value={summary.claims_this_week} />
              <KpiCard label="Payouts This Week" value={inr(summary.payouts_this_week)} />
              <div className="col-span-2 lg:col-span-1">
                <KpiCard label="UPI Mandate Coverage" value={`${summary.upi_mandate_coverage_pct ?? 0}%`}
                  sub={summary.avg_fraud_score_this_week != null ? `Avg fraud score: ${(summary.avg_fraud_score_this_week * 100).toFixed(0)}%` : undefined} />
              </div>
            </div>
          )}

          <div className="grid md:grid-cols-2 gap-4">
            {/* Loss Ratio chart */}

            <Section title="Loss Ratio by Zone" sub="Total payouts ÷ premiums collected">
              {lossRatio.length === 0
                ? <p className="text-gray-600 text-sm py-4">No loss ratio data available yet.</p>
                : (
                  <ResponsiveContainer width="100%" height={200}>
                    <BarChart data={lossRatio} margin={{ left: -20, right: 0, top: 4, bottom: 0 }}>
                      <XAxis dataKey="zone_cluster_id" tickFormatter={z => ZONE_NAMES[z]?.slice(0, 6) || `Z${z}`} tick={{ fill: '#6b7280', fontSize: 10 }} />
                      <YAxis tick={{ fill: '#6b7280', fontSize: 10 }} />
                      <Tooltip
                        contentStyle={{ background: '#111827', border: '1px solid #374151', color: '#f9fafb', borderRadius: 8, fontSize: 12 }}
                        formatter={v => [`${(v * 100).toFixed(1)}%`, 'Loss Ratio']}
                        labelFormatter={z => ZONE_NAMES[z] || `Zone ${z}`}
                      />
                      <Bar dataKey="loss_ratio" fill="#22c55e" radius={[4, 4, 0, 0]}
                        label={{ position: 'top', fill: '#6b7280', fontSize: 9, formatter: v => v > 0 ? `${(v * 100).toFixed(0)}%` : '' }} />
                    </BarChart>
                  </ResponsiveContainer>
                )}
            </Section>

            {/* Enrollment metrics */}
            {enrollment ? (
              <Section title="Enrollment Overview" sub="Last 7-day activity snapshot">
                <div className="space-y-3">
                  {[
                    ['New enrollments (7d)', enrollment.enrollments_last_7d ?? enrollment.new_this_week ?? '—'],
                    ['Lapse rate', `${((enrollment.lapse_rate ?? 0) * 100).toFixed(1)}%`],
                    ['High-risk zone fraction', `${((enrollment.high_tier_fraction ?? 0) * 100).toFixed(1)}%`],
                    ['Adverse selection', enrollment.adverse_selection_alert ? 'Alert' : 'Normal'],
                  ].map(([k, v]) => (
                    <div key={k} className="flex items-center justify-between py-2 border-b border-gray-800 last:border-0">
                      <span className="text-sm text-gray-500">{k}</span>
                      <span className={`text-sm font-semibold ${k === 'Adverse selection' && enrollment.adverse_selection_alert ? 'text-amber-400' : 'text-gray-200'}`}>{v}</span>
                    </div>
                  ))}
                </div>
              </Section>
            ) : (
              <Section title="Enrollment Overview" sub="Loading...">
                <p className="text-gray-600 text-sm">No data available.</p>
              </Section>
            )}
          </div>

          {/* ── TRIGGER SIMULATION CONSOLE ── */}
          <Section title="Trigger Simulation Console" sub="Corroborates a disruption event using the real scoring engine — payouts are initiated immediately for eligible workers">
            <div className="grid md:grid-cols-5 gap-6">
              {/* Inputs */}
              <form onSubmit={async (e) => {
                e.preventDefault();
                const btn = e.currentTarget.querySelector('button[type="submit"]');
                btn.disabled = true
                try {
                  const res = await api.post('/api/v1/trigger/simulate', {
                    zone_cluster_id: simZone,
                    rainfall_mm: simRain,
                    temp_c: simTemp,
                    aqi_value: 50,
                    platform_suspended: simSusp,
                    duration_hours: 1.0,
                  })
                  showToast(`Trigger fired — ${res.data.trigger_type?.replace(/_/g, ' ')} in ${ZONE_NAMES[simZone]}. Payouts initiated.`)
                  setTimeout(() => window.location.reload(), 1800)
                } catch (err) {
                  showToast(err.response?.data?.detail || 'Trigger failed', 'error')
                } finally { btn.disabled = false }
              }} className="md:col-span-3 space-y-5">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="space-y-1.5">
                    <label className="text-[10px] text-gray-500 uppercase font-bold tracking-widest">Zone</label>
                    <select
                      value={simZone} onChange={e => setSimZone(+e.target.value)}
                      className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white outline-none focus:border-primary-500">
                      {Object.entries(ZONE_NAMES).slice(0, 10).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                    </select>
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-[10px] text-gray-500 uppercase font-bold tracking-widest">
                      Rainfall — 24h (mm)
                      <span className="ml-1 text-gray-600 normal-case font-normal">≥64.5 triggers</span>
                    </label>
                    <input
                      type="number" min="0" step="0.1"
                      value={simRain} onChange={e => setSimRain(+e.target.value)}
                      className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white outline-none focus:border-primary-500"
                    />
                    <div className="flex flex-wrap gap-1 mt-1">
                      {[[65, 'Heavy'], [116, 'V.Heavy'], [205, 'Extreme']].map(([v, l]) => (
                        <button type="button" key={v} onClick={() => setSimRain(v)}
                          className={`text-[9px] px-1.5 py-0.5 rounded font-bold border transition-colors ${simRain >= v ? 'bg-primary-900 border-primary-700 text-primary-300' : 'bg-gray-800 border-gray-700 text-gray-500 hover:text-gray-300'}`}>
                          {l}
                        </button>
                      ))}
                    </div>
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-[10px] text-gray-500 uppercase font-bold tracking-widest">
                      Temperature (°C)
                      <span className="ml-1 text-gray-600 normal-case font-normal">≥45°C triggers</span>
                    </label>
                    <input
                      type="number" min="20" max="50" step="1"
                      value={simTemp} onChange={e => setSimTemp(+e.target.value)}
                      className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white outline-none focus:border-primary-500"
                    />
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-[10px] text-gray-500 uppercase font-bold tracking-widest">Platform Outage</label>
                    <button type="button" onClick={() => setSimSusp(p => !p)}
                      className={`w-full py-2 rounded-lg text-xs font-bold border transition-all ${simSusp ? 'bg-red-950 border-red-700 text-red-300' : 'bg-gray-800 border-gray-700 text-gray-500 hover:text-gray-300'}`}>
                      {simSusp ? 'Suspended (+0.40 score)' : 'Platform Running — click to suspend'}
                    </button>
                  </div>
                </div>

                {/* Live composite score preview */}
                <div className="p-3 bg-gray-800/60 rounded-lg border border-gray-700 text-xs text-gray-400 flex items-center gap-3">
                  <span>Score preview:</span>
                  {(() => {
                    let s = 0
                    if (simRain >= 64.5) s += 0.35
                    if (simRain >= 64.5) s += 0.15
                    if (simSusp) s += 0.40
                    if (simTemp >= 45) s += 0.10
                    s = Math.min(1, s)
                    return (
                      <span className={`font-bold text-sm ${s > 0.9 ? 'text-green-400' : s >= 0.5 ? 'text-amber-400' : 'text-red-400'}`}>
                        {(s * 100).toFixed(0)}% — {s > 0.9 ? 'Fast Path ✓' : s >= 0.5 ? 'Corroborated ✓' : 'Below threshold ✗'}
                      </span>
                    )
                  })()}
                </div>

                <button
                  type="submit"
                  className="px-5 py-2.5 bg-primary-600 hover:bg-primary-500 text-white rounded-lg text-sm font-bold transition-all shadow-lg shadow-primary-900/30 disabled:opacity-40">
                  Fire Trigger &amp; Initiate Payouts
                </button>
              </form>

              {/* What to check after firing */}
              <div className="md:col-span-2 border-l border-gray-800 md:pl-6 space-y-4">
                <p className="text-xs font-bold text-gray-400 uppercase tracking-widest pt-4 md:pt-0">What happens after firing</p>
                <div className="space-y-3 text-xs text-gray-500">
                  {[
                    ['Overview → Live Disruptions', 'Count increases by 1 for the zone'],
                    ['Triggers tab', 'New row appears with a real composite score (not 100%)'],
                    ['Claims Review tab', 'Claims created for eligible workers (≥28d enrolled). High fraud-score ones land here for manual review.'],
                    ['System Health → Precision', 'Reject a flagged claim and precision updates instantly — no page refresh needed'],
                  ].map(([title, desc]) => (
                    <div key={title} className="flex gap-2.5">
                      <span className="w-1.5 h-1.5 rounded-full bg-primary-600 mt-1.5 shrink-0" />
                      <div>
                        <p className="text-gray-300 font-semibold">{title}</p>
                        <p>{desc}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </Section>
        </div>
      )}

      {/* ── WORKERS ── */}



      {tab === 'workers' && (
        <Section title="Enrolled Workers" sub={`${workersList.length} workers in the system`}>
          {workersList.length === 0
            ? <p className="text-gray-600 text-sm py-4">No workers found.</p>
            : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-gray-800">
                      {['Worker ID', 'Platform', 'Partner ID', 'Pincode', 'Zone', 'Language', 'Status'].map(h => (
                        <th key={h} className="pb-3 pr-4 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-800/50">
                    {workersList.map(w => (
                      <tr key={w.id} className="hover:bg-gray-800/30 transition-colors">
                        <td className="py-3 pr-4 font-mono text-xs text-gray-500">{String(w.id).slice(0, 8)}…</td>
                        <td className="py-3 pr-4 text-gray-300 capitalize">{w.platform}</td>
                        <td className="py-3 pr-4 font-mono text-xs text-gray-300">{w.partner_id}</td>
                        <td className="py-3 pr-4 text-gray-400">{w.pincode}</td>
                        <td className="py-3 pr-4 text-gray-400 text-xs">{ZONE_NAMES[w.zone_cluster_id] || `Zone ${w.zone_cluster_id}`}</td>
                        <td className="py-3 pr-4 text-gray-400 uppercase text-xs">{w.language_preference}</td>
                        <td className="py-3 pr-4">
                          <span className={`text-xs font-semibold px-2 py-0.5 rounded border ${
                            w.policy_status === 'active' 
                              ? 'bg-green-950 text-green-400 border-green-900' 
                              : 'bg-gray-800 text-gray-500 border-gray-700'
                          }`}>
                            {STATUS_DISPLAY[w.policy_status]?.en || w.policy_status || 'unknown'}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
        </Section>
      )}

      {/* ── TRIGGERS ── */}
      {tab === 'triggers' && (
        <Section title="Recent Trigger Events" sub="Last 15 trigger events across all zones">
          {triggerHist.length === 0
            ? <p className="text-gray-600 text-sm py-4">No trigger events recorded.</p>
            : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-gray-800">
                      {['Zone', 'Trigger Type', 'Composite Score', 'Sources', 'Payouts', 'Status', 'Date'].map(h => (
                        <th key={h} className="pb-3 pr-4 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-800/50">
                    {triggerHist.map(t => (
                      <tr key={t.trigger_event_id} className="hover:bg-gray-800/30 transition-colors">
                        <td className="py-3 pr-4 text-gray-200 font-medium">{ZONE_NAMES[t.zone_cluster_id] || `Zone ${t.zone_cluster_id}`}</td>
                        <td className="py-3 pr-4 text-gray-400">
                          {(t.trigger_type || '').replace(/_/g, ' ').replace(/\baqi\b/gi, 'AQI').replace(/\b\w/g, l => l.toUpperCase())}
                        </td>
                        <td className="py-3 pr-4">
                          <span className={`font-bold text-sm ${parseFloat(t.composite_score) > 0.7 ? 'text-red-400' : 'text-amber-400'}`}>
                            {(parseFloat(t.composite_score || 0) * 100).toFixed(0)}%
                          </span>
                        </td>
                        <td className="py-3 pr-4 text-gray-400">{t.sources_confirmed}</td>
                        <td className="py-3 pr-4 text-gray-300">{t.payout_count ?? '—'}</td>
                        <td className="py-3 pr-4">
                          <span className={`text-xs font-semibold px-2 py-0.5 rounded border ${
                            t.status === 'active' 
                              ? 'bg-green-950 text-green-400 border-green-900' 
                              : 'bg-gray-800 text-gray-500 border-gray-700'
                          }`}>
                            {t.status?.charAt(0).toUpperCase() + t.status?.slice(1)}
                          </span>
                        </td>
                        <td className="py-3 text-gray-600 text-xs font-mono">
                          {t.triggered_at ? new Date(t.triggered_at + (t.triggered_at.includes('Z') ? '' : 'Z')).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', timeZone: 'Asia/Kolkata' }) : '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
        </Section>
      )}

      {/* ── CLAIMS REVIEW ── */}
      {tab === 'claims' && (
        <Section title="Claims Pending Human Review" sub="These claims were flagged by the fraud engine and require manual approval.">
          {pendingClaims.length === 0 ? (
            <div className="text-center py-12">
              <div className="w-12 h-12 rounded-full bg-green-950 border border-green-900 flex items-center justify-center mx-auto mb-3">
                <svg className="w-6 h-6 text-green-400" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
                  <path d="M2 8l4 4 8-8"/>
                </svg>
              </div>
              <p className="text-gray-400 font-semibold">All clear — no claims pending review</p>
              <p className="text-gray-600 text-xs mt-1">The fraud engine auto-approved all recent claims.</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-800">
                    {['Claim ID', 'Worker', 'Fraud Score', 'Routing', 'Zone Match', 'Action'].map(h => (
                      <th key={h} className="pb-3 pr-4 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-800/50">
                  {pendingClaims.map(c => {
                    const cid = c.claim_id || c.id
                    const sc = parseFloat(c.fraud_score || 0)
                    const loading = resolveLoading
                    return (
                      <tr key={cid} className="hover:bg-gray-800/30 transition-colors">
                        <td className="py-3 pr-4 font-mono text-xs text-gray-500" title={String(cid)}>
                          {String(cid).slice(-12).toUpperCase()}
                        </td>
                        <td className="py-3 pr-4 font-mono text-xs text-gray-400" title={String(c.worker_id)}>
                          {String(c.worker_id).slice(-8).toUpperCase()}
                        </td>
                        <td className="py-3 pr-4">
                          <span className={`font-bold ${sc < .3 ? 'text-green-400' : sc < .7 ? 'text-amber-400' : 'text-red-400'}`}>
                            {(sc * 100).toFixed(0)}%
                          </span>
                        </td>
                        <td className="py-3 pr-4 text-xs text-gray-500">
                          {ROUTING_DISPLAY[c.fraud_routing]?.en || c.fraud_routing}
                        </td>
                        <td className="py-3 pr-4">
                          <span className={`text-xs font-semibold ${c.zone_claim_match ? 'text-green-400' : c.zone_claim_match === false ? 'text-red-400' : 'text-gray-500'}`}>
                            {c.zone_claim_match ? 'Matched' : c.zone_claim_match === false ? 'Mismatch' : 'Unknown'}
                          </span>
                        </td>
                        <td className="py-3">
                          <div className="flex gap-2">
                            <button
                              onClick={() => resolveClaim(cid, 'approve')}
                              disabled={!!loading}
                              className="px-3 py-1.5 bg-primary-900/60 hover:bg-primary-800 text-primary-300 border border-primary-700 text-xs rounded-lg font-semibold transition-all disabled:opacity-40">
                              {loading === cid + 'approve' ? '…' : 'Approve'}
                            </button>
                            <button
                              onClick={() => resolveClaim(cid, 'reject')}
                              disabled={!!loading}
                              className="px-3 py-1.5 bg-red-950/60 hover:bg-red-900 text-red-400 border border-red-800 text-xs rounded-lg font-semibold transition-all disabled:opacity-40">
                              {loading === cid + 'reject' ? '…' : 'Reject'}
                            </button>
                          </div>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </Section>
      )}

      {/* ── SYSTEM HEALTH ── */}
      {tab === 'model' && (
        <div className="grid md:grid-cols-2 gap-4 fade-up">
          {/* Fraud model */}
          <Section title="Fraud Detection Model" sub="Ensemble: Isolation Forest + CBLOF scoring engine">
            {modelHealth ? (
              <div className="space-y-3">
                <div className="flex items-center justify-between py-2 border-b border-gray-800">
                  <div>
                    <p className="text-sm text-gray-300 font-medium">Model precision</p>
                    <p className="text-xs text-gray-600 mt-0.5">Correct fraud flags ÷ total flags</p>
                  </div>
                  <span className="text-lg font-bold text-gray-200">
                    {modelHealth.fraud_precision != null ? `${(modelHealth.fraud_precision * 100).toFixed(1)}%` : '—'}
                  </span>
                </div>
                <div className="flex items-center justify-between py-2 border-b border-gray-800">
                  <div>
                    <p className="text-sm text-gray-300 font-medium">Baseline drift</p>
                    <p className="text-xs text-gray-600 mt-0.5">Model performance degradation vs. training set</p>
                  </div>
                  <StatusPill ok={!modelHealth.baseline_drift_alert} okLabel="Stable" badLabel="Drift Detected" />
                </div>
                <div className="flex items-center justify-between py-2">
                  <div>
                    <p className="text-sm text-gray-300 font-medium">Adverse selection</p>
                    <p className="text-xs text-gray-600 mt-0.5">High-risk workers enrolling at higher rates than expected</p>
                  </div>
                  <StatusPill ok={!modelHealth.adverse_selection_alert} okLabel="Normal" badLabel="Alert" />
                </div>
              </div>
            ) : <p className="text-gray-600 text-sm">Model health data unavailable.</p>}
          </Section>

          {/* Zone slab rates */}
          <Section title="Zone Rate Configuration" sub="Per-order earnings rate used for payout calculations">
            {modelHealth?.slabs || modelHealth ? (
              <div className="space-y-3">
                <div className="flex items-center justify-between py-2 border-b border-gray-800">
                  <div>
                    <p className="text-sm text-gray-300 font-medium">Slab config age</p>
                    <p className="text-xs text-gray-600 mt-0.5">Days since zone rates were last verified with market data</p>
                  </div>
                  <span className={`text-sm font-bold ${(modelHealth.oldest_slab_verified_days ?? 0) > 30 ? 'text-amber-400' : 'text-gray-200'}`}>
                    {modelHealth.oldest_slab_verified_days ?? 0}d ago
                  </span>
                </div>
                <div className="flex items-center justify-between py-2">
                  <div>
                    <p className="text-sm text-gray-300 font-medium">Config freshness</p>
                    <p className="text-xs text-gray-600 mt-0.5">Rates should be re-verified every 30 days to stay accurate</p>
                  </div>
                  <StatusPill ok={!modelHealth.slab_config_stale} okLabel="Fresh" badLabel="Stale — update needed" />
                </div>
                <div className="mt-4 p-3 rounded-lg bg-gray-800/50 border border-gray-700">
                  <p className="text-xs text-gray-500">Zone rates are the per-order earnings used in Base Loss calculations. If stale, payouts may under or over-compensate workers. Contact your data team to re-verify.</p>
                </div>
              </div>
            ) : <p className="text-gray-600 text-sm">Zone rate config data unavailable.</p>}
          </Section>
        </div>
      )}
    </AdminLayout>
  )
}
