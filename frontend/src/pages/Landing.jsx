import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../config/api'
import { ZONE_NAMES } from '../config/constants'
import { ago } from '../utils/dateUtils'

const STEPS = [
  {
    num: '01',
    title: 'Rain hits your zone',
    desc: 'Open-Meteo queries 3 GPS points around your area. IMD alerts + GIS flood overlay confirm the disruption.',
  },
  {
    num: '02',
    title: 'Giggle engine fires',
    desc: 'Two-of-three corroboration gate passes. Fraud engine scores every claim in milliseconds. No paperwork.',
  },
  {
    num: '03',
    title: 'UPI credited in 60s',
    desc: 'Your payout is calculated using your real delivery history and sent to your GPay — automatically.',
  },
]

const TRUST = [
  { val: '15M+', label: 'Gig workers at risk in India' },
  { val: '₹49', label: 'Starting weekly premium' },
  { val: '< 60s', label: 'Average payout time' },
  { val: '0', label: 'Forms or calls required' },
]

export default function Landing() {
  const [health, setHealth] = useState(null)
  const [activeTriggers, setActiveTriggers] = useState([])
  const [tick, setTick] = useState(0)

  useEffect(() => {
    api.get('/api/v1/health').then(r => setHealth(r.data)).catch(() => setHealth({ status: 'offline' }))
    api.get('/api/v1/trigger/active').then(r => setActiveTriggers(r.data.items || [])).catch(() => {})
    const id = setInterval(() => setTick(t => t + 1), 3000)
    return () => clearInterval(id)
  }, [])

  const ok = health?.database === 'ok' || health?.database === 'connected'

  const events = activeTriggers.length > 0
    ? activeTriggers.slice(0, 5).map(t => {
        const utcDate = new Date(t.triggered_at.toString().includes('Z') ? t.triggered_at : t.triggered_at + 'Z')
        const ageSeconds = Math.floor((Date.now() - utcDate) / 1000)
        
        let payoutStatus = '✓ Approved'
        if (ageSeconds < 45) {
          payoutStatus = '⏳ Scoring'
        } else if (t.composite_score > 0.9) {
          payoutStatus = '✓ Auto-Approved'
        }

        return {
          zone: ZONE_NAMES[t.zone_cluster_id] || `Zone ${t.zone_cluster_id}`,
          event: `${t.trigger_type?.replace(/_/g, ' ').replace(/\baqi\b/gi, 'AQI').replace(/\b\w/g, l => l.toUpperCase())} detected`,
          payout: payoutStatus,
          time: ago(t.triggered_at),
          color: t.trigger_type?.includes('rain') ? 'bg-blue-500' : 'bg-amber-500'
        }
      })
    : [
        { zone: 'Velachery', event: 'Heavy Rain trigger fired', payout: '₹312', time: '2m ago', color: 'bg-blue-500' },
        { zone: 'T. Nagar', event: 'Platform suspension detected', payout: '₹245', time: '8m ago', color: 'bg-amber-500' },
        { zone: 'Tambaram', event: 'Heatwave — claim approved', payout: '₹198', time: '15m ago', color: 'bg-red-500' },
        { zone: 'Adyar', event: 'Rain cleared — trigger closed', payout: '—', time: '22m ago', color: 'bg-green-500' },
      ]

  return (
    <div className="min-h-screen bg-surface font-sans text-gray-900">

      {/* ── Navbar ─────────────────────────────────────── */}
      <header className="fixed top-0 left-0 right-0 z-50 bg-white/70 backdrop-blur-xl border-b border-primary-100/50">
        <div className="max-w-7xl mx-auto px-8 h-16 flex items-center">
          {/* Logo */}
          <Link to="/" className="flex items-center gap-2.5 mr-10">
            <div className="w-8 h-8 rounded-lg bg-primary-900 flex items-center justify-center">
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                <path d="M8 2L14 6V10L8 14L2 10V6L8 2Z" fill="white" opacity="0.9"/>
                <circle cx="8" cy="8" r="2.5" fill="#4ade80"/>
              </svg>
            </div>
            <span className="font-heading font-bold text-lg text-gray-900 tracking-tight">Giggle</span>
          </Link>

          {/* Nav links */}
          <nav className="hidden md:flex items-center gap-6 text-sm text-gray-500 font-medium">
            <a href="#how" className="hover:text-primary-700 transition-colors">How it Works</a>
            <a href="#cta" className="hover:text-primary-700 transition-colors">Coverage</a>
          </nav>

          <div className="ml-auto flex items-center gap-3">
            {/* Status pill */}
            <span className={`hidden sm:flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-full font-medium border ${
              health === null ? 'bg-gray-50 text-gray-400 border-gray-200' :
              ok ? 'bg-green-50 text-green-700 border-green-200' :
              'bg-red-50 text-red-600 border-red-200'
            }`}>
              <span className={`w-1.5 h-1.5 rounded-full ${ok ? 'bg-green-500' : 'bg-red-500'} ${ok ? 'animate-pulse' : ''}`} />
              {health === null ? 'Connecting' : ok ? 'Systems Live' : 'API Offline'}
            </span>
            <Link to="/login" className="text-sm font-medium text-gray-600 hover:text-gray-900 px-4 py-2 rounded-lg hover:bg-gray-100 transition-colors">
              Sign In
            </Link>
            <Link to="/register" className="text-sm font-semibold text-white bg-primary-900 hover:bg-primary-700 px-5 py-2.5 rounded-xl transition-all hover:shadow-lg hover:-translate-y-px">
              Get Protected
            </Link>
          </div>
        </div>
      </header>

      {/* ── Hero — Split Layout ──────────────────────────── */}
      <section className="min-h-screen flex items-center pt-16 relative overflow-hidden bg-primary-50/50">
        {/* Prominent mesh background */}
        <div className="absolute inset-0 -z-10 opacity-70" style={{
          backgroundImage: `
            radial-gradient(circle at 15% 50%, rgba(34, 197, 94, 0.15) 0%, transparent 50%),
            radial-gradient(circle at 85% 30%, rgba(13, 40, 24, 0.08) 0%, transparent 50%),
            radial-gradient(circle at 50% 80%, rgba(34, 197, 94, 0.1) 0%, transparent 50%)
          `
        }} />
        {/* Dot grid */}
        <div className="absolute inset-0 -z-10" style={{
          backgroundImage: 'radial-gradient(rgba(13, 40, 24, 0.1) 1px, transparent 1px)',
          backgroundSize: '24px 24px',
          opacity: 0.5,
        }} />
        <div className="max-w-7xl mx-auto px-6 sm:px-8 py-12 md:py-20 w-full grid lg:grid-cols-2 gap-12 lg:gap-16 items-center relative z-10">

          {/* Left: Text */}
          <div>
            <div className="inline-flex items-center gap-2 bg-primary-50 border border-primary-200 rounded-full px-4 py-1.5 text-xs font-semibold text-primary-800 mb-8">
              <span className="w-1.5 h-1.5 rounded-full bg-primary-500" />
              Guidewire DEVTrails 2026 · Team ShadowKernel
            </div>

            <h1 className="font-heading text-4xl sm:text-5xl md:text-6xl font-black text-gray-900 leading-[1.05] tracking-tight mb-6">
              Your income,<br/>
              <span className="text-primary-600">protected</span><br/>
              from day one.
            </h1>

            <p className="text-gray-500 text-lg leading-relaxed mb-10 max-w-md">
              When rain, floods, or platform outages stop your deliveries, Giggle automatically detects the disruption and credits your UPI wallet — no claims, no calls, no waiting.
            </p>

            <div className="flex flex-wrap gap-3 mb-12">
              <Link to="/register"
                className="inline-flex items-center gap-2 bg-primary-900 text-white font-semibold px-7 py-4 rounded-2xl hover:bg-primary-700 transition-all hover:shadow-xl hover:-translate-y-0.5 text-base">
                Enroll in 2 minutes
                <svg className="w-4 h-4" viewBox="0 0 16 16" fill="none">
                  <path d="M3 8h10M9 4l4 4-4 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
              </Link>
              <Link to="/login?role=admin"
                className="inline-flex items-center gap-2 text-gray-700 font-medium px-7 py-4 rounded-2xl border border-gray-200 hover:border-gray-300 hover:bg-gray-50 transition-all text-base">
                Admin access
              </Link>
            </div>

            {/* Inline trust signals */}
            <div className="flex flex-wrap gap-6 text-sm text-gray-400 font-medium">
              <span className="flex items-center gap-1.5">
                <svg className="w-4 h-4 text-green-500" viewBox="0 0 16 16" fill="currentColor"><path d="M8 1l1.85 3.75L14 5.5l-3 2.93.71 4.07L8 10.4l-3.71 2.1.71-4.07L2 5.5l4.15-.75z"/></svg>
                No paperwork
              </span>
              <span className="flex items-center gap-1.5">
                <svg className="w-4 h-4 text-green-500" viewBox="0 0 16 16" fill="currentColor"><path d="M8 1l1.85 3.75L14 5.5l-3 2.93.71 4.07L8 10.4l-3.71 2.1.71-4.07L2 5.5l4.15-.75z"/></svg>
                Razorpay UPI payouts
              </span>
              <span className="flex items-center gap-1.5">
                <svg className="w-4 h-4 text-green-500" viewBox="0 0 16 16" fill="currentColor"><path d="M8 1l1.85 3.75L14 5.5l-3 2.93.71 4.07L8 10.4l-3.71 2.1.71-4.07L2 5.5l4.15-.75z"/></svg>
                Zomato & Swiggy eligible
              </span>
            </div>
          </div>

          {/* Right: Live Activity Card */}
          <div className="relative">
            {/* Mesh background */}
            <div className="absolute -inset-8 bg-gradient-to-br from-primary-100 via-primary-50 to-green-100 rounded-3xl -z-10 opacity-60 blur-xl" />
            <div className="absolute -top-4 -right-4 w-48 h-48 bg-primary-300 rounded-full blur-3xl opacity-30 -z-10" />

            <div className="bg-white/90 backdrop-blur-md rounded-3xl shadow-xl border border-primary-100/60 overflow-hidden">
              {/* Card header */}
              <div className="px-6 py-5 border-b border-gray-50 flex items-center justify-between">
                <div>
                  <p className="text-xs font-semibold text-primary-400 uppercase tracking-wide">Live Pipeline</p>
                  <p className="text-sm font-bold text-gray-900 mt-0.5">Chennai Zone Activity</p>
                </div>
                <span className="flex items-center gap-1.5 text-xs font-semibold text-green-700 bg-green-50 px-3 py-1.5 rounded-full border border-green-200">
                  <span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
                  Live
                </span>
              </div>

              {/* Events list */}
              <div className="divide-y divide-gray-50">
                {events.map((ev, i) => (
                  <div key={i} className={`px-6 py-4 flex items-center gap-4 transition-all duration-500 ${i === tick % 4 ? 'bg-primary-50/60' : ''}`}>
                    <span className={`w-2.5 h-2.5 rounded-full shrink-0 ${ev.color} ${i === tick % 4 ? 'animate-pulse' : 'opacity-50'}`} />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-semibold text-gray-900 truncate">{ev.zone}</p>
                      <p className="text-xs text-primary-400/80 truncate">{ev.event}</p>
                    </div>
                    <div className="text-right shrink-0">
                      <p className={`text-sm font-bold ${ev.payout !== '—' ? 'text-primary-700' : 'text-gray-300'}`}>{ev.payout}</p>
                      <p className="text-xs text-gray-400">{ev.time}</p>
                    </div>
                  </div>
                ))}
              </div>

              {/* Card footer */}
              <div className="px-6 py-4 bg-primary-50/50 flex items-center justify-between border-t border-primary-100/30">
                <p className="text-xs text-gray-400">Powered by Open-Meteo · IMD · Razorpay</p>
                <div className="flex -space-x-2">
                  {['PS','RK','MA'].map(i => (
                    <span key={i} className="w-6 h-6 rounded-full bg-primary-200 border-2 border-white flex items-center justify-center text-[9px] font-bold text-primary-800">{i}</span>
                  ))}
                  <span className="w-6 h-6 rounded-full bg-gray-100 border-2 border-white flex items-center justify-center text-[9px] font-bold text-gray-500">+17</span>
                </div>
              </div>
            </div>
          </div>

        </div>
      </section>

      {/* ── Trust Numbers ───────────────────────────────── */}
      <section id="trust" className="bg-primary-900 py-24 relative overflow-hidden">
        {/* Subtle mesh for the dark section */}
        <div className="absolute inset-0 opacity-20" style={{
          backgroundImage: `radial-gradient(circle at 50% 50%, rgba(34, 197, 94, 0.15) 0%, transparent 70%)`
        }} />
        
        <style>{`
          @keyframes borderRotate {
            from { transform: translate(-50%, -50%) rotate(0deg); }
            to   { transform: translate(-50%, -50%) rotate(360deg); }
          }
          .stat-card-animated {
            position: relative;
            overflow: hidden;
            border: 1px solid rgba(255,255,255,0.05);
            transition: border-color 0.3s;
          }
          .stat-card-animated:hover {
            border-color: transparent;
          }
          .stat-card-animated::before {
            content: '';
            position: absolute;
            left: 50%;
            top: 50%;
            width: 200%;
            height: 200%;
            background: conic-gradient(
              from 0deg,
              transparent 0%,
              transparent 65%,
              #22c55e 100%
            );
            animation: borderRotate 3s linear infinite;
            opacity: 0;
            transition: opacity 0.3s;
            z-index: 0;
            pointer-events: none;
          }
          .stat-card-animated:hover::before {
            opacity: 1;
          }
          .stat-card-animated-inner {
            position: absolute;
            inset: 1.5px;
            z-index: 1;
            border-radius: 14px;
            background: #06160c; /* Very dark green-black */
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            overflow: hidden;
          }
        `}</style>

        <div className="max-w-7xl mx-auto px-6 sm:px-8 grid grid-cols-2 md:grid-cols-4 gap-4 sm:gap-6 relative z-10">
          {TRUST.map(t => (
            <div key={t.label} className="stat-card-animated h-32 rounded-2xl bg-black/20">
              <div className="stat-card-animated-inner p-8 text-center backdrop-blur-md">
                <div className="font-heading text-4xl font-black text-white mb-1 tracking-tight">
                  {t.val}
                </div>
                <div className="text-[10px] text-green-400 font-black uppercase tracking-[0.2em]">
                  {t.label}
                </div>
              </div>
            </div>
          ))}
        </div>
      </section>


      {/* ── How it Works ────────────────────────────────── */}
      <section id="how" className="max-w-7xl mx-auto px-8 py-32 relative">
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-full h-full -z-10 overflow-hidden">
          <div className="absolute top-0 left-0 w-full h-px bg-gradient-to-r from-transparent via-primary-200 to-transparent opacity-30" />
          <div className="absolute top-20 -left-20 w-96 h-96 bg-primary-100/40 rounded-full blur-[100px]" />
          <div className="absolute bottom-20 -right-20 w-80 h-80 bg-green-100/30 rounded-full blur-[100px]" />
        </div>
        <div className="max-w-6xl mx-auto">
          <p className="text-xs font-bold text-primary-400 uppercase tracking-widest mb-3">The Process</p>
          <h2 className="font-heading text-4xl font-black text-gray-900 tracking-tight">
            Three steps.<br/>
            <span className="text-primary-400/50">No intervention needed.</span>
          </h2>
        </div>

        <div className="grid md:grid-cols-3 gap-px bg-primary-100/50 rounded-3xl overflow-hidden border border-primary-100/50">
          {STEPS.map((s) => (
            <div key={s.num} className="bg-white/80 backdrop-blur-sm p-8 hover:bg-white transition-all group hover:shadow-lg hover:-translate-y-1">
              <span className="font-heading text-6xl font-black text-gray-200 group-hover:text-primary-500 transition-colors leading-none block mb-6 drop-shadow-sm">
                {s.num}
              </span>
              <h3 className="font-heading font-bold text-gray-900 text-lg mb-3">{s.title}</h3>
              <p className="text-gray-500 text-sm leading-relaxed">{s.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ── CTA ─────────────────────────────────────────── */}
      <section id="cta" className="max-w-7xl mx-auto px-8 pb-28">
        <div className="bg-primary-900 rounded-3xl px-12 py-16 flex flex-col md:flex-row items-center justify-between gap-8">
          <div>
            <h2 className="font-heading text-3xl font-black text-white mb-2">
              Start protecting your income today.
            </h2>
            <p className="text-white/50 text-base">
              Takes 2 minutes. No documents. Works with your existing UPI.
            </p>
          </div>
          <div className="flex gap-3 shrink-0">
            <Link to="/register"
              className="inline-flex items-center gap-2 bg-white text-primary-900 font-bold px-7 py-4 rounded-2xl hover:bg-gray-100 transition-all text-base whitespace-nowrap">
              Enroll Now
            </Link>
            <Link to="/login"
              className="inline-flex items-center gap-2 border border-white/20 text-white font-medium px-7 py-4 rounded-2xl hover:bg-white/10 transition-all text-base whitespace-nowrap">
              Sign In
            </Link>
          </div>
        </div>
      </section>

      {/* ── Footer ──────────────────────────────────────── */}
      <footer className="border-t border-primary-100/50 px-8 py-6 max-w-7xl mx-auto flex items-center justify-between text-xs text-gray-400">
        <span>© 2026 Giggle · Team ShadowKernel · Guidewire DEVTrails</span>
        <Link to="/login?role=admin" className="hover:text-gray-600 transition-colors font-medium">Admin Portal</Link>
      </footer>

    </div>
  )
}
