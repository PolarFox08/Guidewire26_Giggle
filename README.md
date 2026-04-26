# Giggle

## AI-Powered Parametric Income Insurance for India's Gig Economy

> **Guidewire DEVTrails 2026** · University Hackathon · Seed → Scale → Soar
> **Placement:** Finished Top 7 on leaderboard · Selected for Live Demo (DemoJam at DevSummit 2026)
> **Team:** ShadowKernel
> **Persona:** Food Delivery Partners (Zomato and Swiggy), Chennai
> **Coverage:** Income loss from external disruptions only. Health, life, accident, and vehicle repair are explicitly excluded.

---

## Links

| Resource | Link |
|---|---|
| 🎥 Phase 1 Video | [Watch on YouTube/Drive](https://youtu.be/Cym08VIJqjM?si=JFqiiSrCJ86C7UE4) |
| 🎥 Phase 3 Video | [Watch on YouTube/Drive](https://youtu.be/Cym08VIJqjM?si=JFqiiSrCJ86C7UE4) |
| 📊 Final Pitch Deck | [View on Google Slides](https://docs.google.com/presentation/d/1qn5IUIiTm2DbUQ9SqbRwwwnpnb5uIV69/edit?usp=sharing) |
| 🌐 Live Demo (Frontend) | [giggle.vercel.app](#) |
| ⚙️ Live API | [giggle-api.onrender.com/docs](#) |
| 💻 Repository | [github.com/Hemachandhar-A/Giggle](https://github.com/Hemachandhar-A/Giggle) |

---

## Table of Contents

- [The Problem We're Solving](#the-problem-were-solving)
- [What Giggle Is](#what-giggle-is)
- [What Makes Giggle Different](#what-makes-giggle-different)
- [Persona: Priya, Zomato Delivery Partner, Velachery, Chennai](#persona-priya-zomato-delivery-partner-velachery-chennai)
- [Application Workflow](#application-workflow)
- [Weekly Premium Model](#weekly-premium-model)
- [Parametric Triggers](#parametric-triggers)
- [AI/ML Integration](#aiml-integration)
- [Tech Stack](#tech-stack)
- [What We Built (Phase Summary)](#what-we-built-phase-summary)
- [Competitive Differentiation](#competitive-differentiation)
- [Business Model](#business-model)
- [Repository Structure](#repository-structure)
- [Local Development Setup](#local-development-setup)
- [Deployment](#deployment)
- [Scope Boundaries](#scope-boundaries-per-hackathon-golden-rules)
- [References and Evidence Base](#references-and-evidence-base)

---

## The Problem We're Solving

India's 15 million+ platform delivery workers are the last mile of the digital economy. A Zomato rider in Velachery earns ₹20,000–₹30,000 per month — but a single monsoon week can wipe 20–30% of that income with zero safety net.

The problem is not just income loss. It is **how income is structured**. Platform base rates have fallen from ₹40–45/order to ₹15–20/order. Slab bonuses — ₹50 at 7 deliveries, ₹120 at 12, ₹150 at 15, ₹200 at 21+ per day — now constitute a larger fraction of total earnings than base pay. A rain disruption that stops a worker at delivery 10 doesn't just cost 10 deliveries of base pay. It costs the ₹120 slab bonus they were 2 orders away from. **No existing insurance product addresses this.** Not SEWA. Not MIC Global. Not any insurtech in India.

SEWA's 2023 parametric pilot — the only documented attempt — **triggered zero payouts** because city-level IMD weather station data failed to capture hyperlocal conditions. Workers enrolled, paid premiums, and received nothing during the monsoon that should have covered them. Giggle's architecture is built specifically to solve the failure modes SEWA documented.

---

## What Giggle Is

Giggle is a parametric income insurance platform for food delivery workers. When an external disruption — heavy rain, extreme heat, severe pollution, or zone curfew — makes delivery work physically impossible, Giggle detects it automatically, computes the worker's true income loss (including the slab bonus they missed), validates the claim against a multi-layer fraud engine, and deposits the payout to their UPI account within 60 seconds. No claim forms. No calls. No waiting.

**The worker does nothing. The system does everything.**

---

## What Makes Giggle Different

- **Slab-aware payout computation** — the world's first parametric insurance product that models India's platform incentive slab structure. A disruption at delivery 10 costs the ₹120 slab bonus the worker was 2 orders away from. Every existing product ignores this. Giggle computes it.
- **SEWA's 2023 failure, directly fixed** — SEWA's parametric pilot triggered zero payouts because city-level IMD data missed hyperlocal conditions. Giggle queries Open-Meteo at 3 geographic points per zone (centroid + 2 offsets) and takes the maximum reading, expanding spatial coverage to the worker's actual 5–8km delivery radius.
- **2-of-3 source corroboration** — no single weather station controls a payout. Environmental data, geospatial flood zone activation, and platform zone suspension must independently confirm before a claim fires. Eliminates both false positives and the single-point failure that collapsed SEWA's pilot.
- **Isolation Forest + CBLOF fraud ensemble** — CBLOF outperforms Isolation Forest on spatially consistent fraud patterns (silhouette 0.114 vs 0.103, Springer Nature 2025). Running both with max-score output catches ring fraud that either model misses alone.
- **Multilingual-first UX with SHAP explanations in vernacular** — every premium change explained in the worker's primary language (Tamil and Hindi). Onboarding, coverage status, and payout notifications all render in the worker's selected language.

---

## Persona: Priya, Zomato Delivery Partner, Velachery, Chennai

**Profile:** 28 years old. Works 10 hours/day, 6 days/week. Average 14 deliveries/day. Monthly earnings: ₹22,000 (₹17,000 base + ₹5,000 incentive slabs). Primary earner for a family of three.

**The disruption reality Priya faces:**
- Chennai Northeast Monsoon (October–December): 265mm in October, 310mm in November. Velachery floods at 30mm/6hr — documented high-risk GCC drainage zone.
- Cyclone Michaung (December 2023): 500mm in one day. Velachery was impassable for 3–5 days. Priya lost ₹3,300–₹4,400 in one event with zero compensation.
- On a rain surge day (Zomato offers ₹20 extra per order), she loses not just base income — she loses the peak earning opportunity on top.

**What Priya needs from Giggle:**
- A weekly premium she can afford (under ₹100/week, below 2.5% of her weekly income)
- Automatic payout she doesn't have to chase
- An app in Tamil that explains her premium and coverage in plain terms
- Same-day UPI payout so she can buy groceries on the day the storm hits

---

## Application Workflow

### Onboarding Flow

```
Worker opens Giggle app (language: Tamil or Hindi based on preference)
        ↓
Phone number → OTP verification (mock in demo; any 6-digit OTP accepted)
        ↓
Aadhaar OTP verification (mock) → SHA-256 hash stored, raw number never persisted
        ↓
PAN cross-check + Bank account UPI VPA validation via Razorpay
        ↓
Zomato/Swiggy Partner ID verified (simulated B2B2C API)
        ↓
Pincode entered → GIS spatial join (GeoPandas + OpenCity flood hazard GeoJSON)
                  → Flood hazard zone tier assigned (High / Medium / Low)
                  → Zone cluster ID assigned (M5 k-Means, k=20)
        ↓
UPI AutoPay Mandate setup (auto-deduction every Sunday from worker's UPI)
        ↓
4-week waiting period begins → recency premium multiplier applied (1.5× weeks 1–2, 1.25× weeks 3–4)
        ↓
GLM cold-start pricer (M1) computes first weekly premium (zone tier + season + platform)
        ↓
Worker sees: premium amount + SHAP explanation in Tamil/Hindi + zone risk profile
        ↓
Weekly premium auto-deducted via UPI mandate → Policy active
```

### Active Coverage Flow (Every Sunday Midnight via Celery Beat)

```
Celery batch job recalculates income baseline from 30-day delivery activity
        ↓
LightGBM model (M2) computes next week's premium using 11 features
        ↓
SHAP TreeExplainer generates top-3 explanation strings in worker's language
        ↓
Push notification sent in Tamil/Hindi
        ↓
Premium auto-deducted from UPI mandate
```

### Trigger → Payout Flow (Zero Touch — Every 30 Minutes via Celery Beat)

```
Celery polling job queries:
  [1] Open-Meteo API at 3 geographic points per zone cluster
      centroid + 3km NNE offset + 3km SSW offset → max precipitation reading taken
  [2] IMD threshold classification: 64.5mm/24h=Heavy, 115.6mm/24h=Very Heavy, 204.4mm/24h=Extreme
  [3] CPCB AQI API: >300 for 4 consecutive hours = Severe trigger
  [4] Temperature: >45°C for 4+ consecutive hours = Severe Heatwave trigger
  [5] Mock platform zone status API: suspended = strongest single trigger signal
        ↓
Composite disruption score computed:
  Platform zone suspension: 0.40 weight
  Rainfall at IMD threshold: 0.35 weight
  GIS flood zone activation: 0.15 weight
  AQI severe / Extreme heat: 0.10 weight (mutually exclusive, don't stack)
        ↓
2-of-3 source corroboration gate:
  Score < 0.5  → No trigger
  Score 0.5–0.9 → 2 of 3 independent sources must confirm (Environmental + Geospatial + Operational)
  Score > 0.9  → Fast-path: immediate trigger, bypass gate, mandatory audit log
        ↓
IF TRIGGERED:
  Payout calculation:
    Base loss = missed_deliveries × observed per-order rate (capped at 1.5× zone rate)
    Slab delta = P(slab_missed | deliveries_today, day_of_week, time_slot) × slab_bonus_value
    Monthly proximity = P(would_hit_200) × ₹2,000 [final 7 days of month only]
    Peak multiplier = 1.2× if rain surge active in zone [provisional]
    Total payout capped at verified 7-day income baseline
        ↓
  Fraud scoring pipeline (parallel):
    Isolation Forest + CBLOF ensemble → max anomaly score
    Zone-claim GPS consistency (PostGIS ST_Within)
    Delivery activity trajectory (7-day pre-event vs 30-day average)
    Cross-platform activity flag
    Enrollment recency signal (max 0.15 weight)
    Claim timing cluster detection
    Rain paradox validator
        ↓
  Tiered routing:
    Score < 0.30 → Auto-approve → Razorpay UPI payout within 60 seconds
    Score 0.30–0.70 → 50% payout immediately + 48-hour review window
    Score > 0.70  → Full hold → Fraud review queue for manual admin decision
        ↓
  Tamil notification: "₹420 உங்கள் UPI-க்கு அனுப்பப்பட்டது"
  Hindi notification: "₹420 आपके UPI में भेज दिया गया है"
        ↓
Cascade check (every 12 hours post-trigger):
  Still disrupted? → Continue cascade payout: 100% D1 → 80% D2 → 60% D3 → 40% D4–D5
  All 3 sources report normal → Cascade closes → 24hr recovery window before new trigger
```

---

## Weekly Premium Model

**Premium range: ₹49–₹149/week.** Capped at 2.5% of weekly income. At ₹72 average, this is 1.8% of Priya's ₹4,000 weekly income — below the 2.5% microinsurance affordability threshold.

### Model Architecture

| Workers | Model | Features |
|---|---|---|
| Weeks 1–4 (zero history) | GLM Tweedie (statsmodels) — M1 | Zone tier, season flag, platform |
| Week 5+ | LightGBM (objective=tweedie, variance_power=1.5) — M2 | 11 features (see below) |

**Recency multipliers:** 1.5× weeks 1–2 · 1.25× weeks 3–4 · 1.0× from week 5

### LightGBM Feature Set (M2)

| Feature | Source |
|---|---|
| `flood_hazard_zone_tier` | OpenCity GIS spatial join at registration |
| `zone_cluster_id` (1–20) | M5 k-Means output |
| `platform` | Worker declaration |
| `delivery_baseline_30d` | Worker input / simulated delivery history |
| `income_baseline_weekly` | Computed: baseline × zone_rate_mid ÷ 30 × 7 |
| `enrollment_week` | Derived from enrollment_date |
| `season_flag` | Calendar-week lookup (SW_monsoon / NE_monsoon / heat / dry) |
| `open_meteo_7d_precip_probability` | Open-Meteo Forecast API (daily poll) |
| `activity_consistency_score` (M7) | Std dev of 8-week delivery count series, normalized |
| `tenure_discount_factor` | enrollment_week + clean_claim_weeks |
| `historical_claim_rate_zone` | Aggregated from audit_events by zone cluster per season |

**Why Tweedie loss:** Insurance data is zero-inflated (most weeks, no claim fires). Gaussian loss produces systematically biased estimates. LightGBM's `objective='tweedie'` is explicitly documented for insurance total-loss modeling.

### SHAP Premium Explanation (Multilingual)

Every weekly renewal generates a plain-language explanation in the worker's language using pre-approved Tamil and Hindi templates via SHAP TreeExplainer.

Tamil: *"உங்கள் மண்டலத்தில் மழை முன்னறிவிப்பு (+₹12) · வெள்ள அபாய மண்டலம் (+₹8) · 5 வார சுத்தமான பதிவு (-₹5)"*

Hindi: *"आपके क्षेत्र में बारिश का पूर्वानुमान (+₹12) · बाढ़ जोखिम क्षेत्र (+₹8) · 5 हफ्तों का साफ रिकॉर्ड (-₹5)"*

---

## Parametric Triggers

### Trigger 1 — Heavy Rainfall (Environmental)
- **Source:** Open-Meteo API · 1km resolution · updated hourly
- **Method:** 3-point spatial oversampling (centroid + 3km NNE + 3km SSW) · max precipitation taken
- **Threshold:** ≥64.5mm/24h (Heavy Rain) · ≥115.6mm (Very Heavy) · ≥204.4mm (Extremely Heavy)
- **Weight:** 0.35

### Trigger 2 — Flood Zone Activation (Geospatial)
- **Source:** OpenCity Chennai Flood Hazard Zones GeoJSON (public government data)
- **Method:** Zone tier assigned at onboarding via GeoPandas spatial join — cannot be spoofed retroactively
- **Weight:** 0.15

### Trigger 3 — Platform Zone Suspension (Operational)
- **Source:** Mock platform REST API (production: B2B2C API with Zomato/Swiggy)
- **Weight:** 0.40 — highest single signal

### Trigger 4 — Severe AQI (Environmental)
- **Source:** CPCB NAMP API
- **Threshold:** AQI >300 for 4 consecutive hourly readings
- **Weight:** 0.10 (mutually exclusive with heatwave — whichever active takes the slot)

### Trigger 5 — Severe Heatwave (Environmental)
- **Source:** Open-Meteo temperature_2m
- **Threshold:** >45°C for 4+ consecutive hours (IMD Severe Heatwave classification)
- **Weight:** 0.10

---

## AI/ML Integration

### Model Inventory

| ID | Name | Type | Purpose |
|---|---|---|---|
| M1 | GLM Cold-Start Pricer | Tweedie GLM (statsmodels) | Weekly premium for workers weeks 1–4 |
| M2 | LightGBM Weekly Premium | GBDT Tweedie | Dynamic weekly premium from week 5+ |
| M3 | Isolation Forest | Unsupervised (sklearn) | Fraud — global outlier detection |
| M4 | CBLOF | Cluster-based (PyOD) | Fraud — ring fraud detection |
| M5 | Zone Cluster Model | k-Means k=20 (sklearn) | Pincode cardinality reduction 400+ → 20 |
| M6 | Slab Probability Estimator | Non-parametric SQL | P(slab_missed) for payout delta |
| M7 | Activity Consistency Scorer | Rolling std dev, normalized | LightGBM feature + fraud signal |
| M8 | Delivery Activity Trajectory | Statistical ratio + SQL | Pre-event suppression fraud signal |
| M9 | Enrollment Recency Signal | Deterministic formula | Adverse selection signal (max 0.15 weight) |
| M10 | Predictive Claims Forecast | Deterministic heuristic | 7-day reserve management for admin |

### Trained Model Artifacts (Git LFS)

All `.joblib` artifacts are stored via Git LFS at `backend/app/ml/artifacts/`:

- `glm_m1.joblib` — GLM bundle with model + LabelEncoders
- `lgbm_m2.joblib` — LightGBM regressor
- `shap_explainer_m2.joblib` — SHAP TreeExplainer for M2
- `lgbm_m2_feature_list.joblib` — Ordered feature list for inference
- `kmeans_m5.joblib` — k-Means model + StandardScaler bundle

### Fraud Detection: 7-Layer Pipeline

| Layer | Signal | Method |
|---|---|---|
| 1 | IF + CBLOF ensemble score | Max of both models on 4-feature vector |
| 2 | Zone-claim GPS consistency | PostGIS ST_Within on last 5 GPS delivery points |
| 3 | Delivery activity trajectory | 7-day pre-event ratio vs 30-day avg (M8) |
| 4 | Cross-platform activity flag | Secondary platform activity during covered disruption |
| 5 | Enrollment recency | 1 − (enrollment_week ÷ 26), capped at 0.15 weight |
| 6 | Claim timing cluster detection | >10 simultaneous claims during low composite score (<0.5) |
| 7 | Rain paradox validator | Non-flood zone + elevated order volume = fraud signal |

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend (Worker + Admin) | React + Vite + TailwindCSS |
| i18n | react-i18next · Tamil + Hindi + English locale files |
| Charts | Recharts |
| API | FastAPI + Uvicorn (async, 2,847 req/s) |
| Task Queue | Celery + Redis (Upstash free tier) |
| ORM + Migrations | SQLAlchemy 2.0 + Alembic |
| Database | PostgreSQL 16 (Supabase) |
| Geospatial | PostGIS (ST_Within, polygon storage) |
| Time-Series | TimescaleDB extension |
| ML — Premium | LightGBM + statsmodels |
| ML — Fraud | sklearn IsolationForest + PyOD CBLOF |
| ML — Explainability | SHAP TreeExplainer |
| GIS Processing | GeoPandas |
| Fraud Graph | NetworkX (device/IP ring detection) |
| Model Serialization | joblib + Git LFS |
| Weather | Open-Meteo API (free, 1km resolution, 80yr archive) |
| AQI | CPCB NAMP API (free, public) |
| Payments | Razorpay SDK (sandbox UPI payout) |
| Frontend Deploy | Vercel |
| Backend Deploy | Render |
| DB | Supabase (PostgreSQL, free tier) |
| Redis | Upstash (free tier) |

---

## What We Built (Phase Summary)

### Phase 1 — Ideation & Foundation ✅ Complete
- Full product architecture and specification
- Persona research grounded in IMD, SEWA, CPCB documented data
- ML model inventory (M1–M10) with data plans and feasibility verdicts
- 2-minute strategy video

### Phase 2 — Automation & Protection ✅ Complete
- Complete FastAPI backend with 15+ endpoints across onboarding, premium, trigger, claims, payout, admin
- PostgreSQL schema with PostGIS + TimescaleDB on Supabase
- Celery beat tasks: 30-min trigger polling, Sunday midnight renewal, 12-hr cascade recovery
- All 5 ML model artifacts trained (GLM, LightGBM, Isolation Forest, CBLOF, k-Means) and stored in Git LFS
- Razorpay sandbox UPI payout integration with real webhook handling
- React frontend: worker dashboard with Coverage, Claims, Payouts, Premium History, Predictor tabs
- Admin dashboard with Overview, Workers, Triggers, Claims Review, System Health tabs
- Tamil and Hindi language support via i18next

### Phase 3 — Scale & Optimise ✅ Complete
- Advanced fraud detection: GPS spoofing, cross-platform double-claiming, rain paradox validation
- Instant payout simulation: Razorpay sandbox, real transaction IDs (`pay_` format)
- Intelligent worker dashboard: SHAP explanation display, earnings chart, claim fraud score breakdown
- Intelligent admin dashboard: live loss ratio chart by zone, enrollment adverse selection monitor, model drift alert, slab config staleness alert, trigger simulation console
- Landing page with live pipeline widget showing real-time Chennai zone activity
- Multi-step registration flow with UPI AutoPay Mandate, pincode-to-zone auto-resolution, Fast Demo Fill
- 20+ seeded demo workers across 6 Chennai zones with realistic delivery history, claims, and payouts
- Full Tamil/Hindi/English language toggle
- Final pitch deck and 5-minute walkthrough video

---

## Competitive Differentiation

| Feature | Giggle | SEWA 2023 Pilot | MIC Global | OTT Risk |
|---|---|---|---|---|
| Slab bonus payout modeling | ✅ | ❌ | ❌ | ❌ |
| 3-point spatial weather oversampling | ✅ | ❌ (failed) | ❌ | ❌ |
| 2-of-3 corroboration gate | ✅ | ❌ | Not documented | Not documented |
| 60-second UPI payout | ✅ | ❌ | Not documented | Not documented |
| Fraud ensemble (IF + CBLOF) | ✅ | ❌ | Not documented | Not documented |
| SHAP explanations in vernacular | ✅ | ❌ | ❌ | ❌ |
| GLM cold-start for new workers | ✅ | ❌ | Population mean | Population mean |
| Weekly premium (gig-aligned) | ✅ | Annual | Annual | Not documented |

---

## Business Model

**Revenue:** Weekly SaaS premium (₹49–₹149/week per enrolled worker)
**Distribution:** B2B2C — Zomato/Swiggy embed enrollment in partner app; premium deducted from weekly platform settlement
**Regulatory:** Technology platform operating under IRDAI-licensed insurer partner (Acko / ICICI Lombard) — IRDAI 2023 sandbox framework explicitly enables parametric microinsurance for gig workers
**Reinsurance:** Swiss Re / GIC Re catastrophe backstop for simultaneous large-event payouts
**Loss ratio target:** 60–75%

### Unit Economics (Chennai, Year 1)

| Metric | Conservative | Base Case |
|---|---|---|
| Active workers | 5,000 | 15,000 |
| Average weekly premium | ₹65 | ₹72 |
| Gross annual premium revenue | ₹1.69 Cr | ₹5.62 Cr |
| Loss ratio | 70% | 65% |
| Gross margin | ₹50.7 L | ₹1.97 Cr |
| CAC (B2B2C via platform) | ~₹0 | ~₹0 |

---

## Repository Structure

```
Giggle/
├── backend/
│   ├── app/
│   │   ├── api/               # FastAPI routers (onboarding, premium, claims, payout, admin)
│   │   ├── models/            # SQLAlchemy ORM models (worker, policy, claims, payout, audit, zone, slab)
│   │   ├── ml/
│   │   │   ├── inference.py   # Unified M1/M2 inference + SHAP + affordability cap
│   │   │   ├── model_loader.py
│   │   │   └── artifacts/     # .joblib model files (Git LFS)
│   │   ├── trigger/           # Open-Meteo sampler, AQI monitor, IMD classifier, composite scorer
│   │   ├── fraud/             # IF+CBLOF ensemble, 7-layer behavioral signal pipeline
│   │   ├── payout/            # Slab estimator (M6), cascade model, Razorpay client
│   │   ├── tasks/             # Celery: trigger polling, weekly renewal, cascade recovery, AQI polling
│   │   └── core/              # config.py, database.py, gis.py (GeoPandas), dependencies.py
│   ├── migrations/            # Alembic migration files
│   ├── data/                  # OpenCity Chennai GeoJSON, pincode centroids CSV
│   ├── scripts/
│   │   ├── zone_clustering.py         # M5 offline preprocessing → zone_clusters table
│   │   ├── loss_ratio_simulation.py   # Actuarial loss simulation
│   │   ├── synthetic_data.py          # 10,000 worker-week training records
│   │   ├── train_premium_models.py    # M1 GLM + M2 LightGBM training (run on Kaggle)
│   │   └── seed_demo_data.py          # 20+ demo workers, historical claims, payout records
│   ├── tests/
│   │   ├── test_ml/           # Inference engine tests (13 model + 2 real-model tests)
│   │   └── test_premium/      # API endpoint tests (6 HTTP tests)
│   ├── main.py
│   ├── requirements.txt
│   ├── alembic.ini
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── config/            # api.js (base URL + axios), constants.js (ZONE_NAMES, enums)
│   │   ├── locales/           # en.json, ta.json, hi.json
│   │   ├── pages/             # Landing, Register, Login, Dashboard, Admin
│   │   ├── components/        # Layout, StatusBadge, MetricCard, LoadingSpinner
│   │   └── hooks/             # useWorker.js, useAuth.js
│   ├── index.html
│   ├── tailwind.config.js
│   └── vite.config.js
└── README.md
```

---

## Local Development Setup

### Prerequisites

- Python 3.11+
- Node.js 18+
- Git with Git LFS enabled
- A Supabase account (free tier)
- An Upstash Redis account (free tier)
- A Razorpay test account (free)

### Backend Setup

```bash
git clone https://github.com/Hemachandhar-A/Giggle.git
cd Giggle/backend

# Pull ML model artifacts from Git LFS
git lfs install
git lfs pull

# Create virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Fill in: DATABASE_URL, REDIS_URL, RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET

# Run database migrations
alembic upgrade head

# Seed demo data (20+ workers, historical claims, payout records)
python scripts/seed_demo_data.py

# Start API server
uvicorn main:app --reload --port 8000
# API docs: http://localhost:8000/docs
```

### Celery Workers (separate terminals)

```bash
# Worker process
celery -A app.tasks.celery_app worker --loglevel=info

# Beat scheduler (trigger polling every 30min, Sunday renewal, 12hr cascade check)
celery -A app.tasks.celery_app beat --loglevel=info
```

### Frontend Setup

```bash
cd Giggle/frontend
npm install
npm run dev
# App: http://localhost:5173
```

### Demo Accounts

After running `seed_demo_data.py`, these demo accounts are available:

| Worker | Partner ID | Platform | Zone | Flood Tier | Language |
|---|---|---|---|---|---|
| Priya Sundaram | ZMT001 | Zomato | Velachery (Zone 7) | High | Tamil |
| Ravi Kumar | SWG001 | Swiggy | Anna Nagar (Zone 4) | Medium | Tamil |
| Mohammed Arif | ZMT002 | Zomato | Tambaram (Zone 9) | Medium | Hindi |

Login with partner ID at `/login`. Admin access: username `admin` / password `admin` at `/admin`.

### Running Tests

```bash
cd backend
python -m pytest tests/test_ml/test_models.py -v
python -m pytest tests/test_premium/test_api.py -v

# With coverage
python -m pytest tests/test_ml/ tests/test_premium/ -v \
  --cov=app.ml --cov=app.api.premium --cov-report=term-missing
```

---

## Deployment

### Frontend — Vercel

```bash
cd frontend
npm run build

# Deploy via Vercel CLI
npm install -g vercel
vercel --prod

# Set environment variable in Vercel dashboard:
# VITE_API_BASE_URL = https://your-render-url.onrender.com
```

Or connect your GitHub repo to Vercel directly for automatic deploys on push to `main`.

### Backend — Render

1. Go to [render.com](https://render.com) → New Web Service → Connect GitHub repo
2. Set root directory: `backend`
3. Build command: `pip install -r requirements.txt`
4. Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
5. Add environment variables: `DATABASE_URL`, `REDIS_URL`, `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`

**Celery Worker (second Render service):**
- Start command: `celery -A app.tasks.celery_app worker --loglevel=info`
- Same environment variables

**Celery Beat (third Render service):**
- Start command: `celery -A app.tasks.celery_app beat --loglevel=info`
- Same environment variables

### Database — Supabase

```sql
-- Run in Supabase SQL Editor after creating project
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS timescaledb;
```

Then run Alembic migrations pointing to Supabase DATABASE_URL.

### Redis — Upstash

Create a Redis database at [upstash.com](https://upstash.com) (free tier). Copy the `REDIS_URL` (starts with `rediss://`) to your environment variables.

### ML Model Artifacts — Git LFS

Railway/Render pulls from Git LFS automatically on deploy. If artifacts are missing:
```bash
git lfs install
git lfs pull
```

---

## Scope Boundaries (Per Hackathon Golden Rules)

Giggle covers **income loss from external disruptions only.**

Explicitly excluded:
- Health insurance or hospitalisation claims
- Life insurance or death benefits
- Accident compensation or injury payments
- Vehicle repair or maintenance costs
- Platform technical outages (platform liability, not external disruption)
- Account deactivation by platform
- Algorithmic wage changes
- Secondary platform earnings during a disruption on the covered platform — income continuation, not income loss, and is a claim rejection condition

---

## References and Evidence Base

- SEWA 2023 parametric pilot post-mortem (Climate Resilience for All, Swiss Re)
- IMD rainfall classification thresholds (India Meteorological Department)
- CPCB AQI severity thresholds (Central Pollution Control Board NAMP)
- OpenCity Chennai Flood Hazard Zone data (public government GIS)
- Zomato slab incentive structure (worker community reports + verified press coverage)
- CAS 2024 actuarial study on LightGBM vs GLM (Casualty Actuarial Society)
- CBLOF vs Isolation Forest benchmarking (Springer Nature, 2025)
- LightGBM Tweedie distribution documentation (official LightGBM reference)
- FastAPI performance benchmarks (TechEmpower Framework Benchmarks)
- TimescaleDB vs MongoDB (TimescaleDB official benchmark)
- IRDAI 2023 Regulatory Sandbox framework for parametric microinsurance

---

*Giggle — Built for Priya. Deployed for 15 million workers like her.*
*Guidewire DEVTrails 2026 · Team ShadowKernel · Selected for DemoJam at DevSummit 2026*
