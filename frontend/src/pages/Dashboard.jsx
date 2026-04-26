import { useEffect, useState } from 'react'
import { useTranslation } from '../../node_modules/react-i18next'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'
import Layout from '../components/Layout'
import { api } from '../config/api'
import { getAuth } from '../hooks/useAuth'
import { ZONE_NAMES, STATUS_DISPLAY, TIER_DISPLAY, TRIGGER_DISPLAY, ROUTING_DISPLAY } from '../config/constants'

function inr(v) { return `₹${parseFloat(v || 0).toFixed(2)}` }
function ago(dt) {
  if (!dt) return '—'
  const date = new Date(dt)
  // If no timezone in string, assume it's UTC from backend
  const utcDate = dt.toString().includes('Z') || dt.toString().includes('+') ? date : new Date(dt + 'Z')
  const s = Math.floor((Date.now() - utcDate) / 1000)
  if (s < 0) return 'Just now'
  if (s < 60) return `${s}s ago`
  if (s < 3600) return `${Math.floor(s / 60)}m ago`
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`
  return utcDate.toLocaleDateString('en-IN', { day: 'numeric', month: 'short', timeZone: 'Asia/Kolkata' })
}
function badgeClass(status) {
  return {
    active: 'badge-active', approved: 'badge-approved', paid: 'badge-paid',
    waiting: 'badge-waiting', partial: 'badge-partial', held: 'badge-held',
    suspended: 'badge-suspended', lapsed: 'badge-lapsed', failed: 'badge-failed'
  }[status] || 'badge-waiting'
}

export default function Dashboard() {
  const { t, i18n } = useTranslation()
  const auth = getAuth()
  const wid = auth?.worker_id

  const [summary, setSummary] = useState(null)
  const [policy, setPolicy] = useState(null)
  const [premHist, setPremHist] = useState([])
  const [claims, setClaims] = useState([])
  const [payouts, setPayouts] = useState([])
  const [activeTriggers, setActiveTriggers] = useState([])
  const [loading, setLoading] = useState(true)
  const [tab, setTab] = useState('policy')

  const [predDeliveries, setPredDeliveries] = useState(10)
  const [predHours, setPredHours] = useState(4)
  const [predType, setPredType] = useState('heavy_rain')
  const [predResult, setPredResult] = useState(null)
  const [predLoading, setPredLoading] = useState(false)

  const handlePredict = async () => {
    setPredLoading(true)
    try {
      const { data } = await api.post(`/api/v1/payout/${wid}/predict`, {
        deliveries_completed_today: predDeliveries,
        disruption_duration_hours: predHours,
        trigger_type: predType
      })
      setPredResult(data)
    } catch (e) {
      alert("Error predicting payout")
    } finally {
      setPredLoading(false)
    }
  }

  useEffect(() => {
    if (!wid) return
    Promise.allSettled([
      api.get('/api/v1/admin/dashboard/summary'),
      api.get(`/api/v1/policy/${wid}`),
      api.get(`/api/v1/premium/history/${wid}`),
      api.get(`/api/v1/claims/${wid}`),
      api.get(`/api/v1/payout/${wid}/history`),
      api.get('/api/v1/trigger/active'),
    ]).then(([s, p, ph, c, pay, at]) => {
      if (s.value) setSummary(s.value.data)
      if (p.value) setPolicy(p.value.data)
      if (ph.value) setPremHist((ph.value.data.history || []).slice().reverse())
      if (c.value) setClaims(c.value.data.items || c.value.data.claims || [])
      if (pay.value) setPayouts(pay.value.data.items || pay.value.data.payouts || [])
      if (at.value) setActiveTriggers(at.value.data.items || at.value.data.active_triggers || [])
      setLoading(false)
    })
  }, [wid])

  if (loading) return (
    <Layout>
      <div className="flex items-center justify-center h-64 gap-3">
        <span className="spinner" /> <span className="text-gray-500">{t('common.loading')}</span>
      </div>
    </Layout>
  )

  const workerZone = auth?.zone_cluster_id || policy?.zone_cluster_id
  const disruptionInZone = activeTriggers.find(t => t.zone_cluster_id === workerZone)
  const shap = policy?.shap_explanation_json
  const shapList = Array.isArray(shap) ? shap : (shap?.top3 || [])
  const waitDays = policy?.days_until_claim_eligible || 0
  const isWaiting = policy?.status === 'waiting' || waitDays > 0

  const translateShap = (str) => {
    if (i18n.language === 'en') {
      return str.replace('உங்கள் மண்டலத்தில் மழை முன்னறிவிப்பு', 'Rain forecast in your zone')
        .replace('வெள்ள அபாய மண்டலம்', 'Flood hazard zone')
        .replace('5 வார சுத்தமான பதிவு', '5 weeks clean record')
    }
    if (i18n.language === 'hi') {
      return str.replace('உங்கள் மண்டலத்தில் மழை முன்னறிவிப்பு', 'आपके क्षेत्र में बारिश का पूर्वानुमान')
        .replace('வெள்ள அபாய மண்டலம்', 'बाढ़ खतरा क्षेत्र')
        .replace('5 வார சுத்தமான பதிவு', '5 सप्ताह का स्वच्छ रिकॉर्ड')
    }
    return str
  }

  const workerName = auth?.label ? auth.label.split('—')[0].trim() : (auth?.platform ? auth.platform.toUpperCase() + ' Worker' : 'Worker')

  return (
    <Layout>
      {/* Welcome Header */}
      <div className="mb-8 fade-up">
        <h1 className="text-3xl font-bold text-primary-900 font-heading">
          {t('common.welcome', 'Welcome back,')} {workerName}
        </h1>
        <p className="text-gray-500 mt-1">Here is your Giggle coverage and community overview.</p>
      </div>

      {/* Alert banner */}
      {disruptionInZone && (
        <div className="mb-6 bg-red-50 border border-red-200 rounded-2xl px-5 py-4 flex items-start gap-3 fade-up">
          <span className="text-2xl">{TRIGGER_DISPLAY[disruptionInZone.trigger_type]?.icon || '⚠️'}</span>
          <div>
            <p className="font-semibold text-red-800">Active Disruption in Your Zone</p>
            <p className="text-sm text-red-600 mt-0.5">
              {TRIGGER_DISPLAY[disruptionInZone.trigger_type]?.en} detected in{' '}
              {ZONE_NAMES[workerZone] || `Zone ${workerZone}`} —{' '}
              {isWaiting ? 'Waiting period active — claim pending review' : 'Claim processing automatically'}
            </p>
          </div>
        </div>
      )}

      {/* KPI bar */}
      {summary && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6 fade-up">
          {[
            { label: t('dashboard.active_policies'), val: summary.active_workers ?? '—', color: 'text-primary-700' },
            { label: t('dashboard.live_disruptions'), val: summary.active_triggers ?? 0, color: 'text-amber-600' },
            { label: t('dashboard.claims_this_week'), val: summary.claims_this_week ?? 0, color: 'text-gray-800' },
            { label: t('dashboard.payouts_this_week'), val: inr(summary.payouts_this_week || 0), color: 'text-green-700' },
          ].map(k => (
            <div key={k.label} className="card text-center">
              <div className={`font-heading text-2xl font-bold ${k.color}`}>{k.val}</div>
              <div className="text-xs text-gray-500 mt-1">{k.label}</div>
            </div>
          ))}
        </div>
      )}

      {/* Tabs */}
      <div className="flex items-center gap-2 mb-6 overflow-x-auto no-scrollbar pb-1 fade-up">
        {[
          ['policy', t('nav.coverage', 'Coverage')],
          ['claims', t('nav.claims', 'Claims')],
          ['payouts', t('nav.payouts', 'Payouts')],
          ['premium', t('nav.premium_history', 'Premium History')],
          ['predictor', t('nav.predictor', 'Payout Predictor')],
        ].map(([id, label]) => (
          <button key={id} onClick={() => setTab(id)}
            className={`px-4 py-2 rounded-xl text-sm font-semibold transition-all whitespace-nowrap ${tab === id ? 'bg-primary-900 text-white shadow-md' : 'bg-white text-gray-600 hover:bg-gray-50 border border-gray-200'
              }`}>
            {label}
          </button>
        ))}
      </div>

      {/* Policy tab */}
      {tab === 'policy' && policy && (
        <div className="grid md:grid-cols-2 gap-6 fade-up">
          <div className="card">
            <div className="flex items-center justify-between mb-4">
              <h2 className="font-heading font-semibold text-primary-900">Your Policy</h2>
              <span className={`badge ${badgeClass(policy.status)}`}>
                {STATUS_DISPLAY[policy.status]?.en || policy.status}
              </span>
            </div>

            {isWaiting && (
              <div className="mb-4 bg-amber-50 border border-amber-200 rounded-xl p-3">
                <p className="text-sm text-amber-800 font-medium">⏳ Waiting Period Active</p>
                <div className="mt-2 bg-amber-200 rounded-full h-2">
                  <div className="bg-amber-500 h-2 rounded-full transition-all" style={{ width: `${Math.max(5, 100 - (waitDays / 28) * 100)}%` }} />
                </div>
                <p className="text-xs text-amber-700 mt-1">{waitDays} days remaining</p>
              </div>
            )}

            <div className="space-y-3">
              {[
                ['Weekly Premium', <span className="font-bold text-primary-900 text-lg">{inr(policy.weekly_premium_amount)}</span>],
                ['Coverage Week', `#${policy.coverage_week_number || '—'}`],
                ['Clean Claim Weeks', policy.clean_claim_weeks ?? '—'],
                ['Claim Eligible', waitDays === 0
                  ? <span className="badge badge-approved">✓ Eligible</span>
                  : <span className="badge badge-waiting">In {waitDays} days</span>],
              ].map(([k, v]) => (
                <div key={k} className="flex justify-between items-center py-2.5 border-b border-gray-50 text-sm">
                  <span className="text-gray-500">{k}</span>
                  <span>{v}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="card">
            <h2 className="font-heading font-semibold text-primary-900 mb-4">{t('dashboard.price_factors')}</h2>
            {shapList.length > 0 ? (
              <div className="space-y-2">
                {shapList.map((s, i) => (
                  <div key={i} className="flex items-start gap-2 py-2.5 border-b border-gray-50 text-sm">
                    <span className="text-lg">{i === 0 ? '🔴' : i === 1 ? '🟡' : '🟢'}</span>
                    <span className="text-gray-700 leading-relaxed">{translateShap(s)}</span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-gray-400 text-sm py-4">No data available for this week.</p>
            )}
          </div>
        </div>
      )}

      {/* Claims tab */}
      {tab === 'claims' && (
        <div className="card fade-up">
          <h2 className="font-heading font-semibold text-primary-900 mb-4">{t('claims.title', 'Claim History')}</h2>
          {claims.length === 0 ? (
            <p className="text-gray-400 text-sm py-8 text-center">{t('claims.empty', 'No claims on record. Disruption events trigger automatic claims.')}</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead><tr className="text-left border-b border-gray-100">
                  {[t('claims.id', 'Claim ID'), t('claims.amount', 'Amount'), t('claims.fraud_score', 'Fraud Score'), t('claims.routing', 'Routing'), t('claims.status', 'Status'), t('claims.filed', 'Filed')].map(h => (
                    <th key={h} className="pb-2 pr-4 text-xs font-semibold text-gray-400 uppercase tracking-wide">{h}</th>
                  ))}
                </tr></thead>
                <tbody>
                  {claims.map(c => {
                    const sc = parseFloat(c.fraud_score || 0)
                    const col = sc < .3 ? 'text-green-600' : sc < .7 ? 'text-amber-600' : 'text-red-600'
                    return (
                      <tr key={c.claim_id || c.id} className="border-b border-gray-50 hover:bg-gray-50 transition-colors">
                        <td className="py-3 pr-4 font-mono text-xs text-gray-500">{String(c.claim_id || c.id).slice(-8).toUpperCase()}</td>
                        <td className="py-3 pr-4 font-bold">{inr(c.total_payout_amount)}</td>
                        <td className={`py-3 pr-4 font-bold ${col}`}>{(sc * 100).toFixed(0)}%</td>
                        <td className="py-3 pr-4"><span className="badge badge-waiting text-xs">{ROUTING_DISPLAY[c.fraud_routing]?.en || c.fraud_routing}</span></td>
                        <td className="py-3 pr-4"><span className={`badge ${badgeClass(c.status)}`}>{STATUS_DISPLAY[c.status]?.en || c.status}</span></td>
                        <td className="py-3 text-gray-400">{ago(c.claim_date)}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Payouts tab */}
      {tab === 'payouts' && (
        <div className="card fade-up">
          <h2 className="font-heading font-semibold text-primary-900 mb-4">{t('payouts.title', 'Payout Ledger')}</h2>
          {payouts.length === 0 ? (
            <p className="text-gray-400 text-sm py-8 text-center">{t('payouts.empty', 'No payouts yet.')}</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead><tr className="text-left border-b border-gray-100">
                  {[t('payouts.amount', 'Amount'), t('payouts.status', 'Status'), t('payouts.razorpay_id', 'Razorpay ID'), t('payouts.initiated', 'Initiated')].map(h => (
                    <th key={h} className="pb-2 pr-4 text-xs font-semibold text-gray-400 uppercase tracking-wide">{h}</th>
                  ))}
                </tr></thead>
                <tbody>
                  {payouts.map(p => (
                    <tr key={p.payout_event_id || p.id} className="border-b border-gray-50 hover:bg-gray-50 transition-colors">
                      <td className="py-3 pr-4 font-bold text-green-700">{inr(p.amount)}</td>
                      <td className="py-3 pr-4"><span className={`badge ${badgeClass(p.status)}`}>{STATUS_DISPLAY[p.status]?.en || p.status}</span></td>
                      <td className="py-3 pr-4 font-mono text-xs text-gray-500">{p.razorpay_payout_id || '—'}</td>
                      <td className="py-3 text-gray-400">{ago(p.initiated_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}


      {/* Premium History */}
      {tab === 'premium' && (
        <div className="card fade-up">
          <h2 className="font-heading font-semibold text-primary-900 mb-4">Premium History</h2>
          {premHist.length === 0 ? (
            <p className="text-gray-400 text-sm py-8 text-center">No premium history yet.</p>
          ) : (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={premHist} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
                <XAxis dataKey="week_number" tickFormatter={w => `W${w}`} tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip formatter={(v) => [`₹${v}`, 'Premium']} />
                <Bar dataKey="premium_amount" fill="#7DAE8A" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      )}

      {/* Payout Predictor */}
      {tab === 'predictor' && (
        <div className="card fade-up">
          <h2 className="font-heading font-semibold text-primary-900 mb-2">{t('predictor.title', 'Payout Predictor')}</h2>
          <p className="text-sm text-gray-500 mb-6">{t('predictor.desc', 'Estimate your potential payout for a hypothetical disruption event based on your real performance history.')}</p>

          <div className="grid md:grid-cols-2 gap-8">
            <form onSubmit={(e) => { e.preventDefault(); handlePredict() }} className="space-y-4">
              <div>
                <label className="block text-sm font-semibold text-gray-700 mb-1">{t('predictor.label_event', 'Disruption Event')}</label>
                <select value={predType} onChange={e => setPredType(e.target.value)} className="w-full border-gray-300 rounded-xl p-2.5 text-sm bg-gray-50">
                  <option value="heavy_rain">{t('predictor.event_rain', 'Heavy Rain')}</option>
                  <option value="severe_heatwave">{t('predictor.event_heat', 'Severe Heatwave')}</option>
                  <option value="platform_suspension">{t('predictor.event_outage', 'Platform Suspension')}</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-semibold text-gray-700 mb-1">{t('predictor.label_deliveries', 'Deliveries Completed Today')}</label>
                <input type="number" min="0" value={predDeliveries} onChange={e => setPredDeliveries(Number(e.target.value))} className="w-full border-gray-300 rounded-xl p-2.5 text-sm bg-gray-50" />
                <p className="text-xs text-gray-400 mt-1">{t('predictor.deliveries_help', 'Number of orders delivered before the disruption started.')}</p>
              </div>

              <div>
                <label className="block text-sm font-semibold text-gray-700 mb-1">{t('predictor.label_duration', 'Disruption Duration (Hours)')}</label>
                <input type="number" min="1" max="24" value={predHours} onChange={e => setPredHours(Number(e.target.value))} className="w-full border-gray-300 rounded-xl p-2.5 text-sm bg-gray-50" />
              </div>

              <button type="submit" disabled={predLoading} className="w-full py-3 rounded-xl bg-primary-900 hover:bg-primary-700 text-white font-bold transition-all shadow-lg hover:shadow-primary-900/20">
                {predLoading ? t('predictor.btn_calculating', 'Calculating...') : t('predictor.btn_predict', 'Predict Payout')}
              </button>
            </form>

            <div className="bg-surface border border-gray-100 rounded-2xl p-5 flex flex-col justify-center min-h-[300px]">
              {predResult ? (
                <div>
                  <h3 className="text-sm font-semibold text-gray-500 mb-4 uppercase tracking-wide">{t('predictor.breakdown_title', 'Estimated Breakdown')}</h3>
                  <div className="space-y-3 mb-6">
                    <div className="flex justify-between items-center text-sm border-b border-gray-100 pb-2">
                      <span className="text-gray-600">{t('predictor.base_loss', 'Base Loss Compensation')}</span>
                      <span className="font-medium text-gray-900">{inr(predResult.base_loss)}</span>
                    </div>
                    <div className="flex justify-between items-center text-sm border-b border-gray-100 pb-2">
                      <span className="text-gray-600">{t('predictor.slab_delta', 'Slab Target Bonus Delta')}</span>
                      <span className="font-medium text-gray-900">{inr(predResult.slab_delta)}</span>
                    </div>
                    <div className="flex justify-between items-center text-sm border-b border-gray-100 pb-2">
                      <span className="text-gray-600">{t('predictor.monthly_proximity', 'Monthly Proximity Protection')}</span>
                      <span className="font-medium text-gray-900">{inr(predResult.monthly_proximity)}</span>
                    </div>
                    {predResult.cascade_multiplier < 1 && (
                      <div className="flex justify-between items-center text-sm text-amber-600 border-b border-gray-100 pb-2">
                        <span>{t('predictor.cascade_taper', 'Cascade Taper')} (Day {predResult.cascade_day})</span>
                        <span className="font-medium">{(predResult.cascade_multiplier * 100).toFixed(0)}%</span>
                      </div>
                    )}
                  </div>
                  <div className="pt-2 border-t-2 border-gray-800">
                    <div className="flex justify-between items-end">
                      <div>
                        <span className="block text-[10px] font-semibold text-gray-500 uppercase">{t('predictor.total_label', 'Total Predicted Payout')}</span>
                        {predResult.total_payout >= predResult.weekly_baseline_cap && (
                          <span className="text-[10px] text-amber-600 font-medium">{t('predictor.capped_notice', 'Capped at weekly baseline')}</span>
                        )}
                      </div>
                      <span className="text-3xl font-bold text-green-600">{inr(predResult.total_payout)}</span>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="text-center text-gray-400 py-8">
                  <span className="text-4xl mb-3 block">📊</span>
                  <p className="text-sm">{t('predictor.placeholder', 'Enter scenario details and click Predict Payout to see your personalized estimate.')}</p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

    </Layout>
  )
}
