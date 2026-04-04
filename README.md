# Giggle

## AI-Powered Parametric Income Insurance for India's Gig Economy

> **Guidewire DEVTrails 2026** · University Hackathon · Seed -> Scale -> Soar  
> **Persona:** Food Delivery Partners (Zomato and Swiggy), Chennai  
> **Coverage:** Income loss from external disruptions only. Health, life, accident, and vehicle repair are explicitly excluded.

---

## Table of Contents

- [The Problem We're Solving](#the-problem-were-solving)
- [What giggle Is](#what-giggle-is)
- [What Makes giggle Different](#what-makes-giggle-different)
- [Persona: Priya, Zomato Delivery Partner, Velachery, Chennai](#persona-priya-zomato-delivery-partner-velachery-chennai)
- [Application Workflow](#application-workflow)
- [Weekly Premium Model](#weekly-premium-model)
- [Parametric Triggers](#parametric-triggers)
- [AI/ML Integration Plan](#aiml-integration-plan)
- [Platform Decision: Mobile App + Web Admin](#platform-decision-mobile-app--web-admin)
- [Tech Stack](#tech-stack)
- [Development Plan](#development-plan)
- [Competitive Differentiation](#competitive-differentiation)
- [Why This Cannot Be Replicated Without This Specification](#why-this-cannot-be-replicated-without-this-specification)
- [Business Model](#business-model)
- [Repository Structure](#repository-structure)
- [Local Development Setup](#local-development-setup)
- [Scope Boundaries (Per Hackathon Golden Rules)](#scope-boundaries-per-hackathon-golden-rules)
- [References and Evidence Base](#references-and-evidence-base)

---

## The Problem We're Solving

India's 15 million+ platform delivery workers are the last mile of the digital economy. A Zomato rider in Velachery earns ₹20,000–₹30,000 per month — but a single monsoon week can wipe 20–30% of that income with zero safety net.

The problem is not just income loss. It is **how income is structured**. Platform base rates have fallen from ₹40–45/order to ₹15–20/order. Slab bonuses — ₹50 at 7 deliveries, ₹120 at 12, ₹150 at 15, ₹200 at 21+ per day — now constitute a larger fraction of total earnings than base pay. A rain disruption that stops a worker at delivery 10 doesn't just cost 10 deliveries of base pay. It costs the ₹120 slab bonus they were 2 orders away from. **No existing insurance product addresses this.** Not SEWA. Not MIC Global. Not any insurtech in India.

SEWA's 2023 parametric pilot — the only documented attempt — **triggered zero payouts** because city-level IMD weather station data failed to capture hyperlocal conditions. Workers enrolled, paid premiums, and received nothing during the monsoon that should have covered them. giggle's architecture is built specifically to solve the failure modes SEWA documented.

---

## What giggle Is

giggle is a parametric income insurance platform for food delivery workers. When an external disruption — heavy rain, extreme heat, severe pollution, or zone curfew — makes delivery work physically impossible, giggle detects it automatically, computes the worker's true income loss (including the slab bonus they missed), validates the claim against a multi-layer fraud engine, and deposits the payout to their UPI account within 60 seconds. No claim forms. No calls. No waiting.

**The worker does nothing. The system does everything.**

## What Makes giggle Different

- **Slab-aware payout computation** — the world's first parametric insurance product that models India's platform incentive slab structure. A disruption at delivery 10 costs the ₹120 slab bonus the worker was 2 orders away from. Every existing product ignores this. giggle computes it.
- **SEWA's 2023 failure, directly fixed** — SEWA's parametric pilot triggered zero payouts because city-level IMD data missed hyperlocal conditions. giggle queries Open-Meteo at 3 geographic points per zone (centroid + 2 offsets) and takes the maximum reading, expanding spatial coverage to the worker's actual 5–8km delivery radius.
- **2-of-3 source corroboration** — no single weather station controls a payout. Environmental data, geospatial flood zone activation, and platform zone suspension must independently confirm before a claim fires. Eliminates both false positives and the single-point failure that collapsed SEWA's pilot.
- **Isolation Forest + CBLOF fraud ensemble** — CBLOF outperforms Isolation Forest on spatially consistent fraud patterns (silhouette 0.114 vs 0.103, Springer Nature 2025). Running both with max-score output catches ring fraud that either model misses alone.
- **Multilingual-first UX with SHAP explanations in vernacular** — every premium change explained in the worker's primary language. giggle is architected for full regional language support; MVP launches with Hindi and Tamil, covering the two largest delivery-worker language groups. Onboarding, coverage status, and payout notifications all render in the worker's selected language. Without this, enrollment fails regardless of backend sophistication.

---

## Persona: Priya, Zomato Delivery Partner, Velachery, Chennai

**Profile:** 28 years old. Works 10 hours/day, 6 days/week. Average 14 deliveries/day. Monthly earnings: ₹22,000 (₹17,000 base + ₹5,000 incentive slabs). Primary earner for a family of three.

**The disruption reality Priya faces:**
- Chennai Northeast Monsoon (October–December): 265mm in October, 310mm in November. Velachery floods at 30mm/6hr — it is on the GCC's documented high-risk drainage zone.
- Cyclone Michaung (December 2023): 500mm in one day. Velachery was impassable for 3–5 days. Priya lost ₹3,300–₹4,400 in one event with zero compensation.
- On a rain surge day when Zomato offers ₹20 extra per order, Priya loses not just base income — she loses the peak earning opportunity. Her actual loss on a flooded rain day is 40–60% above her average daily baseline.

**What Priya needs from giggle:**
- A weekly premium she can afford (under ₹100/week, below 2.5% of her weekly income).
- Automatic payout she doesn't have to chase.
- An app in her primary language (Tamil for Chennai; Hindi for northern metros) that explains her premium and coverage in plain terms.
- Same-day UPI payout so she can buy groceries on the day the storm hits — not three days later.

---

## Application Workflow

### Onboarding Flow

```
Worker opens giggle app (language auto-selected: Hindi or Tamil based on device locale; MVP supports both)
        ↓
Aadhaar OTP verification (Gridlines API)
        ↓
PAN cross-check (ITD API) + Bank account penny-drop (Razorpay)
        ↓
Zomato/Swiggy Partner ID verified (simulated B2B2C API)
        ↓
Primary platform declared → single-platform policy scope enforced
        ↓
Pincode entered → GIS spatial join (GeoPandas + OpenCity flood hazard GeoJSON)
                  → Flood hazard zone tier assigned (High / Medium / Low)
        ↓
4-week waiting period begins → recency premium multiplier applied (1.5× weeks 1–2, 1.25× weeks 3–4)
        ↓
GLM cold-start pricer computes first weekly premium (zone tier + season + platform)
        ↓
Worker sees: premium amount + SHAP explanation in worker's selected language + 7-day zone risk forecast
        ↓
Weekly premium deducted → Policy active
```

### Active Coverage Flow (Weekly Cycle)

```
Every Sunday midnight:
  → Celery batch job recalculates income baseline (30-day delivery activity)
  → LightGBM model computes next week's premium (10 features including zone cluster,
    season flag, Open-Meteo 7-day disruption probability, activity consistency score)
  → SHAP explanation generated → Push notification sent in worker's selected language (Hindi or Tamil, MVP)
  → Premium deducted from registered UPI VPA
```

### Trigger → Payout Flow (Zero Touch)

```
Every 30 minutes:
  Celery polling job queries:
    [1] Open-Meteo API at 3 geographic points per pincode cluster (centroid + 3km NNE + 3km SSW)
        → Max precipitation reading taken (3-point spatial oversampling)
    [2] IMD threshold classification checked (64.5mm/24h = heavy rain trigger)
    [3] CPCB AQI API for worker's nearest station (>300 = severe trigger)
    [4] IMD temperature data (>45°C = severe heatwave trigger)
    [5] Simulated platform zone availability status (suspended = social trigger)
        ↓
  Trigger signal weighting engine computes composite disruption score:
    Platform zone suspension: 0.40 weight
    Rainfall at IMD threshold: 0.35 weight
    GIS flood zone activation: 0.15 weight
    AQI severe:               0.10 weight
        ↓
  2-of-3 source corroboration gate:
    Score < 0.5 → No trigger
    Score 0.5–0.9 → 2 of 3 sources must confirm → Trigger with proportional payout
    Score > 0.9 → Fast-path (extreme event) → Immediate trigger with audit log
        ↓
  IF TRIGGERED:
    Payout calculation pipeline:
      Base loss = missed_deliveries × worker's observed per-order rate
      Slab delta = P(slab_missed | current_delivery_count, day_of_week, time_slot) × slab_value
      Monthly proximity = P(would_hit_200) × ₹2,000 [activates final 7 days of month only]
      Peak context = 1.2× multiplier if rain surge is active in zone [provisional]
      Total payout capped at verified 7-day income baseline
        ↓
    Fraud scoring pipeline (parallel):
      Isolation Forest + CBLOF ensemble → max anomaly score
      Zone-claim GPS consistency check
      Delivery activity trajectory (7-day pre-event vs 30-day average)
      Cross-platform activity flag
      Enrollment recency signal (max 0.15 weight)
      Claim timing cluster detection
      Rain paradox validator (non-flood zone + elevated order volume = fraud signal)
        ↓
    Tiered routing:
      Score < 0.3 → Auto-approve → Razorpay UPI payout within 60 seconds
      Score 0.3–0.7 → 50% payout + 48-hour review window
      Score > 0.7 → Hold → Fraud review queue
        ↓
    Push notification in worker's selected language (Tamil example below; Hindi equivalent in hi.json):
      "கனமழை கண்டறியப்பட்டது. உங்கள் மண்டலத்தில் வெள்ளம் உறுதிப்படுத்தப்பட்டது.
       ₹420 உங்கள் UPI-க்கு அனுப்பப்பட்டது." 
      (Heavy rain detected. Flooding confirmed in your zone. ₹420 sent to your UPI.)
        ↓
    Cascade check (every 12 hours post-trigger):
      Zone still disrupted? → Continue cascade payout (100% D1, 80% D2, 60% D3, 40% D4–5)
      Recovery confirmed (all 3 sources) → Cascade closes
```

---

## Weekly Premium Model

### Design Rationale

Gig workers operate week-to-week. Weekly premium collection aligned to their earnings cycle removes the barrier of annual or monthly upfront payment. The premium is dynamic — it changes every week based on real forecast risk, not a static annual rate.

**Premium range: ₹49–₹149/week.** At ₹65 average, this is 1.6% of a ₹4,000 weekly income — below the documented 2.5% microinsurance affordability threshold.

### Model Architecture

| Workers | Model | Features Used |
|---|---|---|
| Weeks 1–4 (zero history) | GLM Tweedie (statsmodels) | Zone tier, season flag, platform |
| Week 5+ | LightGBM (objective=tweedie, variance_power=1.5) | 10 features (see below) |

### LightGBM Feature Set

| Feature | Source | Availability |
|---|---|---|
| `flood_hazard_zone_tier` | OpenCity GIS spatial join | Registration |
| `zone_cluster_id` (1–20) | k-Means offline on GIS + rainfall frequency | Registration |
| `platform` | Worker declaration | Registration |
| `delivery_baseline_30d` | Worker input / platform API | Week 1+ |
| `income_baseline_weekly` | Computed: baseline × zone rate | Week 1+ |
| `enrollment_week` | Derived from enrollment date | Registration |
| `season_flag` | Calendar-week lookup (SW/NE monsoon/heat/dry) | Registration |
| `open_meteo_7d_precip_probability` | Open-Meteo Forecast API (daily poll) | Week 1+ |
| `activity_consistency_score` | Std dev of 8-week delivery count series | Week 8+ (default 0.5) |
| `tenure_discount_factor` | Enrollment week + clean claim weeks | Week 5+ |
| `historical_claim_rate_zone` | Aggregated from audit_events by zone cluster per season | Simulation value at launch; credibility-weighted (Z = min(claims/50, 1)) from real data after 3 months |

**Why Tweedie loss:** Insurance weekly loss data is zero-inflated (most weeks, no claim fires). Gaussian loss produces systematically biased estimates. LightGBM's `objective='tweedie'` is explicitly documented for insurance total-loss modeling.

**Why k-means zone clustering:** Chennai has 400–500 active pincodes. LightGBM overfits on high-cardinality sparse categoricals. k-Means on (flood_hazard_tier, historical_rain_frequency) reduces cardinality from 400+ to 20 well-populated clusters.

### SHAP Premium Explanation (Multilingual, Worker-Facing)

**MVP language support: Hindi (primary) and Tamil.** Full regional language expansion (Telugu, Kannada, Bengali, Marathi) is architected via react-i18next locale files and targeted for post-MVP phases as the platform expands to new metros.

Every weekly renewal surfaces a plain-language explanation in the worker's selected language.

Tamil example:
*"உங்கள் கட்டணம் ₹74 இந்த வாரம். காரணம்: உங்கள் மண்டலத்தில் மழை முன்னறிவிப்பு (+₹18), வெள்ள அபாய மண்டலம் (+₹10), 8 வார சுத்தமான பதிவு (-₹8)."*

Hindi example:
*"इस हफ्ते आपका प्रीमियम ₹74 है। कारण: आपके क्षेत्र में बारिश का पूर्वानुमान (+₹18), बाढ़ जोखिम क्षेत्र (+₹10), 8 हफ्तों का साफ रिकॉर्ड (-₹8)।"*

### Adverse Selection Controls

- **4-week waiting period** before first claim eligibility (enforced at pipeline, not UI)
- **Recency multiplier:** 1.5× weeks 1–2, 1.25× weeks 3–4, base from week 5
- **Re-enrollment resets** enrollment_week to zero — the waiting period restarts
- **Rolling baseline floor:** The floor activates only when the pre-event activity drop coincides with a forecast disruption in that zone. Personal inactivity weeks with no disruption forecast use the actual lower baseline — the drop reflects personal circumstances, not pre-event suppression fraud.

---

## Parametric Triggers

### Trigger 1 — Heavy Rainfall (Environmental)

**Data source:** Open-Meteo Forecast & Current Conditions API  
**Resolution:** 1km gridded model, updated hourly  
**Query method:** 3-point spatial oversampling — centroid + 3km NNE + 3km SSW offset. Max precipitation taken. This expands spatial coverage to approximate the worker's 5–8km delivery radius and directly addresses SEWA's 2023 single-station failure.  
**IMD threshold:** 64.5mm/24h (Heavy Rain), 115.6mm/24h (Very Heavy), 204.4mm/24h (Extremely Heavy)  
**Trigger weight:** 0.35 in composite score

### Trigger 2 — Flood Zone Activation (Geospatial)

**Data source:** OpenCity Chennai Flood Hazard Zones (GeoJSON, public)  
**Method:** Worker's flood hazard zone tier (High/Medium/Low) is assigned at onboarding via GeoPandas spatial join. When rainfall crosses the zone's drainage threshold AND the worker's zone is High-risk tier, a GIS-based flood activation event is recorded.  
**Trigger weight:** 0.15 in composite score  
**Key property:** This signal cannot be spoofed — it is derived from the worker's registered zone at onboarding, not from a real-time GPS claim.

### Trigger 3 — Platform Zone Suspension (Operational)

**Data source:** Simulated platform API (mock REST endpoint in demo; B2B2C API in production)  
**Logic:** If the covered platform has suspended deliveries in the worker's registered zone, this constitutes the strongest independent evidence that work is physically impossible.  
**Trigger weight:** 0.40 in composite score (highest single signal)  
**Social disruption gate:** For curfews and bandhs (unverifiable by public API), platform zone suspension is mandatory corroborating evidence. If the platform has not suspended the zone, no social disruption claim fires.

### Trigger 4 — Severe Air Quality (Environmental)

**Data source:** CPCB NAMP AQI API (public, free, station-level)  
**Threshold:** AQI > 300 (Severe, CPCB classification) for 4 consecutive hourly readings  
**Trigger weight:** 0.10 in composite score  
**Deployment relevance:** Primary trigger for Delhi NCR expansion. Chennai-specific for Diwali + vehicle pollution events.

### Trigger 5 — Extreme Heat (Environmental)

**Data source:** Open-Meteo temperature_2m field  
**IMD threshold:** >45°C for 4+ consecutive hours (Severe Heatwave, IMD classification)  
**Trigger weight:** 0.10 independent weight in the composite score, replacing the AQI weight when heat is the active trigger. On a pure heat day: platform suspension (0.40) + rainfall (0.35) + GIS zone (0.15) + heat (0.10) = 1.00. Heat and AQI do not fire simultaneously in the same composite evaluation — whichever is active takes the 0.10 slot. On a pure heat day with no rainfall, the rainfall component contributes zero but the 0.10 heat signal can still contribute toward corroboration alongside platform suspension and GIS zone activation.  
**Deployment relevance:** April–June heat season across all Indian metros. SEWA's validated trigger type — giggle uses the official IMD severe heatwave threshold (45°C) rather than SEWA's initial miscalibrated version.

### 2-of-3 Corroboration Gate

No single source triggers a payout. At least 2 of 3 independent source categories must confirm a disruption:
- Environmental (Open-Meteo + IMD classification = 1 source)
- Geospatial (flood zone activation = 1 source)  
- Operational (platform zone suspension = 1 source)

**Fast-path exception:** Composite score > 0.9 bypasses corroboration (all sources firing simultaneously = unambiguous extreme event). Automatic audit log entry required.

---

## AI/ML Integration Plan

### Model M1 — GLM Cold-Start Pricer
- **Type:** Tweedie GLM (statsmodels)
- **Purpose:** Premium calculation for workers in weeks 1–4 (zero delivery history)
- **Training:** Synthetic dataset (10,000 workers) calibrated against Open-Meteo 80-year historical rainfall frequency per zone tier per season
- **Handoff:** At week 5, LightGBM (M2) takes over automatically

### Model M2 — LightGBM Weekly Premium
- **Type:** Gradient Boosted Decision Tree, `objective='tweedie'`, `tweedie_variance_power=1.5`
- **Purpose:** Dynamic weekly premium for all workers with ≥4 weeks history
- **Training data:** Synthetic base + accumulated real worker-weeks (quarterly retraining)
- **Explainability:** SHAP TreeExplainer — exact values, top-3 features surfaced in worker's selected language (Hindi or Tamil, MVP)
- **Overfitting protection:** k-means zone clustering (M5) replaces raw pincode as feature

### Model M3+M4 — Fraud Detection Ensemble
- **Type:** Isolation Forest (sklearn) + CBLOF (PyOD) — unsupervised at launch
- **Ensemble method:** Both models run on same 4-feature vector; max anomaly score output
- **Why ensemble:** CBLOF silhouette 0.114 vs IF 0.103 in insurance fraud benchmarks (Springer Nature 2025). IF misses spatially consistent ring fraud; CBLOF's cluster-distance approach catches it.
- **Training:** Synthetic worker profiles — 20 normal + 4 fraud archetypes (GPS spoofer, pre-event suppressor, ring registration, cross-platform double-claim)
- **Phase 2 transition:** Semi-supervised upgrade at 200+ confirmed fraud labels from manual review queue

### Model M5 — Zone Cluster Model (k-Means)
- **Type:** k-Means clustering (sklearn), k=20, offline preprocessing
- **Purpose:** Reduce pincode cardinality from 400+ to 20 well-populated risk clusters
- **Features:** (flood_hazard_tier, historical_heavy_rain_frequency_per_year)
- **Data:** OpenCity GeoJSON + Open-Meteo 80-year archive
- **Cost:** One-time offline script, <5 minutes compute, annual refresh

### Model M6 — Slab Probability Estimator
- **Type:** Non-parametric conditional frequency query (SQL, no ML library)
- **Purpose:** Compute P(slab_missed | deliveries_completed_today, day_of_week, time_slot) from worker's own 30-day history
- **Innovation:** This is giggle's most novel feature. Zomato's step-function slab bonuses (₹50@7, ₹120@12, ₹150@15, ₹200@21+) are the dominant income component at current base rates. No existing insurance product models slab loss. giggle computes the actuarially honest counterfactual income loss including the slab the worker was tracking toward.

### Models M7–M9 — Deterministic Behavioral Signals
- **M7 Activity Consistency Scorer:** Rolling std dev of 8-week delivery counts, normalized. LightGBM feature + fraud ensemble input. From UBI behavioral pricing research.
- **M8 Delivery Activity Trajectory:** 7-day pre-event activity ratio vs 30-day average. Conditional baseline floor gate. Zone cohort comparison.
- **M9 Enrollment Recency Signal:** Deterministic formula 1-(week/26). Max 0.15 weight in fraud ensemble.

### Model M10 — Predictive Claims Forecast (Admin)
- **Type:** Deterministic heuristic (not ML)
- **Purpose:** 7-day expected payout forecast for insurer reserve management
- **Method:** P(trigger | forecast_precip) × active_workers × avg_payout, summed across all zones. P values calibrated from Open-Meteo 80-year forecast-vs-observation accuracy.

---

## Platform Decision: Mobile App + Web Admin

**Worker-facing: React Native (Expo managed workflow)**  
The delivery worker persona is mobile-first. Workers manage their entire work life from a smartphone. An insurance product that requires a browser is a product that will not be used. React Native is chosen over Flutter because the team has existing React/JavaScript experience — Flutter's Dart learning curve would consume 2–3 weeks of a 6-week timeline. The Expo managed workflow eliminates native build complexity and allows OTA updates without app store submissions.

**Insurer/admin-facing: React.js (Vite)**  
The loss ratio monitor, disruption heatmap, fraud flag queue, and predictive claims forecast are data-dense web dashboards designed for desktop use by insurance professionals. A mobile app is the wrong medium for these tools. React.js shares component patterns and type definitions with the React Native worker app, enabling code reuse across both interfaces.

**Language:** giggle is architected for multilingual support from day one. The MVP launches with **Hindi and Tamil** — Hindi as the primary language covering the largest delivery-worker population across northern metros, Tamil for the initial Chennai deployment. react-i18next manages string loading from locale files (hi.json, ta.json, en.json). Language is auto-detected from device locale on first launch and can be changed in-app at any time. Post-MVP expansion (Telugu, Kannada, Bengali, Marathi) requires only adding a new locale JSON file — no UI code changes.

---

## Tech Stack

### Overview

| Layer | Technology | Justification |
|---|---|---|
| Worker App | React Native + Expo | Mobile-first persona; team JS experience; Expo OTA updates |
| Admin Dashboard | React.js + Vite | Desktop data-dense UI; shared component patterns with RN |
| i18n | react-i18next | MVP: Hindi + Tamil locale files; English fallback; SHAP string templating; post-MVP expansion via locale JSON only |
| API | FastAPI + Uvicorn | 2,847 req/s async; Pydantic validation; auto Swagger docs |
| Task Queue | Celery + Redis | Scheduled polling, payout chain, retraining jobs |
| ORM + Migrations | SQLAlchemy + Alembic | Typed DB access; schema version control |
| Primary Database | PostgreSQL 16 | ACID compliance; extensible; single engine for all workloads |
| Geospatial | PostGIS extension | ST_Within, ST_Distance, polygon storage; no separate GIS DB |
| Time-Series | TimescaleDB extension | 1,400× faster than MongoDB on time-series queries; native SQL |
| ML — Premium | LightGBM + statsmodels | Tweedie loss; fast categoricals; SHAP native support |
| ML — Fraud | sklearn IsolationForest + PyOD CBLOF | Unsupervised ensemble; insurance fraud benchmark validated |
| ML — Explainability | SHAP TreeExplainer | Exact values for LightGBM; regulatory transparency |
| GIS Processing | GeoPandas | Spatial join at onboarding; pincode centroid → flood zone tier |
| Fraud Graph | NetworkX | Device/IP ring detection; daily batch; connected_components |
| Model Serialization | joblib | LightGBM + GLM + fraud ensemble persistence |
| Weather | Open-Meteo API | 1km resolution; free; no API key; 80-year historical archive |
| AQI | CPCB NAMP API | Public; station-level; free; JSON output |
| KYC | Gridlines / AuthBridge | Aadhaar OTP + PAN + bank penny-drop; standard insurtech KYC |
| Payments | Razorpay SDK (sandbox) | UPI payout API; test mode with real API structure |
| Push Notifications | Firebase FCM | React Native integration via @react-native-firebase/messaging |
| Infrastructure | Docker Compose | 4-container local + demo env; zero microservice overhead |
| CI/CD | GitHub Actions | Test → Build → Deploy pipeline per phase submission |

### Architecture Decision Records

**Why PostgreSQL over MongoDB + InfluxDB + PostGIS separately:**  
Three separate databases for a 4-person team on a 6-week timeline create three operational footprints, three backup strategies, and three connection pools. PostgreSQL with PostGIS and TimescaleDB extensions handles all three workloads — relational/transactional, geospatial, and time-series — on a single engine with full SQL and ACID compliance. TimescaleDB queries are 1,400× faster than MongoDB on time-series data. PostGIS provides ST_Within and spatial indexing that MongoDB cannot replicate without application-layer code.

**Why FastAPI over Django/Flask:**  
The payout pipeline is an I/O-bound async chain: trigger → fraud score → payout compute → Razorpay API → UPI → push notification. Django (743 req/s, 178ms latency) and Flask (892 req/s, 142ms) block the thread on each I/O step. FastAPI's ASGI-native async (2,847 req/s, 45ms) handles the chain concurrently. Pydantic schema validation eliminates input validation bugs at every API boundary.

**Why Docker Compose over microservices:**  
A 4-person team building 44 product features cannot also manage service discovery, distributed tracing, independent deployments, and inter-service auth. Docker Compose runs the full stack (FastAPI, Celery, Redis, PostgreSQL) in 4 containers with a single `docker compose up`. This is the correct trade-off for the hackathon timeline and for a seed-stage startup.

---

## Development Plan

### Rapid Development Strategy

All three phases leverage AI-assisted development (Cursor/GitHub Copilot/Claude) for boilerplate generation, schema scaffolding, and test writing. The team builds the novel differentiated logic (slab probability estimator, 3-point spatial oversampling, CBLOF+IF ensemble, conditional baseline floor), which requires domain knowledge that cannot be AI-generated. Commodity code (API endpoints, CRUD operations, UI components) is agent-assisted.

---

### Phase 1 — Ideation & Foundation (March 4–20) ✅ COMPLETE

**Theme:** Ideate & Know Your Delivery Worker

**Goal:** Define the complete product architecture, evidence-base every design decision, and deliver the Phase 1 required artefacts.

**Deliverables (per use case document):**
- [x] README.md in GitHub repository covering: persona scenarios, workflow, weekly premium model, parametric triggers, platform justification, AI/ML integration plans, tech stack, development plan
- [ ] GitHub repository link (live)
- [ ] 2-minute video (publicly accessible link) — outlining strategy, plan of execution, and prototype with minimal scope

**Phase 1 Work Completed:**
- Persona research and validation against TeamLease, IMD, SEWA, and CPCB documented data
- Complete feature specification (44 features across 8 modules) derived from first-principles analysis
- ML model inventory (M1–M10) with data collection plans, feasibility verdicts, and alternatives
- Competitive evaluation against SEWA 2023, MIC Global, OTT Risk, Bharatsure
- Stress-test analysis (7 critical blind spots identified and resolved)
- Tech stack evaluation with evidence-based selection rationale
- Loss ratio viability analysis using Open-Meteo 80-year historical data
- Cross-domain innovations incorporated: UBI behavioral scoring, emergency alert pre-notification, event-driven activity summary card

---

### Phase 2 — Automation & Protection (March 21–April 4)

**Theme:** Protect Your Worker

**Deliverables (per use case document):**
- [ ] 2-minute demo video (publicly accessible link)
- [ ] Executable source code demonstrating: Registration Process, Insurance Policy Management, Dynamic Premium Calculation, Claims Management

**Sprint 1 (March 21–26) — Core Infrastructure**

```
Day 1–2: Infrastructure setup
  - Docker Compose: FastAPI + Celery + Redis + PostgreSQL with TimescaleDB + PostGIS
  - Alembic migrations: worker_profiles, policies, delivery_history, audit_events,
    trigger_state, zone_clusters, slab_config tables
  - GitHub Actions CI pipeline: lint → test → build on every push

Day 2–3: Data pipeline
  - Open-Meteo Historical API: pull 80-year Chennai rainfall data
  - OpenCity GeoJSON: download flood hazard zone polygons
  - India Post pincode centroids: build lookup table
  - k-Means zone clustering (M5): offline script → zone_clusters table populated
  - Loss ratio simulation: expected event frequency per zone tier per season

Day 3–4: ML models (M1 + M2)
  - Synthetic training dataset generation (10,000 worker profiles from zone distribution)
  - GLM cold-start pricer (M1): statsmodels Tweedie, train + serialize with joblib
  - LightGBM premium model (M2): objective=tweedie, SHAP TreeExplainer, train + serialize
  - FastAPI inference endpoint: /premium/calculate (returns premium + SHAP top-3 features)

Day 4–5: Onboarding flow
  - Aadhaar OTP mock endpoint (simulates Gridlines response)
  - PAN verification mock
  - Platform ID verification mock (simulated Zomato partner database)
  - GIS spatial join at registration (GeoPandas: pincode → flood hazard tier)
  - Device fingerprinting (FingerprintJS in React Native)
  - 4-week waiting period + recency multiplier enforcement in policy activation

Day 5–6: React Native worker app — onboarding screens
  - Multilingual UI with react-i18next: MVP populates hi.json (Hindi) and ta.json (Tamil) for all onboarding strings; language auto-detected from device locale on first launch
  - Onboarding flow: KYC → Platform ID → Pincode → Premium display with SHAP explanation
  - Active coverage status screen
  - Premium history screen
```

**Sprint 2 (March 27–April 4) — Trigger Engine + Claims + Demo**

```
Day 7–8: Parametric trigger engine
  - Open-Meteo 3-point spatial oversampling (centroid + 2 offset points, max precipitation)
  - IMD threshold classification layer (config table: 64.5mm, 115.6mm, 204.4mm thresholds)
  - CPCB AQI hourly polling (Celery beat, 60-minute interval)
  - Platform zone status mock API (simulated suspension endpoint)
  - Trigger signal weighting engine (composite score computation)
  - 2-of-3 corroboration gate + score > 0.9 fast-path

Day 8–9: Payout calculation pipeline
  - Missed delivery estimator (SQL: avg deliveries/hour by day × time slot)
  - Base income loss calculator (missed_count × observed per-order rate)
  - Slab probability estimator (M6): conditional frequency SQL query
    → Daily slab delta (P(slab_missed) × slab_value)
    → Monthly proximity check (final 7 days + within 30 orders of 200)
  - Cascade payout model (state machine: ACTIVE → RECOVERING → CLOSED)
  - 12-hour recovery check Celery job
  - Per-event 5-day cap + weekly coverage ceiling enforcement

Day 9–10: Fraud detection ensemble
  - Synthetic fraud scenario engine: 20 normal + GPS spoofer + pre-event suppressor
    + ring registration + cross-platform double-claim profiles
  - IsolationForest + CBLOF (PyOD) training on synthetic profiles
  - Fraud signal pipeline: zone-claim GPS check, trajectory scorer, recency signal,
    claim timing cluster detector, device/IP graph (NetworkX)
  - Tiered routing: <0.3 auto-approve / 0.3–0.7 partial + review / >0.7 hold

Day 10–11: Razorpay sandbox integration
  - Razorpay Python SDK test mode configuration
  - UPI VPA validation at onboarding (Razorpay VPA verify endpoint)
  - Payout API call in Celery task chain (trigger → fraud → payout → FCM notification)
  - Immutable audit trail (append-only audit_events table, no DELETE permissions)
  - FastAPI webhook handler for Razorpay payout status callbacks

Day 11–13: React Native completion + admin dashboard
  - Worker dashboard: active coverage, this week's premium + SHAP, payout history,
    zone risk indicator (7-day forecast strip), earnings protected tracker
  - Pre-event proactive alert (dual-gate: forecast confidence >70% + historical hit rate >60%)
  - React.js admin dashboard (Vite): loss ratio monitor (Recharts), disruption heatmap
    (React Leaflet + zone GeoJSON), fraud flag queue, predictive claims forecast bar chart

Day 13–14: Integration testing + demo video
  - End-to-end scenario: Worker enrollment → week passes → monsoon trigger fires
    → fraud gate clears → Razorpay payout → push notification → dashboard updates
  - 2-minute demo video: screen recording of full flow
  - Code cleanup, README update for Phase 2 submission
```

---

### Phase 3 — Scale & Optimise (April 5–17)

**Theme:** Perfect for Your Worker

**Deliverables (per use case document):**
- [ ] Advanced fraud detection demonstrating GPS spoofing detection and fake weather claim prevention
- [ ] Instant Payout System (Simulated) via Razorpay test mode
- [ ] Intelligent Dashboard — worker (earnings protected, active coverage) + admin (loss ratios, predictive analytics)
- [ ] 5-minute demo video: screen-capture walkthrough demonstrating a simulated external disruption and automated claim approval + payout
- [ ] Final Pitch Deck (PDF): delivery persona, AI & fraud architecture, business viability of weekly pricing model

**Sprint 3 (April 5–10) — Advanced Fraud + Dashboard Completion**

```
Day 15–16: Advanced fraud features
  - GPS zone consistency check with PostGIS ST_Within (last 5 delivery GPS points
    vs claimed disruption zone polygon)
  - Rain paradox validator (flood zone tier check + order volume elevation check)
  - Cross-platform activity flag (policy scope declaration + secondary platform signal)
  - Device/IP graph analysis (NetworkX connected_components, daily batch job)
  - Rolling baseline floor conditional activation (only when disruption was forecast)
  - Fraud scenario demonstration: trigger GPS spoofer profile → elevated IF+CBLOF score
    → tiered routing to review queue → admin dashboard shows evidence breakdown

Day 17–18: Admin dashboard completion
  - Cascade event monitor (active events, daily burn rate, projected closure, remaining exposure)
  - Model health monitor (RMSE tracking, fraud precision, baseline drift alert)
  - Reinsurance exposure report (max simultaneous payout by zone, catastrophe exposure tier)
  - Worker enrollment/retention metrics (enrollment spikes, lapse trigger analysis)
  - Rolling baseline drift alert (15% zone-level drop triggers slab_config review)
  - slab_config_last_verified alert (30-day admin alert for stale platform pay structure)

Day 18–19: Worker dashboard completion
  - Event-driven weekly activity summary card (renders only on: premium delta >₹10,
    forecast tier change, or payout anniversary)
  - Payout history feed with cascade day grouping (Day 1/Day 2/Day 3 under one event)
  - PDF export of payout history (react-native-pdf for tax/SSC compliance records)
  - Zone risk indicator with confidence decay visual for days 5–7
```

**Sprint 4 (April 10–17) — Demo Simulation + Final Submission**

```
Day 20–21: Cyclone Michaung simulation scenario
  - Scenario engine: simulate Velachery flood event (Open-Meteo historical data replay
    from December 12, 2023 — Cyclone Michaung landfall)
  - Trigger all 5 signals simultaneously → composite score 0.95 → fast-path fires
  - Show 8 enrolled workers: 5 legitimate (Velachery high-risk zone) + 2 fraud profiles
    (GPS spoofer in Adyar, cross-platform worker on Swiggy)
  - Cascade: Day 1 full payout → Day 2 80% → Day 3 60% → Day 4 recovery confirmed → close
  - Fraud queue: GPS spoofer holds for review → admin approves legitimate override
  - Admin dashboard: loss ratio spike, cascade event monitor active, fraud score distribution

Day 21–23: 5-minute demo video production
  - Screen recording: complete worker journey (onboarding → policy → trigger → payout → dashboard)
  - Highlight differentiators on-screen:
    → "3-point spatial oversampling — this is why SEWA failed and we don't"
    → "Slab delta computation — ₹120 bonus she would have missed at delivery 10"
    → "Composite score 0.95 — all 3 sources confirming, fast-path activated"
    → "₹480 to Priya's UPI in 47 seconds"
    → "Fraud profile blocked — GPS in Adyar while claiming Velachery flood"

Day 23–25: Final Pitch Deck (PDF)
  - Slide structure:
    1. The Problem: Priya's rain day (income loss is slab loss, not just base loss)
    2. SEWA's Failure & What We Fixed
    3. giggle: How It Works (trigger → payout flow diagram)
    4. The Slab Innovation (the feature no competitor has)
    5. AI & Fraud Architecture (M1–M10 model inventory visual)
    6. Tech Stack (single PostgreSQL engine + 3 extensions)
    7. Business Viability: Loss Ratio Model (Open-Meteo 80-year data)
    8. Unit Economics: ₹1.69–₹5.62 Cr Gross Revenue Year 1, Chennai
    9. Competitive Differentiation Table
    10. Regulatory Pathway (IRDAI sandbox + licensed insurer white-label model)
    11. Scale: Mumbai, Delhi, Bengaluru, Q-Commerce expansion
    12. Ask: The Seed → Scale journey

Day 25–27: Final QA + submission package
  - Full end-to-end regression test on Docker Compose environment
  - All Phase 3 deliverables verified against use case document checklist
  - Repository tagged v1.0.0-phase3
  - Submission form completed with: GitHub repo link, demo video link, pitch deck PDF
```

---

## Competitive Differentiation

| Dimension | giggle | SEWA 2023 | MIC Global (India) | Any Vibe-Coded Team |
|---|---|---|---|---|
| Weather granularity | 1km + 3-point oversampling | City-level → **zero payouts** | Country aggregates | City-level API call |
| Payout model | Slab-aware (base + delta + monthly) | Flat ₹151–₹1,651 | Flat "inconvenience payment" | Flat amount |
| Fraud detection | IF+CBLOF ensemble + 7 behavioral signals | None | None documented | Basic threshold |
| Trigger design | 2-of-3 corroboration, composite score | Single station | Single index | Single source |
| Multi-day events | Cascade model (5 days, empirical taper) | Single event | Single event | Single event |
| Multi-platform fraud | Policy scope + cross-platform flag | Not addressed | Not applicable | Not addressed |
| Income baseline | Activity-computed (never self-declared) | Self-declared | Self-declared | Self-declared |
| Worker language | Hindi + Tamil (MVP); multilingual architecture for regional expansion; SHAP in vernacular | Not documented | English only | English only |
| Cold-start pricing | GLM base rate weeks 1–4 | Population mean | Population mean | Population mean |

---

## Why This Cannot Be Replicated Without This Specification

- **Slab delta computation** requires knowing Zomato's exact incentive structure from worker community reports — domain knowledge, not documentation
- **3-point spatial oversampling** requires understanding the physics of sub-pincode rainfall variation — meteorological domain knowledge applied to API engineering
- **SEWA 2023 failure analysis** requires reading the documented pilot post-mortem and operationalizing it into a weighted composite score
- **Cross-platform double-claim fraud vector** requires understanding how gig workers actually operate across multiple platforms simultaneously
- **CBLOF + IF ensemble** requires reading the 2025 Springer Nature insurance fraud benchmarking paper — not the first search result
- **GLM cold-start layer** requires understanding the actuarial cold-start problem — not a general ML concept
- **Tweedie loss function** requires knowing that default Gaussian loss produces systematically biased estimates on zero-inflated insurance data

---

## Business Model

**Revenue:** Weekly SaaS premium (₹49–₹149/week per enrolled worker)  
**Distribution:** B2B2C — Zomato/Swiggy embed enrollment in partner app, premium deducted from weekly earnings settlement (identical model to ICICI Lombard + Ola/Uber driver insurance)  
**Regulatory:** Technology platform operating under IRDAI-licensed insurer partner (Acko, Digit, or ICICI Lombard) — IRDAI 2023 sandbox framework explicitly enables parametric microinsurance for gig workers  
**Reinsurance:** Swiss Re / GIC Re catastrophe risk backstop for simultaneous large-event payouts. Without reinsurance, a Cyclone Michaung-scale event — 10,000 active workers in affected zones, 5-day cascade at an average ₹400/day payout — produces ₹2 Cr in simultaneous claims against a weekly premium reserve of approximately ₹32.5 L (5,000 workers × ₹65 average premium). This is a 6× overrun in a single week. Catastrophe reinsurance is a structural product requirement, not an optional add-on. The reinsurance exposure report in the admin dashboard (Feature 6.5) produces the actuarial summary required for this conversation with GIC Re or Swiss Re.
**Loss ratio target:** 60–75% (leaving 25–40% for operations, platform fee, and margin)

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
giggle/
├── backend/
│   ├── app/
│   │   ├── api/               # FastAPI routers (onboarding, premium, claims, payout, admin)
│   │   ├── models/            # SQLAlchemy ORM models
│   │   ├── ml/                # M1–M10 model files, training scripts, joblib artifacts
│   │   ├── trigger/           # Trigger engine, composite scorer, corroboration gate
│   │   ├── fraud/             # IF+CBLOF ensemble, behavioral signal pipeline
│   │   ├── payout/            # Slab estimator, cascade model, Razorpay integration
│   │   └── tasks/             # Celery tasks (polling, weekly renewal, retraining)
│   ├── migrations/            # Alembic migration files
│   ├── data/                  # GeoJSON (OpenCity), pincode centroids, zone clusters
│   ├── scripts/               # zone_clustering.py, loss_ratio_simulation.py, synthetic_data.py, train_all.py
│   └── tests/
├── worker-app/                # React Native (Expo)
│   ├── src/
│   │   ├── screens/           # Onboarding, Dashboard, Coverage, History
│   │   └── locales/           # hi.json (Hindi, MVP primary), ta.json (Tamil, MVP), en.json (fallback); add locale file per language for expansion
├── admin-dashboard/           # React.js (Vite)
│   ├── src/
│   │   ├── pages/             # LossRatio, DisruptionMap, FraudQueue, ClaimsForecast
│   │   └── components/
├── docker-compose.yml
├── .github/workflows/         # CI/CD pipeline
└── README.md
```

---

## Local Development Setup

```bash
# Clone repository
git clone https://github.com/[team]/giggle.git
cd giggle

# Start all services
docker compose up --build

# Run preprocessing (one-time)
docker compose exec backend python scripts/zone_clustering.py
docker compose exec backend python scripts/loss_ratio_simulation.py
docker compose exec backend python scripts/synthetic_data.py

# Train ML models (one-time, after data pipeline)
docker compose exec backend python scripts/train_all.py

# Run database migrations
docker compose exec backend alembic upgrade head

# Worker app
cd worker-app && npx expo start

# Admin dashboard
cd admin-dashboard && npm run dev
```

**Environment variables required:** See `.env.example` in repository root. All API keys for external services have free tiers or sandbox modes — no paid credentials required to run the full demo.

---

## Scope Boundaries (Per Hackathon Golden Rules)

giggle covers **income loss from external disruptions only.**

Explicitly excluded:
- Health insurance or hospitalisation claims
- Life insurance or death benefits  
- Accident compensation or injury payments
- Vehicle repair or maintenance costs
- Platform technical outages (platform liability, not external disruption)
- Account deactivation by platform (platform conduct, not external disruption)
- Algorithmic wage changes (regulatory/advocacy domain, not insurance)
- Secondary platform earnings during a disruption on the covered platform — a worker earning on Swiggy while their Zomato zone is suspended has not lost income; this is income continuation, not income loss, and is a claim rejection condition

---

## References and Evidence Base

All design decisions in this README are grounded in documented evidence:

- SEWA 2023 parametric pilot post-mortem (Climate Resilience for All, Swiss Re)
- IMD rainfall classification thresholds (India Meteorological Department official classification)
- CPCB AQI severity thresholds (Central Pollution Control Board NAMP documentation)
- OpenCity Chennai Flood Hazard Zone data (ward-level, public government GIS)
- Zomato slab incentive structure (documented from worker community reports and verified press coverage)
- CAS 2024 actuarial study on LightGBM vs GLM (Casualty Actuarial Society)
- CBLOF vs Isolation Forest benchmarking (Springer Nature, 2025)
- LightGBM Tweedie distribution documentation (official LightGBM parameter reference)
- FastAPI performance benchmarks (TechEmpower Framework Benchmarks)
- TimescaleDB vs MongoDB time-series performance (TimescaleDB official benchmark)
- UBI behavioral scoring research (PMC 2024, lagged behavioral factors in weekly UBI)
- Insurance proactive alert retention study (InsuranceNewsNet 2024, 25% retention uplift)
- IRDAI 2023 Regulatory Sandbox framework for parametric microinsurance

---

*giggle — Built for Priya. Deployed for 15 million workers like her.*
