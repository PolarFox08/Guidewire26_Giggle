# Giggle — Agent Context & Specification Document
### Guidewire DEVTrails 2026 | Team ShadowKernel
### Version 2.0 | Backend Only | Phase 2

---

## HOW TO USE THIS DOCUMENT

This document is the single source of truth for building Giggle.
Upload it to your agent at the start of every session.

**GitHub Copilot:** Place at `docs/AGENT_CONTEXT.md` → use `@workspace #file:docs/AGENT_CONTEXT.md` in every Copilot Chat session.
**Claude (claude.ai or Claude Code):** Upload this `.md` file as an attachment at session start.
**Cursor:** Reference via `@docs/AGENT_CONTEXT.md` in chat or add to `.cursorrules`.

**Each person uploads:** Part 1 (Common Context) + their own Part (2, 3, 4, or 5).
Do not upload the full document — keep context focused per person.

**Team split overview:**
- **Person 1:** Infrastructure, Onboarding, Policy, Fraud Engine, Admin Endpoints (Part 2)
- **Person 2:** Premium Pricing Models (M1, M2, M5, M7) and Premium API (Part 3)
- **Person 3:** Trigger Engine, Payout Pipeline, Celery Tasks, Claims API (Part 4)

**Agent instructions to include in every prompt:**
> "Do not guess. Do not assume. Every business rule, threshold, formula, and architectural decision is specified in this document. If something is not in this document, ask before implementing."

---

---

# PART 1 — COMMON CONTEXT
### All agents read this. All persons must understand this completely.

---

## 1.1 What Giggle Is

Giggle is a parametric income insurance platform for food delivery workers on Zomato and Swiggy, starting in Chennai. It protects workers against income loss caused by external disruptions — heavy rain, extreme heat, severe air pollution, or zone curfews — that make delivery work physically impossible.

**Core promise:** When a disruption occurs, Giggle detects it automatically, computes the worker's true income loss, validates the claim against a fraud engine, and deposits the payout to the worker's UPI account within 60 seconds. The worker does nothing. The system does everything.

**What is covered:** Income loss from external environmental and social disruptions only.

**What is permanently excluded — never implement features for these:**
- Health insurance or hospitalisation
- Life insurance or death benefits
- Accident compensation or injury payments
- Vehicle repair or maintenance
- Platform technical outages (platform's own liability)
- Account deactivation by platform
- Algorithmic wage changes

---

## 1.2 The Core Domain Problem Giggle Solves

Platform base pay has collapsed from ₹40–45/order to ₹15–20/order over two years. Workers stay because of step-function incentive slab bonuses. Zomato's documented slab structure (from worker community reports, verified across multiple sources):

| Deliveries Completed That Day | Bonus Paid |
|---|---|
| 7 | ₹50 |
| 12 | ₹120 |
| 15 | ₹150 |
| 21+ | ₹200 |

A worker stopped at delivery 10 by flooding does not lose just 10 deliveries of base pay. They lose the ₹120 bonus they were 2 orders away from. This is a step-function loss, not a linear one. No existing insurance product in India models this. Giggle is the first.

**SEWA 2023 Failure — Why Our Architecture Is What It Is:**
SEWA ran India's only documented parametric income insurance pilot for gig workers in 2023. It triggered zero payouts during the monsoon season. Root cause: they used a single city-level IMD weather station 8km from the affected zone (Velachery, Chennai). On the days Velachery flooded, that station showed below-threshold rainfall. Giggle queries Open-Meteo at 3 geographic points per zone (centroid + 3km NNE offset + 3km SSW offset) and takes the maximum precipitation reading. This directly fixes SEWA's documented failure mode. This 3-point oversampling is not optional — it is the core architectural decision.

---

## 1.3 The Worker Persona

**Name:** Priya (representative persona)
**Age:** 28, primary earner for family of three
**Location:** Velachery, Chennai — documented high-risk flood zone (GCC drainage zone)
**Platform:** Zomato delivery partner
**Working pattern:** 10 hours/day, 6 days/week, average 14 deliveries/day
**Monthly income:** ₹22,000 (₹17,000 base + ₹5,000 slab bonuses)
**Documented loss event:** Cyclone Michaung, December 2023 — 500mm rainfall in one day, Velachery impassable for 3–5 days, Priya lost ₹3,300–₹4,400 with zero compensation received
**What she needs:** Weekly premium under ₹100/week (under 2.5% of ₹4,000 weekly income), automatic payout without filing claims, app in Tamil, same-day UPI payout
**Language:** Tamil primary, not English

---

## 1.4 The Four Operational Loops

Giggle operates four concurrent loops that together form the zero-touch parametric insurance engine.

### Loop 1 — Onboarding (one-time per worker)
1. Worker registers on app (Tamil UI)
2. Mock KYC: Aadhaar OTP verification, PAN cross-check, bank account penny-drop via Razorpay
3. Platform ID verified against mock partner database (Zomato or Swiggy)
4. Primary platform declared — single-platform policy scope enforced
5. Pincode entered → GeoPandas spatial join maps pincode centroid to OpenCity Chennai Flood Hazard Zone GeoJSON → flood hazard tier assigned (High / Medium / Low)
6. Device fingerprint captured for ring-registration fraud detection
7. 4-week waiting period begins — no claims eligible until 28 days after enrollment
8. Recency premium multiplier applied: 1.5× for weeks 1–2, 1.25× for weeks 3–4, base rate from week 5
9. GLM cold-start pricer (M1) computes first weekly premium using zone tier + season flag + platform
10. Worker sees premium + SHAP explanation in Tamil + 7-day zone risk forecast
11. Weekly premium deducted from registered UPI VPA
12. Policy active

### Loop 2 — Weekly Renewal (every Sunday midnight via Celery beat)
1. Celery batch job recalculates income baseline from worker's most recent 30-day delivery activity
2. LightGBM model (M2) computes next week's premium using 11 features
3. SHAP TreeExplainer generates explanation, formatted as Tamil-language templated string
4. Push notification sent in Tamil
5. Premium deducted from registered UPI VPA
6. Platform ID re-verified to confirm worker still active on covered platform

### Loop 3 — Trigger Monitoring (every 30 minutes via Celery beat)
1. Open-Meteo API queried at 3 geographic points per active zone cluster (centroid + 3km NNE + 3km SSW) — maximum precipitation reading taken
2. IMD threshold classification applied: 64.5mm/24h = Heavy Rain, 115.6mm/24h = Very Heavy, 204.4mm/24h = Extremely Heavy
3. CPCB AQI API polled hourly — trigger if AQI > 300 (Severe) for 4 consecutive hourly readings
4. Open-Meteo temperature_2m checked — trigger if >45°C for 4+ consecutive hours (IMD Severe Heatwave)
5. Mock platform zone status API checked — zone suspended = strongest single trigger signal
6. Composite score computed using fixed weights (see Section 1.7)
7. 2-of-3 source corroboration gate evaluated
8. If triggered: payout computation pipeline fires, fraud engine runs in parallel
9. Tiered routing based on fraud score
10. Razorpay UPI payout within 60 seconds for auto-approved claims

### Loop 4 — Cascade Recovery Check (every 12 hours post-trigger)
1. Check if disrupted zone is still disrupted (re-query all sources)
2. If still disrupted: continue cascade payout at tapering rates — Day 1: 100%, Day 2: 80%, Day 3: 60%, Day 4: 40%, Day 5: 40%. Maximum 5 cascade days per event
3. Recovery confirmed when all three source categories simultaneously report normal conditions
4. Worker receives push notification in Tamil: coverage restored
5. 24-hour recovery window before new trigger event can start for same zone
6. Annual payout per worker additionally capped at 12× weekly coverage amount

---

## 1.5 The Payout Formula

**Total Payout = Base Loss + Slab Delta + Monthly Proximity Component + Peak Context Multiplier (rain days only)**
Hard cap: total payout ≤ verified 7-day income baseline

### Component 1: Base Loss
- `missed_delivery_count` = average deliveries per hour for this day-of-week and time-slot (from worker's 30-day history) × disruption duration in hours
- `per_order_rate` = worker's observed average per-order rate from declared earnings ÷ delivery count over 30-day window
- If declared per-order rate exceeds 1.5× the zone rate table value, cap it at 1.5× (prevents income inflation fraud)
- `base_loss` = missed_delivery_count × per_order_rate

### Component 2: Slab Delta (Core Innovation — M6)
- At trigger time, system records `deliveries_completed_today`
- Query worker's 30-day delivery history: among all days with same day-of-week and time-slot AND deliveries_completed_at_trigger = N (±1), what fraction ultimately reached the next slab threshold?
- That fraction = P(slab_missed)
- `slab_delta` = P(slab_missed) × slab_bonus_value
- If fewer than 5 matching historical days exist: use zone-level cohort average as fallback (default 30%)

### Component 3: Monthly Proximity (final 7 days of month only)
- Activates ONLY in final 7 calendar days of month AND when worker's cumulative monthly delivery count is within 30 orders of the 200-order monthly threshold
- `P(would_hit_200)` = deliveries_needed ÷ (typical_daily_rate × remaining_days)
- `monthly_proximity` = P(would_hit_200) × ₹2,000

### Component 4: Peak Context Multiplier (rain days only — provisional)
- Activates ONLY when `trigger_type = 'heavy_rain'` AND `zone_order_volume_ratio > 1.20` (zone order volume is above 120% of the 4-week rolling average)
- When active: multiply the sum of (base_loss + slab_delta + monthly_proximity) by **1.2×** before applying cascade taper
- Set `peak_multiplier_applied = TRUE` on the claims record
- Source: Zomato activates rain surcharge pricing (₹20 extra/order) on heavy rain days — documented from platform behaviour. This conservative 1.2× multiplier captures the elevated counterfactual earning opportunity
- This is marked **provisional**: the exact worker-facing surge routing is unconfirmed until platform B2B2C data is available. The multiplier is a model parameter (not a trained coefficient) and can be updated without retraining
- `zone_order_volume_ratio` in demo: derive from delivery_history counts for this zone cluster — count deliveries in zone in last hour vs 4-week rolling hourly average. If no delivery_history data for the zone: default to 1.0 (multiplier does NOT activate)

### Cascade Taper
Applied to total (Base + Slab + Monthly): Day 1 = 1.0×, Day 2 = 0.8×, Day 3 = 0.6×, Day 4 = 0.4×, Day 5 = 0.4×

---

## 1.6 The Fraud Detection Pipeline (Seven Layers)

All seven layers run and produce signals. Final fraud score = max(IF_score, CBLOF_score) combined with behavioral signal adjustments. Output: single score 0.0–1.0.

**Tiered routing based on final fraud score:**
| Score | Action | Worker Notification (Tamil) |
|---|---|---|
| < 0.3 | Auto-approve → Razorpay UPI payout within 60 seconds | "₹420 உங்கள் UPI-க்கு அனுப்பப்பட்டது" |
| 0.3–0.7 | 50% payout released + 48-hour review window | "50% கட்டணம் அனுப்பப்பட்டது. 48 மணி நேரத்தில் முழு மதிப்பாய்வு" |
| > 0.7 | Full hold → fraud review queue for manual admin review | "உங்கள் கோரிக்கை மதிப்பாய்வில் உள்ளது" |

**Layer 1: Isolation Forest + CBLOF Ensemble (M3 + M4)**
4-feature input vector (identical for both models):
- `zone_claim_match` — binary: do any of worker's last 5 GPS delivery points fall within the claimed disruption zone polygon? 1 = match (low anomaly), 0 = no match (maximum anomaly)
- `activity_7d_score` — ratio: deliveries in 7 days before event ÷ (30-day daily average × 7)
- `claim_to_enrollment_days` — integer: days since enrollment at claim time
- `event_claim_frequency` — integer: number of trigger events claimed in last 90 days
Final fraud score = max(IF_score, CBLOF_score). Both models run independently on same input.

**Layer 2: Zone-Claim GPS Consistency (PostGIS ST_Within)**
PostGIS query: do any of worker's last 5 GPS delivery locations fall within the claimed disruption zone polygon or adjacent cluster? Worker claiming Velachery flood with no GPS history in Velachery = maximum anomaly. This cannot be retroactively faked.

**Layer 3: Delivery Activity Trajectory (M8)**
Ratio: deliveries_7d_before_event ÷ (30d_daily_avg × 7). Score below 0.6 = unusual pre-event inactivity.
Critical rule: the conditional baseline floor activates ONLY when pre-event drop coincides with Open-Meteo forecast showing elevated disruption probability for that zone that week. Personal inactivity weeks with no disruption forecast use actual lower baseline — floor must NOT activate for personal inactivity.

**Layer 4: Cross-Platform Activity Flag**
If worker completed deliveries on a non-covered platform during the disruption window on the covered platform, route to fraud review queue. Policy scope is single-platform. Undisclosed secondary platform activity discovered post-claim = policy cancellation.

**Layer 5: Enrollment Recency Signal (M9)**
`enrollment_recency_score` = 1 − (enrollment_week ÷ 26). Maximum contribution to final fraud score capped at 0.15. The 4-week waiting period is the primary adverse selection gate — M9 is secondary signal only.

**Layer 6: Claim Timing Cluster Detector**
Count workers in same zone with simultaneous offline events (within ±15 min of each other) when composite disruption score < 0.5. If > 10 workers show simultaneous offline during low-composite-score conditions = coordinated fraud flag. During genuine severe events composite score is high — the <0.5 gate distinguishes ring fraud from real mass disruption.

**Layer 7: Rain Paradox Validator**
Rain days are peak earning days (elevated order volumes + surge pricing). A worker in a non-flood-tier zone going offline when zone order volume is above 110% of rolling average = strong fraud signal.
Check: (a) Is worker's zone High or Medium flood hazard tier? If No → zone does not physically flood at this rainfall. (b) Is zone order volume elevated (>110% rolling average)? If Yes → orders are flowing for workers who can work. Worker in non-flood zone claiming rain income loss when orders are flowing = fraud signal.

---

## 1.7 Trigger Composite Scoring

Composite score = weighted sum of active signals. Maximum possible = 1.0.

| Signal | Weight | Condition |
|---|---|---|
| Platform zone suspension | 0.40 | Mock platform API returns suspended |
| Rainfall at IMD threshold | 0.35 | ≥ 64.5mm/24h at any of 3 query points |
| GIS flood zone activation | 0.15 | Zone is High/Medium tier AND rainfall triggered |
| AQI severe | 0.10 | CPCB AQI > 300 for 4 consecutive hours |
| Extreme heat | 0.10 | Temperature > 45°C for 4+ consecutive hours |

Note: AQI and heat are mutually exclusive in the same composite evaluation — whichever is active takes the 0.10 slot. They do not stack.

**Corroboration gate decision logic:**
- Score < 0.5 → No trigger
- Score 0.5–0.9 → Requires 2 of 3 independent source categories confirmed (Environmental + Geospatial + Operational). If only 1 source: no trigger.
- Score > 0.9 → Fast-path: automatic trigger, bypass corroboration gate, mandatory audit log entry

**Three independent source categories for corroboration:**
1. Environmental: Open-Meteo + IMD classification (counts as 1 source)
2. Geospatial: OpenCity flood zone activation (counts as 1 source)
3. Operational: Platform zone suspension (counts as 1 source)

---

## 1.8 ML Model Inventory (M1–M10)

| ID | Name | Type | Purpose | Data Regime |
|---|---|---|---|---|
| M1 | GLM Cold-Start Pricer | Tweedie GLM (statsmodels) | Weekly premium for workers in weeks 1–4 | Synthetic 10K workers calibrated from Open-Meteo 80yr |
| M2 | LightGBM Weekly Premium | GBDT, objective=tweedie, variance_power=1.5 | Dynamic weekly premium for workers with ≥5 weeks history | Synthetic base + accumulated real worker-weeks |
| M3 | Isolation Forest | Unsupervised anomaly (sklearn) | Fraud scoring — global outlier detection | Synthetic 28-profile scenario engine |
| M4 | CBLOF | Cluster-Based Local Outlier Factor (PyOD) | Fraud scoring — spatially consistent ring fraud | Same 4-feature vector as M3, max-score ensemble |
| M5 | Zone Cluster Model | k-Means k=20 (sklearn), offline | Reduces pincode cardinality 400+ → 20 risk clusters | OpenCity GIS + Open-Meteo 80yr rain frequency |
| M6 | Slab Probability Estimator | Non-parametric conditional frequency SQL | Computes P(slab_missed) for payout delta | Worker's own 30-day delivery_history (simulated in demo) |
| M7 | Activity Consistency Scorer | Statistical rolling std dev, normalized | LightGBM feature + fraud ensemble behavioral baseline | Worker's 8-week delivery count series (default 0.5 until week 8) |
| M8 | Delivery Activity Trajectory | Statistical ratio + SQL cohort comparison | Pre-event fraud signal + conditional baseline floor gate | 7-day pre-event vs 30-day average + zone cohort |
| M9 | Enrollment Recency Signal | Deterministic formula: 1 − (week/26) | Adverse selection fraud signal | enrollment_week field — always available from registration |
| M10 | Predictive Claims Forecast | Deterministic heuristic (not ML) | Admin 7-day reserve management forecast | Open-Meteo 7-day forecast × active workers × avg payout |

### M1 — GLM Cold-Start Pricer: Why It Exists
New workers have zero delivery history. LightGBM (M2) requires behavioral features that don't exist for them. Without a cold-start solution, M2 falls back to population mean — over-pricing low-risk workers and under-pricing high-risk ones who enroll strategically before monsoon. GLM cold-start is the actuarial industry-standard fix.

Features (3 — all available at registration, zero collection lag):
- `flood_hazard_zone_tier` — High/Medium/Low from OpenCity GIS spatial join
- `season_flag` — SW_monsoon / NE_monsoon / heat / dry from calendar-week lookup
- `platform` — zomato or swiggy, declared at registration

Transition: at week 5, M2 automatically takes over. If M1 and M2 differ by >20% at transition week, admin dashboard flags for review.

Training: Synthetic dataset of 10,000 workers. Premium label derived from actuarial loss ratio simulation: expected_payout = historical heavy rain frequency per zone tier per season (Open-Meteo 80yr) × average payout per worker. Premium = expected_payout ÷ 0.65 (targeting 65% loss ratio). Apply 1.1× climate adjustment factor to expected_payout.

### M2 — LightGBM Weekly Premium: Critical Parameters
**Tweedie loss is non-negotiable.** Default LightGBM uses Gaussian loss which produces systematically biased estimates on zero-inflated insurance data (most weeks have zero claims). LightGBM's own documentation states Tweedie is useful for modeling total loss in insurance.
Parameters: `objective='tweedie'`, `tweedie_variance_power=1.5`

**k-Means zone clustering is non-negotiable.** Chennai has 400–500 active pincodes. LightGBM overfits on high-cardinality sparse categoricals. Replace raw pincode with `zone_cluster_id` (output of M5, k=20).

Complete 11-feature set:

| Feature | Type | Source | Available From |
|---|---|---|---|
| flood_hazard_zone_tier | Categorical H/M/L | OpenCity GIS spatial join | Registration |
| zone_cluster_id (1–20) | Categorical | M5 k-Means output | Registration |
| platform | Categorical | Worker declaration | Registration |
| delivery_baseline_30d | Numeric | Worker input / platform API | Week 1+ |
| income_baseline_weekly | Numeric | Computed: baseline_30d × zone_rate_mid ÷ 30 × 7 | Week 1+ |
| enrollment_week | Integer | Derived from enrollment_date | Registration |
| season_flag | Categorical (4 states) | Calendar-week lookup table | Registration |
| open_meteo_7d_precip_probability | Numeric 0–1 | Open-Meteo Forecast API, daily poll | Week 1+ |
| activity_consistency_score (M7) | Numeric 0–1 | Std dev of 8-week delivery count series, normalized | Week 8+ (default 0.5) |
| tenure_discount_factor | Numeric 0.85–1.0 | enrollment_week + clean_claim_weeks | Week 5+ |
| historical_claim_rate_zone | Numeric | Aggregated from audit_events by zone cluster per season. Simulation value at launch; credibility-weighted Z=min(claims/50,1) from real data after 3 months | Simulation at launch |

Post-inference affordability cap: if computed premium > (weekly_baseline × 0.025), cap at weekly_baseline × 0.025. This is a post-hoc business rule, not a model constraint. For the average Priya-profile worker (₹4,000/week), cap is ₹100. Premium floor: ₹49. Ceiling: ₹149.

SHAP explainability: use SHAP TreeExplainer (exact values, not approximation) after every M2 inference. Format top-3 features by absolute SHAP value into Tamil-language templated strings. Pre-approved templates only — no free-form AI generation.

Tamil SHAP template examples:
- open_meteo_7d_precip_probability: "உங்கள் மண்டலத்தில் மழை முன்னறிவிப்பு (+₹{amount})"
- flood_hazard_zone_tier: "வெள்ள அபாய மண்டலம் (+₹{amount})"
- activity_consistency_score: "{weeks} வார சுத்தமான பதிவு (-₹{amount})"
- tenure_discount_factor: "விசுவாசமான வாடிக்கையாளர் தள்ளுபடி (-₹{amount})"

Hindi equivalents in hi.json locale file.

### M3 + M4 — Fraud Ensemble: Why CBLOF + IF
Isolation Forest uses random tree splitting to detect global outliers — good for workers whose feature vector is unusual compared to the general population. CBLOF computes anomaly by distance to cluster center — superior for organized fraud rings where multiple fraudsters operate in the same geographic zone at the same time. CBLOF silhouette score 0.114 vs IF 0.103 in insurance fraud benchmarking (Springer Nature 2025). Running both with max-score ensemble catches what either model misses alone.

Training data: generate 28 synthetic profiles — 20 normal workers (variable but internally consistent delivery patterns), 3 GPS spoofers (high delivery count but GPS history outside claimed zone), 3 pre-event suppressors (delivery activity drops noticeably in week before forecast monsoon event), 2 ring registration profiles (same device fingerprint, simultaneous offline events filing simultaneous claims). A flat scenario engine where every worker has identical patterns does not test the fraud models. Differentiation must be demonstrable on screen.

### M5 — Zone Cluster Model
One-time offline k-Means clustering. k=20. Features: flood_hazard_tier (numeric 1/2/3) from OpenCity GIS + historical heavy rain frequency per year from Open-Meteo 80-year archive per pincode centroid. Runs once as preprocessing script, populates zone_clusters table. Annual refresh. New pincodes outside original dataset assigned to nearest cluster centroid at onboarding.

---

## 1.9 Complete Database Schema

All tables in PostgreSQL 16 with PostGIS and TimescaleDB extensions on Supabase.

**worker_profiles**
| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | UUID | PRIMARY KEY, DEFAULT gen_random_uuid() | |
| aadhaar_hash | VARCHAR(64) | NOT NULL UNIQUE | SHA-256 of aadhaar number — never store raw |
| pan_hash | VARCHAR(64) | NOT NULL UNIQUE | SHA-256 of PAN |
| platform | VARCHAR(10) | NOT NULL | 'zomato' or 'swiggy' only |
| partner_id | VARCHAR(50) | NOT NULL UNIQUE | Platform-issued partner ID |
| pincode | INTEGER | NOT NULL | 6-digit India pincode |
| flood_hazard_tier | VARCHAR(6) | NOT NULL | 'high', 'medium', or 'low' |
| zone_cluster_id | INTEGER | NOT NULL, FK zone_clusters(id) | M5 output, 1–20 |
| upi_vpa | VARCHAR(100) | NOT NULL | Validated at onboarding via Razorpay |
| device_fingerprint | VARCHAR(128) | NULLABLE | For ring-registration detection |
| registration_ip | VARCHAR(45) | NULLABLE | For IP-graph ring detection |
| enrollment_date | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | |
| enrollment_week | INTEGER | NOT NULL, DEFAULT 1 | Incremented by weekly renewal task |
| is_active | BOOLEAN | NOT NULL, DEFAULT TRUE | |
| language_preference | VARCHAR(5) | NOT NULL, DEFAULT 'ta' | 'ta', 'hi', or 'en' |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | |

**policies**
| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | UUID | PRIMARY KEY | |
| worker_id | UUID | NOT NULL, FK worker_profiles(id) | |
| status | VARCHAR(20) | NOT NULL | 'waiting', 'active', 'suspended', 'lapsed' |
| weekly_premium_amount | NUMERIC(8,2) | NOT NULL | |
| coverage_start_date | TIMESTAMPTZ | NULLABLE | Set when status becomes 'active' |
| coverage_week_number | INTEGER | NOT NULL, DEFAULT 1 | |
| clean_claim_weeks | INTEGER | NOT NULL, DEFAULT 0 | Consecutive weeks without a claim |
| last_premium_paid_at | TIMESTAMPTZ | NULLABLE | |
| next_renewal_at | TIMESTAMPTZ | NULLABLE | Next Sunday midnight |
| model_used | VARCHAR(10) | NULLABLE | 'glm' or 'lgbm' |
| shap_explanation_json | JSONB | NULLABLE | Top 3 SHAP features for current week |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | |

**delivery_history** — TimescaleDB hypertable on recorded_at
| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | UUID | PRIMARY KEY | |
| worker_id | UUID | NOT NULL, FK worker_profiles(id) | |
| recorded_at | TIMESTAMPTZ | NOT NULL | Hypertable partition key |
| deliveries_count | INTEGER | NOT NULL | Count for this time slot |
| earnings_declared | NUMERIC(8,2) | NULLABLE | Self-declared in demo |
| gps_latitude | NUMERIC(10,7) | NULLABLE | Last known GPS for fraud check |
| gps_longitude | NUMERIC(10,7) | NULLABLE | |
| platform | VARCHAR(10) | NOT NULL | 'zomato' or 'swiggy' |
| is_simulated | BOOLEAN | NOT NULL, DEFAULT TRUE | Always TRUE in demo |

**zone_clusters**
| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | INTEGER | PRIMARY KEY | 1 to 20 |
| centroid_lat | NUMERIC(10,7) | NOT NULL | Used for 3-point Open-Meteo queries |
| centroid_lon | NUMERIC(10,7) | NOT NULL | |
| flood_tier_numeric | INTEGER | NOT NULL | 1=low, 2=medium, 3=high |
| avg_heavy_rain_days_yr | NUMERIC(5,2) | NOT NULL | From Open-Meteo 80yr archive |
| zone_rate_min | NUMERIC(6,2) | NOT NULL | Min ₹/order in this zone |
| zone_rate_mid | NUMERIC(6,2) | NOT NULL | Median ₹/order used in payout calc |
| zone_rate_max | NUMERIC(6,2) | NOT NULL | Max ₹/order cap |

**slab_config**
| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | SERIAL | PRIMARY KEY | |
| platform | VARCHAR(10) | NOT NULL | 'zomato' or 'swiggy' |
| deliveries_threshold | INTEGER | NOT NULL | 7, 12, 15, 21 for Zomato |
| bonus_amount | NUMERIC(8,2) | NOT NULL | 50, 120, 150, 200 for Zomato |
| last_verified_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Admin alert if > 30 days old |
| is_active | BOOLEAN | NOT NULL, DEFAULT TRUE | |

Seed data for slab_config at migration: Zomato: (7,₹50), (12,₹120), (15,₹150), (21,₹200). Swiggy: use documented equivalent values.

**trigger_events** — TimescaleDB hypertable on triggered_at
| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | UUID | PRIMARY KEY | |
| zone_cluster_id | INTEGER | NOT NULL, FK zone_clusters(id) | |
| triggered_at | TIMESTAMPTZ | NOT NULL | Hypertable partition key |
| trigger_type | VARCHAR(30) | NOT NULL | 'heavy_rain', 'very_heavy_rain', 'extreme_heavy_rain', 'severe_heatwave', 'severe_aqi', 'platform_suspension' |
| composite_score | NUMERIC(4,3) | NOT NULL | 0.000 to 1.000 |
| rain_signal_value | NUMERIC(8,2) | NULLABLE | mm/24h max of 3-point query |
| aqi_signal_value | INTEGER | NULLABLE | AQI reading |
| temp_signal_value | NUMERIC(5,2) | NULLABLE | °C |
| platform_suspended | BOOLEAN | NOT NULL, DEFAULT FALSE | |
| gis_flood_activated | BOOLEAN | NOT NULL, DEFAULT FALSE | |
| corroboration_sources | INTEGER | NOT NULL | Count of independent source categories confirmed (0–3) |
| fast_path_used | BOOLEAN | NOT NULL, DEFAULT FALSE | |
| status | VARCHAR(20) | NOT NULL, DEFAULT 'active' | 'active', 'recovering', 'closed' |
| closed_at | TIMESTAMPTZ | NULLABLE | |

**claims**
| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | UUID | PRIMARY KEY | |
| worker_id | UUID | NOT NULL, FK worker_profiles(id) | |
| trigger_event_id | UUID | NOT NULL, FK trigger_events(id) | |
| policy_id | UUID | NOT NULL, FK policies(id) | |
| claim_date | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | |
| cascade_day | INTEGER | NOT NULL, DEFAULT 1 | 1 to 5 |
| deliveries_completed | INTEGER | NOT NULL | At time of trigger |
| base_loss_amount | NUMERIC(8,2) | NOT NULL | |
| slab_delta_amount | NUMERIC(8,2) | NOT NULL, DEFAULT 0 | |
| monthly_proximity_amount | NUMERIC(8,2) | NOT NULL, DEFAULT 0 | |
| peak_multiplier_applied | BOOLEAN | NOT NULL, DEFAULT FALSE | |
| total_payout_amount | NUMERIC(8,2) | NOT NULL | After cascade taper and hard cap |
| fraud_score | NUMERIC(4,3) | NOT NULL | 0.000 to 1.000 |
| fraud_routing | VARCHAR(20) | NOT NULL | 'auto_approve', 'partial_review', 'hold' |
| zone_claim_match | BOOLEAN | NULLABLE | PostGIS GPS check result |
| activity_7d_score | NUMERIC(4,3) | NULLABLE | M8 output |
| status | VARCHAR(20) | NOT NULL, DEFAULT 'pending' | 'pending', 'approved', 'partial', 'held', 'rejected' |

**payout_events**
| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | UUID | PRIMARY KEY | |
| claim_id | UUID | NOT NULL, FK claims(id) | |
| worker_id | UUID | NOT NULL, FK worker_profiles(id) | |
| razorpay_payout_id | VARCHAR(100) | NULLABLE | From Razorpay sandbox response |
| amount | NUMERIC(8,2) | NOT NULL | Actual amount sent (may be 50% for partial) |
| upi_vpa | VARCHAR(100) | NOT NULL | Worker's registered UPI VPA |
| status | VARCHAR(20) | NOT NULL | 'initiated', 'processing', 'paid', 'failed' |
| initiated_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | |
| completed_at | TIMESTAMPTZ | NULLABLE | |
| failure_reason | TEXT | NULLABLE | |

**audit_events** — APPEND-ONLY. No UPDATE. No DELETE. Ever.
| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | UUID | PRIMARY KEY | |
| event_type | VARCHAR(50) | NOT NULL | e.g. 'worker_registered', 'trigger_fired', 'payout_initiated', 'fraud_flagged' |
| entity_id | UUID | NOT NULL | worker_id, claim_id, policy_id, trigger_id |
| entity_type | VARCHAR(30) | NOT NULL | 'worker', 'claim', 'policy', 'trigger_event' |
| payload | JSONB | NOT NULL | Full event details |
| actor | VARCHAR(50) | NOT NULL, DEFAULT 'system' | 'system', 'admin', worker_id |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | |

IRDAI requires complete auditability of every policy, trigger, claim, and payout. Implement SQLAlchemy event listener that raises RuntimeError on any before_update event for AuditEvent model. Grant only INSERT on this table at DB level — no UPDATE or DELETE permissions for application role.

---

## 1.10 All Predefined API Endpoints

Do not create endpoints outside this list without team agreement.

**Onboarding (owned by Person 1)**
```
POST /api/v1/onboarding/kyc/aadhaar         — Mock Aadhaar OTP verification
POST /api/v1/onboarding/kyc/pan             — Mock PAN cross-check
POST /api/v1/onboarding/kyc/bank            — Mock bank penny-drop + UPI VPA validation
POST /api/v1/onboarding/platform/verify     — Mock platform partner ID verification
POST /api/v1/onboarding/register            — Complete worker registration (all steps)
GET  /api/v1/onboarding/status/{worker_id}  — Registration + waiting period status
```

**Premium (owned by Person 2)**
```
POST /api/v1/premium/calculate              — Compute weekly premium for a worker (M1 or M2)
GET  /api/v1/premium/history/{worker_id}    — Premium history with SHAP explanations
POST /api/v1/premium/renew                  — Admin: manually trigger renewal for a worker
```

**Policy (owned by Person 1)**
```
GET  /api/v1/policy/{worker_id}             — Active policy details + coverage status
GET  /api/v1/policy/{worker_id}/coverage    — Is coverage active? Days until claim-eligible?
PUT  /api/v1/policy/{worker_id}/suspend     — Admin: suspend a policy
```

**Trigger Engine (owned by Person 3)**
```
GET  /api/v1/trigger/zone/{zone_cluster_id} — Current trigger state for a zone
POST /api/v1/trigger/simulate               — Admin: simulate a disruption event for demo
GET  /api/v1/trigger/active                 — All currently active trigger events
GET  /api/v1/trigger/history                — Past trigger events with composite scores
```

**Claims (owned by Person 3)**
```
GET  /api/v1/claims/{worker_id}             — Worker's full claim history
GET  /api/v1/claims/detail/{claim_id}       — Single claim with all fraud signal breakdown
GET  /api/v1/claims/pending                 — Admin: claims in review queue (fraud 0.3–0.7 and held)
PUT  /api/v1/claims/{claim_id}/resolve      — Admin: approve or reject a held claim
```

**Payout (owned by Person 3)**
```
GET  /api/v1/payout/{worker_id}/history     — Payout history for a worker
POST /api/v1/payout/webhook/razorpay        — Razorpay payout status webhook handler
```

**Fraud (owned by Person 1)**
```
POST /api/v1/fraud/score                    — Internal: score a claim (called by payout pipeline)
GET  /api/v1/fraud/queue                    — Admin: fraud review queue with signal breakdown
GET  /api/v1/fraud/worker/{worker_id}/signals — Fraud signal breakdown for a specific worker
```

**Admin Dashboard (owned by Person 1 — endpoints; data comes from all tables)**
```
GET  /api/v1/admin/dashboard/summary        — Active workers, active triggers, payouts this week, avg fraud score
GET  /api/v1/admin/dashboard/loss-ratio     — Loss ratio over time by zone cluster per month
GET  /api/v1/admin/dashboard/claims-forecast — M10: 7-day predicted claims volume and amount
PUT  /api/v1/admin/slab-config/verify       — Mark slab config as verified (resets 30-day timer)
PUT  /api/v1/admin/slab-config/update       — Update a slab threshold or bonus amount
GET  /api/v1/admin/model-health             — Premium model RMSE, fraud precision, slab staleness alert
GET  /api/v1/admin/enrollment-metrics       — Enrollment spikes, lapse rate, adverse selection indicators
```

**Health**
```
GET  /api/v1/health                         — Service health: API, DB, Redis, Celery all checked
```

---

## 1.11 Tech Stack

| Layer | Technology | Why |
|---|---|---|
| API Framework | FastAPI + Uvicorn | ASGI async: 2,847 req/s at 45ms (TechEmpower benchmarks). The trigger→fraud→payout chain is I/O-bound async — synchronous WSGI frameworks block on each step. Pydantic validation at every boundary. |
| Task Queue | Celery + Redis | 30-min trigger polling, Sunday midnight renewal, 12-hour cascade checks, hourly AQI polling — all Celery beat scheduled tasks. Redis as message broker. |
| ORM + Migrations | SQLAlchemy 2.0 + Alembic | Typed DB access, schema version control per phase. |
| Database | PostgreSQL 16 | Single engine for relational, geospatial (PostGIS), and time-series (TimescaleDB). Eliminates three-database operational overhead. |
| Geospatial | PostGIS extension | ST_Within for GPS zone consistency fraud check. Polygon storage for OpenCity flood hazard zones. |
| Time-Series | TimescaleDB extension | 1,400× faster than MongoDB on time-series queries. Stores precipitation readings, trigger state history, payout event timeseries. Native SQL — no query language change. |
| ML — Premium | LightGBM + statsmodels | LightGBM: native Tweedie loss + SHAP native support. statsmodels: standard GLM implementation for M1 cold-start. |
| ML — Fraud | sklearn IsolationForest + PyOD CBLOF | Both unsupervised — no fraud labels required at launch. Max-score ensemble catches what either model misses. |
| ML — Explainability | SHAP TreeExplainer | Exact (not approximate) values for LightGBM. IRDAI regulatory transparency requirement. |
| GIS Processing | GeoPandas | Pincode centroid → flood zone tier spatial join at onboarding. One-time per worker, not real-time. |
| Fraud Graph | NetworkX | Device/IP ring detection via connected_components. Daily batch job. |
| Model Serialization | joblib | LightGBM, GLM, fraud ensemble — serialized to disk, loaded at FastAPI startup. Stored in Git LFS. |
| Payments | Razorpay SDK (sandbox) | UPI payout API. Test mode uses real API structure + real webhook handling. Only funds are virtual. Hackathon rules explicitly permit sandbox payment systems. |
| Weather | Open-Meteo API | Free, no API key, 1km gridded resolution, 80-year historical archive, hourly real-time updates. |
| AQI | CPCB NAMP API via data.gov.in | Public, free, station-level JSON output. Requires free account at data.gov.in. |
| Push Notifications | Expo Push Notifications | Use `expo-notifications` + Expo push API during development (no Firebase config needed for Expo Go). Switch to Firebase FCM for production build in Phase 3. |

---

## 1.12 Data Sources

| Source | Used For | Access | Status |
|---|---|---|---|
| Open-Meteo Historical API | M1/M2/M5 training, loss ratio simulation, cascade taper calibration | Free, no API key, archive-api.open-meteo.com | ✅ Confirmed free |
| Open-Meteo Forecast API | Trigger engine (every 30 min), M2 feature, M10 forecast, pre-event alert | Free, no API key, api.open-meteo.com | ✅ Confirmed free |
| OpenCity Chennai Flood Hazard GeoJSON | Worker flood tier assignment at onboarding, M2/M5 feature, fraud GPS zone check | Free public government GIS, one-time download from data.opencity.in | ✅ Download and store in backend/data/ |
| India Post Pincode Centroid Table | Pincode → lat/lon mapping for GIS join and Open-Meteo queries | Use Kaggle dataset (data.gov.in has no lat/lon) | ✅ Download CSV from Kaggle, filter to Tamil Nadu |
| CPCB NAMP AQI API | AQI trigger monitoring (Trigger 4) | Free, requires account at data.gov.in | ✅ Register and get API key |
| IMD Thresholds | Trigger classification | Static config values (no API) — 64.5mm heavy, 115.6mm very heavy, 204.4mm extremely heavy, 45°C severe heatwave | ✅ Hardcode in config table |
| Razorpay Sandbox | UPI payout simulation, VPA validation, webhook handling | Free test mode, sign up at dashboard.razorpay.com | ✅ No KYC needed for test keys |
| Mock: Aadhaar OTP KYC | Onboarding verification | Return {"verified": true} from FastAPI mock endpoint | ⚠️ Demo only |
| Mock: PAN verification | Onboarding verification | Return {"verified": true} from FastAPI mock endpoint | ⚠️ Demo only |
| Mock: Platform ID verification | Zomato/Swiggy partner ID check | Seeded list of test partner IDs in database | ⚠️ Demo only |
| Mock: Platform zone suspension | Trigger 3 — highest weight signal | Mock REST endpoint toggled by /trigger/simulate admin endpoint | ⚠️ Demo only |
| Mock: Delivery GPS history | Fraud zone-claim GPS check, M6 slab estimator, M8 trajectory | Seed delivery_history table with synthetic GPS coordinates | ⚠️ Demo only — use case document explicitly permits simulation |
| Synthetic training data | M1, M2, M3+M4 training | Generated by scripts/synthetic_data.py | ✅ No external source needed |

---

## 1.13 Folder Structure

```
Giggle/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── onboarding.py     ← Person 1
│   │   │   ├── premium.py        ← Person 2
│   │   │   ├── policy.py         ← Person 1
│   │   │   ├── trigger.py        ← Person 3
│   │   │   ├── claims.py         ← Person 3
│   │   │   ├── payout.py         ← Person 3
│   │   │   ├── fraud.py          ← Person 1
│   │   │   └── admin.py          ← Person 1
│   │   ├── models/
│   │   │   ├── worker.py         ← Person 1 (all SQLAlchemy ORM models here)
│   │   │   ├── policy.py
│   │   │   ├── delivery.py
│   │   │   ├── zone.py
│   │   │   ├── slab.py
│   │   │   ├── trigger.py
│   │   │   ├── claims.py
│   │   │   ├── payout.py
│   │   │   └── audit.py
│   │   ├── ml/
│   │   │   ├── artifacts/        ← Trained .joblib files (Git LFS)
│   │   │   └── inference.py      ← Person 2 (premium inference)
│   │   ├── trigger/
│   │   │   ├── open_meteo.py     ← Person 3 (3-point spatial oversampling)
│   │   │   ├── imd_classifier.py ← Person 3
│   │   │   ├── aqi_monitor.py    ← Person 3
│   │   │   └── composite_scorer.py ← Person 3
│   │   ├── fraud/
│   │   │   ├── scorer.py         ← Person 1 (IF+CBLOF ensemble inference)
│   │   │   ├── behavioral.py     ← Person 1 (M7, M8, M9 signals)
│   │   │   └── graph.py          ← Person 1 (NetworkX ring detection)
│   │   ├── payout/
│   │   │   ├── calculator.py     ← Person 3 (payout formula + M6)
│   │   │   └── razorpay_client.py ← Person 3
│   │   ├── tasks/
│   │   │   ├── celery_app.py     ← Person 3
│   │   │   ├── trigger_polling.py ← Person 3
│   │   │   ├── weekly_renewal.py ← Person 3
│   │   │   ├── cascade_recovery.py ← Person 3
│   │   │   └── aqi_polling.py    ← Person 3
│   │   └── core/
│   │       ├── config.py         ← Person 1
│   │       ├── database.py       ← Person 1
│   │       ├── gis.py            ← Person 1 (GeoPandas spatial join)
│   │       └── dependencies.py   ← Person 1
│   ├── migrations/               ← Person 1 (all Alembic files)
│   ├── data/
│   │   ├── chennai_flood_hazard.geojson  ← Download once (Person 1)
│   │   └── chennai_pincodes.csv          ← Download once (Person 1)
│   ├── scripts/
│   │   ├── zone_clustering.py    ← Person 2
│   │   ├── loss_ratio_simulation.py ← Person 2
│   │   ├── synthetic_data.py     ← Person 2
│   │   └── train_premium_models.py ← Person 2
│   ├── tests/
│   │   ├── test_api/             ← Person 1
│   │   ├── test_ml/              ← Person 2
│   │   ├── test_trigger/         ← Person 3
│   │   └── test_payout/          ← Person 3
│   ├── main.py                   ← Person 1 (creates and owns)
│   ├── requirements.txt          ← Person 1 creates; all add packages, coordinate via WhatsApp
│   ├── alembic.ini               ← Person 1
│   └── .env.example              ← Person 1
├── docs/
│   └── AGENT_CONTEXT.md          ← This file
├── .gitignore
├── .gitattributes                ← Git LFS config
└── README.md
```

---

## 1.14 Deployment (Free Tier — Full Guide)

**Database: Supabase**
- Sign up at supabase.com (free)
- Create new project → copy DATABASE_URL (postgres://...)
- Go to SQL Editor → run: `CREATE EXTENSION IF NOT EXISTS postgis;`
- Go to SQL Editor → run: `CREATE EXTENSION IF NOT EXISTS timescaledb;`
- Run Alembic migrations from local: `alembic upgrade head` (pointing to Supabase DATABASE_URL)
- Free tier: 500MB storage, 2 compute units — sufficient for demo

**Redis: Upstash**
- Sign up at upstash.com (free)
- Create Redis database → copy REDIS_URL (rediss://...)
- Free tier: 10,000 commands/day — sufficient for demo polling schedule

**Backend API: Railway.app**
- Sign up at railway.app (free tier: 500 hours/month)
- New project → Deploy from GitHub → select repo
- Set root directory to `backend/`
- Add all environment variables from .env.example with real values
- Add Procfile in backend/: `web: uvicorn main:app --host 0.0.0.0 --port $PORT`
- Railway auto-deploys on every push to main branch

**Celery Worker: Railway.app (second service)**
- Same project → New service → same GitHub repo
- Start command: `celery -A app.tasks.celery_app worker --loglevel=info`
- Same environment variables

**Celery Beat: Railway.app (third service)**
- Start command: `celery -A app.tasks.celery_app beat --loglevel=info --scheduler celery.beat:PersistentScheduler`

**Model Artifacts: Git LFS**
- `git lfs install` (Person 1 does once)
- `git lfs track "*.joblib"` → commits .gitattributes
- Each person pushes their .joblib artifacts after training on Kaggle
- Railway pulls from Git LFS automatically on deploy

**Local Development (no Docker)**
```bash
cd backend
python -m venv venv
source venv/bin/activate     # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env         # fill in values from WhatsApp group
alembic upgrade head
uvicorn main:app --reload --port 8000
# Separate terminal:
celery -A app.tasks.celery_app worker --loglevel=info
celery -A app.tasks.celery_app beat --loglevel=info
```

API docs auto-available at: `http://localhost:8000/docs`

---

## 1.15 Non-Negotiable Rules (Do Not Deviate)

1. **LightGBM MUST use** `objective='tweedie'`, `tweedie_variance_power=1.5` — Gaussian loss produces wrong estimates on zero-inflated insurance data. LightGBM's own documentation confirms this.
2. **GLM cold-start MUST be active for enrollment weeks 1–4** — LightGBM has no behavioral features for new workers without it.
3. **Pincode MUST NOT be a raw LightGBM feature** — use zone_cluster_id from M5 (k=20). 400+ pincodes causes documented overfitting.
4. **3-point spatial oversampling MUST be used for every Open-Meteo query** — single centroid = SEWA 2023 failure mode.
5. **Conditional baseline floor MUST activate ONLY when disruption was forecast** — personal inactivity must not trigger the floor.
6. **slab_config_last_verified MUST have 30-day admin alert** — Zomato changes slab structure silently. Stale config produces wrong payout amounts for every single claim.
7. **audit_events MUST be append-only** — revoke UPDATE and DELETE at DB level. IRDAI regulatory requirement.
8. **Waiting period MUST be enforced at pipeline level** — not just at UI. claim_date − enrollment_date must be ≥ 28 days. Re-enrollment resets the clock.
9. **Do not guess or assume any threshold, weight, formula, or business rule** — everything is in this document.

---

## 1.16 Testing Standards

Run `pytest backend/tests/ -v --cov=app` before every PR. Minimum 80% coverage on your module.

Every feature requires all four test categories:
- **Happy path** — valid inputs, correct outputs, correct HTTP status
- **Edge cases** — boundary values (e.g. exactly 64.5mm rainfall), first-week worker, empty history, max payout cap reached, month boundary for monthly proximity
- **Error cases** — invalid inputs return correct HTTP status codes (400, 404, 409, 422)
- **Business rule enforcement** — waiting period blocks claims, fraud routing thresholds, payout cap, cascade day limits, audit append-only

---

## 1.17 Branch and Merge Rules

- `main` — protected. Person 1 merges only. Production-ready code only.
- `dev` — integration branch. All PRs go here first.
- `person1`, `person2`, `person3` — individual working branches.
- Each person only modifies files in their designated folders (see 1.13).
- One PR per completed feature. Do not bundle unrelated changes.
- `requirements.txt` changes: announce in WhatsApp group before pushing. Person 1 adds the package and pushes so nobody overwrites.
- `.env` never committed. Only `.env.example` with dummy values.
- Integration checkpoint: Day 5 — Person 1's onboarding endpoint + Person 2's premium endpoint must work together end-to-end before Person 3 begins payout pipeline.

---

---

# PART 2 — PERSON 1
## Infrastructure, Onboarding, Policy, Fraud Engine, Admin Endpoints

---

## 2.1 What You Own

**Your branch:** `person1`

**Folders you create and own exclusively:**
- `backend/app/models/` — all SQLAlchemy ORM models. Everyone else imports from here.
- `backend/app/api/onboarding.py`
- `backend/app/api/policy.py`
- `backend/app/api/fraud.py`
- `backend/app/api/admin.py`
- `backend/app/fraud/` — entire fraud module (scorer, behavioral signals, graph analysis)
- `backend/app/core/` — config, database session, GIS utility, dependencies
- `backend/migrations/` — all Alembic migration files
- `backend/main.py`
- `backend/tests/test_api/` — API tests for your endpoints

**Folders you must never touch:**
- `backend/app/ml/` — Person 2
- `backend/app/trigger/` — Person 3
- `backend/app/payout/` — Person 3
- `backend/app/tasks/` — Person 3

**Files other persons will import from your code:**
- All SQLAlchemy models (everyone imports from `app.models.*`)
- `app.core.database.get_db` (all persons use for DB sessions)
- `app.core.config.settings` (all persons use for env variables)
- `app.fraud.scorer.compute_fraud_score` and `route_claim` (Person 3 imports for payout pipeline)
- `app.fraud.behavioral.compute_activity_7d_score` (Person 3 imports)

---

## 2.2 Repository Initialisation (You Do This First, Before Anyone Starts)

Create the full folder structure from Section 1.13, set up `.gitignore`, `.env.example`, `requirements.txt` with all packages from the shared list, configure Git LFS for `.joblib` files, create `alembic.ini`, set up `main.py` registering all routers. Push to GitHub. Create all four branches. Share Supabase DATABASE_URL and Upstash REDIS_URL with team via WhatsApp.

Download `chennai_flood_hazard.geojson` from OpenCity and `chennai_pincodes.csv` from Kaggle. Place in `backend/data/`. The pincodes CSV must have exactly these columns: `pincode` (integer), `latitude` (float), `longitude` (float). Filter to Tamil Nadu pincodes only.

Run Alembic initial migration to create all tables. Run slab_config data seed migration to populate Zomato slab values: (7, ₹50), (12, ₹120), (15, ₹150), (21, ₹200).

---

## 2.3 Core Infrastructure to Build

**app/core/config.py:**
Pydantic Settings class reading all environment variables from .env. Variables needed: DATABASE_URL, REDIS_URL, RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET, DATA_GOV_IN_API_KEY, OPEN_METEO_BASE_URL, OPEN_METEO_ARCHIVE_URL.

**app/core/database.py:**
SQLAlchemy engine (pool_pre_ping=True, pool_size=10), SessionLocal, DeclarativeBase. `get_db()` dependency. Connection must work with Supabase's connection pooler.

**app/core/gis.py:**
Load OpenCity GeoJSON and pincode CSV exactly once at module load (not per-request). Expose one function: `get_flood_tier_for_pincode(pincode: int) -> str` returning 'high', 'medium', or 'low'. Also expose `get_zone_cluster_for_pincode(pincode: int) -> int` returning zone_cluster_id 1–20 by finding the nearest zone_clusters centroid. Both functions must handle unknown pincodes gracefully without crashing — return 'low' and nearest cluster respectively.

**BOOTSTRAP DEPENDENCY — READ THIS:** `get_zone_cluster_for_pincode` queries the zone_clusters table which is populated by Person 2's `zone_clustering.py` script. This table will be **empty** until Person 2 runs that script (Day 2–4 per Appendix C). Your `get_zone_cluster_for_pincode` function MUST handle an empty zone_clusters table gracefully: if the table has zero rows, return `cluster_id=1` as the default and log a WARNING: "zone_clusters table is empty — returning default cluster 1. Run scripts/zone_clustering.py first." Do NOT crash or raise an exception. Onboarding will work with the default cluster; correct cluster assignment will apply once Person 2's script has run and is confirmed via the Day 5 integration checkpoint.

**All SQLAlchemy ORM models:**
Implement every table from Section 1.9 exactly. All UUID primary keys. All TIMESTAMPTZ timestamps. NUMERIC precision exactly as specified. Use GeoAlchemy2 Geometry('POINT', srid=4326) for GPS columns in delivery_history. Implement SQLAlchemy before_update event listener on AuditEvent model that raises RuntimeError — this enforces append-only at the ORM layer in addition to DB-level permissions.

**Alembic migrations:**
Initial migration creates all tables. Second data migration seeds slab_config. Third migration grants INSERT-only on audit_events to application role (revokes UPDATE, DELETE). Keep migrations clean and reversible.

---

## 2.4 Onboarding API to Build

All KYC endpoints are mocked. Each must validate input format, return realistic response structure, and write to audit_events.

**POST /api/v1/onboarding/kyc/aadhaar:**
Input validation: Aadhaar number must be 12 digits (spaces allowed in input, strip before validate). OTP must be 6 digits. Return aadhaar_hash (SHA-256 of stripped aadhaar number). Never store or log the raw aadhaar number anywhere.

**POST /api/v1/onboarding/kyc/pan:**
Input validation: PAN format regex `[A-Z]{5}[0-9]{4}[A-Z]{1}`. Return pan_hash (SHA-256).

**POST /api/v1/onboarding/kyc/bank:**
Input: upi_vpa. Validate: must contain '@', minimum 5 characters, maximum 100. Return verified=true, mocked bank_name and account_type.

**POST /api/v1/onboarding/platform/verify:**
Input: platform ('zomato' or 'swiggy'), partner_id. Check partner_id against a seeded test list in the database. If found: return verified=true, partner_name. If not found: return 404. Seed 20 test partner IDs in each platform's list.

**POST /api/v1/onboarding/register:**
This is the main registration endpoint. Receives all collected fields: aadhaar_hash, pan_hash, upi_vpa, platform, partner_id, pincode, device_fingerprint, language_preference.

Business logic in exact order:
1. Check for duplicate aadhaar_hash → 409 Conflict if exists
2. Check for duplicate pan_hash → 409 Conflict if exists
3. Check for duplicate device_fingerprint → if exists, do NOT block registration but write device_fingerprint_collision event to audit_events (ring registration signal)
4. Call `get_flood_tier_for_pincode(pincode)` to assign flood_hazard_tier
5. Call `get_zone_cluster_for_pincode(pincode)` to assign zone_cluster_id
6. Create worker_profiles record
7. Create policies record: status='waiting', coverage_week_number=1, clean_claim_weeks=0
8. Call the premium calculation endpoint internally to get first premium → update policy.weekly_premium_amount and policy.model_used and policy.shap_explanation_json
9. Compute next_renewal_at: next Sunday midnight from today
10. Write worker_registered event to audit_events
11. Return: worker_id, policy summary (status, premium, coverage_start=None, days_until_eligible=28)

---

## 2.5 Policy API to Build

**GET /api/v1/policy/{worker_id}:**
Return: policy status, weekly_premium_amount, coverage_start_date, coverage_week_number, enrollment_week, days_until_claim_eligible (= max(0, 28 − days_since_enrollment_date)), model_used, shap_explanation_json.

**GET /api/v1/policy/{worker_id}/coverage:**
Return: is_coverage_active (bool — status='active' AND days_until_claim_eligible=0), current_week_number, premium_this_week, shap_top3 formatted in worker's language_preference, next_renewal_at.

**PUT /api/v1/policy/{worker_id}/suspend:**
Admin-only endpoint (add admin auth header check). Set policy.status='suspended'. Write policy_suspended event to audit_events. Return updated policy.

---

## 2.6 Fraud Module to Build

**app/fraud/scorer.py — ML inference:**
Load iso_forest_m3.joblib and cblof_m4.joblib from app/ml/artifacts/ at module startup. Expose `compute_fraud_score(zone_claim_match, activity_7d_score, claim_to_enrollment_days, event_claim_frequency) -> float` that runs both models on the 4-feature vector and returns max(IF_score, CBLOF_score) normalized to 0–1. Expose `route_claim(fraud_score: float) -> str` that returns 'auto_approve', 'partial_review', or 'hold' using thresholds 0.3 and 0.7.

For training the models: use Kaggle (see Section 2.7 below). The trained .joblib files are pushed to Git LFS. Do not include training code in the application.

**app/fraud/behavioral.py — deterministic signals:**
- `compute_activity_7d_score(deliveries_7d: int, avg_daily_30d: float) -> float` — ratio capped at 1.5. Default 0.5 if avg_daily_30d is 0.
- `compute_enrollment_recency_score(enrollment_week: int) -> float` — formula: 1 − (enrollment_week / 26), clamped 0–1. Caller applies 0.15 max weight cap.
- `check_rain_paradox(zone_flood_tier: str, zone_order_volume_ratio: float) -> bool` — returns True (fraud signal active) only when zone_flood_tier is 'low' AND zone_order_volume_ratio > 1.10. High/medium tier zones flood legitimately.
- `check_conditional_baseline_floor(activity_dropped: bool, disruption_was_forecast: bool) -> bool` — returns True (floor should activate) only when BOTH conditions are true. Personal inactivity without a forecast disruption must NOT activate the floor.

**app/fraud/graph.py — NetworkX ring detection:**
`detect_ring_registrations(db: Session) -> list[list[str]]` — build undirected graph where each node is a worker_id and edges connect workers sharing the same device_fingerprint or registration_ip. Return list of connected components with size > 1 (each = one suspected ring). This runs as a daily admin batch query, not per-claim.

**app/api/fraud.py:**
- POST /api/v1/fraud/score: Internal endpoint — receives claim data, calls scorer.py and behavioral.py, returns fraud_score and routing decision with all signal breakdown
- GET /api/v1/fraud/queue: Returns all claims with status='held' or fraud_routing='partial_review', ordered by claim_date desc, with fraud_score and signal breakdown
- GET /api/v1/fraud/worker/{worker_id}/signals: Returns all historical fraud signals for a worker — claim_count, avg_fraud_score, zone_claim_match history, enrollment_recency, ring_registration_flag

---

## 2.7 Model Training (Run on Kaggle, Push Artifacts to Git LFS)

**What to train:** iso_forest_m3.joblib and cblof_m4.joblib

**Where to train:** Kaggle notebook (free GPU/CPU). Kaggle URL: kaggle.com → New Notebook → upload this context document as dataset reference.

**Training data specification:** Generate 28 synthetic worker profiles:
- 20 normal workers: variable but internally consistent delivery patterns. Different zones, different day-of-week patterns, different slab-hitting rates. zone_claim_match mostly 1, activity_7d_score between 0.7–1.3, claim_to_enrollment_days between 60–365, event_claim_frequency 0–3.
- 3 GPS spoofers: zone_claim_match = 0 (no GPS match), otherwise normal-looking. High delivery counts claimed but GPS shows device in different zone.
- 3 pre-event suppressors: activity_7d_score very low (0.1–0.4), claim filed immediately after trigger. Enrollment recent (20–60 days).
- 2 ring registration profiles: very short claim_to_enrollment_days (5–20), high event_claim_frequency (5–12).

**Models to train:**
- Isolation Forest: contamination=0.05, n_estimators=200, random_state=42
- CBLOF: contamination=0.05, n_clusters=3, random_state=42 (PyOD library)
- Train both on the same 28-profile × features matrix
- Verify: fraud profiles should score higher than normal profiles on both models
- Verify: silhouette score of CBLOF should be higher than Isolation Forest on test data

**After training:** Download iso_forest_m3.joblib and cblof_m4.joblib. Copy to backend/app/ml/artifacts/. Push via Git LFS. Verify inference function in scorer.py returns sensible scores.

---

## 2.8 Admin Endpoints to Build

**GET /api/v1/admin/dashboard/summary:**
Query: count of active workers, count of active trigger events, count of claims this week, sum of payouts this week, average fraud score this week across all claims. Return all as JSON.

**GET /api/v1/admin/dashboard/loss-ratio:**
Query audit_events and payout_events: group total premiums collected vs total payouts made by zone_cluster_id and month. Compute loss_ratio = payouts ÷ premiums for each group. Return time-series array.

**GET /api/v1/admin/dashboard/claims-forecast (M10):**
Deterministic: query Open-Meteo 7-day forecast for each active zone cluster centroid. For each zone: P(trigger) = 1 if forecast_precipitation_probability > 60% else 0.3. Expected_claims = P(trigger) × active_workers_in_zone × avg_payout_last_30d. Return 7-day array by zone.

**GET /api/v1/admin/slab-config/verify and PUT /api/v1/admin/slab-config/update:**
Verify: query slab_config, check last_verified_at. If any row older than 30 days: return stale_alert=true with which platform is stale and how many days since last verification. Update: accept platform, deliveries_threshold, bonus_amount in body. Update record, reset last_verified_at to NOW(), write slab_config_updated event to audit_events.

**GET /api/v1/admin/model-health:**
Return: premium_model_rmse (null if fewer than 50 claims), fraud_precision (fraction of held claims confirmed fraudulent after manual review — null if fewer than 20 resolved held claims), slab_config_stale (bool), oldest_slab_verified_days (int), baseline_drift_alert (bool — zone-level avg income_baseline_weekly dropped >15% over 4-week window vs 12-week average, excluding weeks with active cascade events).

---

## 2.9 Tests You Must Write (backend/tests/test_api/)

Your tests must cover all four categories from Section 1.16. Specific test cases required:

**Onboarding tests:**
- Valid Aadhaar format → 200 + aadhaar_hash returned
- Aadhaar < 12 digits → 400
- Invalid PAN format → 400
- Valid PAN → 200 + pan_hash returned
- UPI VPA missing '@' → 400
- Duplicate aadhaar_hash registration → 409
- Duplicate device_fingerprint → 200 (allowed but audit event written)
- Known Chennai high-risk pincode (Velachery = 600042) → flood_hazard_tier = 'high'
- Unknown pincode → defaults to 'low', does not crash
- Complete registration → policy created with status='waiting'
- Registration → days_until_claim_eligible = 28

**Policy tests:**
- Worker in waiting period → is_coverage_active = false
- Worker past 28 days → is_coverage_active = true
- Suspended policy → is_coverage_active = false

**Fraud tests:**
- GPS spoofer profile (zone_claim_match=0) → fraud_score > 0.5
- Legitimate worker (zone_claim_match=1, activity_score~1.0, long tenure, low frequency) → fraud_score < 0.3
- Fraud score 0.35 → route_claim returns 'partial_review'
- Fraud score 0.75 → route_claim returns 'hold'
- Rain paradox: low-tier zone + order_volume_ratio=1.15 → True
- Rain paradox: high-tier zone + order_volume_ratio=1.15 → False (legitimate flood zone)
- Conditional baseline floor: activity_dropped=True + disruption_forecast=False → False (must NOT activate)
- Conditional baseline floor: activity_dropped=True + disruption_forecast=True → True
- Audit event update attempt → RuntimeError raised

---

---

# PART 3 — PERSON 2
## Premium Pricing Models (M1, M2, M5, M7) and Premium API

---

## 3.1 What You Own

**Your branch:** `person2`

**Folders you create and own exclusively:**
- `backend/app/ml/inference.py` — premium calculation inference (M1 + M2 combined)
- `backend/app/ml/artifacts/` — trained .joblib model files (via Git LFS)
- `backend/app/api/premium.py` — premium router
- `backend/scripts/zone_clustering.py` — M5 offline preprocessing
- `backend/scripts/loss_ratio_simulation.py` — actuarial loss simulation
- `backend/scripts/synthetic_data.py` — training data generation
- `backend/scripts/train_premium_models.py` — M1 + M2 training
- `backend/tests/test_ml/` — ML model tests

**Folders you must never touch:**
- `backend/app/models/` — Person 1 owns all models
- `backend/app/fraud/` — Person 1
- `backend/app/trigger/` — Person 3
- `backend/app/payout/` — Person 3
- `backend/app/tasks/` — Person 3

**What other persons depend on from your code:**
- Person 3's weekly_renewal.py Celery task calls `app.ml.inference.calculate_premium` to recompute premiums every Sunday
- Person 1's /onboarding/register endpoint calls your /premium/calculate API internally to get the first premium

**Dependency on Person 1:** Your `inference.py` imports SQLAlchemy models from `app.models.*`. Your `premium.py` router uses `app.core.database.get_db`. Person 1 must push their models and database setup before you can wire the API. You can write and test inference.py independently using mocked DB values.

---

## 3.2 What You Are Building

You build the complete ML pricing stack:
1. **M5** — offline k-Means zone clustering (preprocessing script, runs once)
2. **M1** — GLM Tweedie cold-start pricer (statsmodels, for workers in weeks 1–4)
3. **M2** — LightGBM dynamic weekly premium (for workers in weeks 5+)
4. **M7** — Activity consistency scorer (statistical, no separate model file)
5. **inference.py** — unified inference function that routes to M1 or M2 based on enrollment_week
6. **/api/premium.py** — FastAPI router exposing premium endpoints

---

## 3.3 Script 1: zone_clustering.py (M5) — Run This First

**Purpose:** Reduce 400+ Chennai pincodes to 20 risk clusters. Populate zone_clusters table. Generate kmeans_m5.joblib for assigning new pincodes to clusters at onboarding.

**Data inputs:**
- `backend/data/chennai_pincodes.csv` — columns: pincode, latitude, longitude
- `backend/data/chennai_flood_hazard.geojson` — OpenCity Chennai flood hazard polygons
- Open-Meteo Historical API — 80-year precipitation archive per pincode centroid

**What to do:**
1. Load pincodes CSV, filter to Chennai bounding box (lat 12.7–13.3, lon 80.0–80.4), deduplicate by pincode
2. Load OpenCity GeoJSON with GeoPandas, perform spatial join to assign flood_hazard_tier to each pincode centroid
3. For a representative sample of pincodes (50 is enough — do not query all 300, it is slow): query Open-Meteo Historical API (`archive-api.open-meteo.com/v1/archive`) for daily precipitation from 1944-01-01 to 2023-12-31. Count days where precipitation_sum ≥ 64.5mm. Divide by 80 years to get avg_heavy_rain_days_per_year.
4. Run sklearn KMeans(n_clusters=20, random_state=42, n_init=10) on 2-feature matrix: [flood_tier_numeric, avg_heavy_rain_days_yr] after StandardScaler
5. For each cluster: compute centroid lat/lon (mean of member pincodes), mean flood_tier_numeric, mean avg_heavy_rain_days_yr, and zone rate range (zone_rate_min, zone_rate_mid, zone_rate_max derived from flood tier: higher flood risk = higher zone rate in ₹15–40/order range)
6. Insert into zone_clusters table (rows 1–20)
7. Save kmeans_m5.joblib (the trained k-Means model object + the scaler) for use in onboarding's `get_zone_cluster_for_pincode`

**Run this script locally after Alembic migrations are done. Point DATABASE_URL to Supabase.**

---

## 3.4 Script 2: loss_ratio_simulation.py

**Purpose:** Compute expected annual payout per worker per zone tier per season. These values become the premium labels for M1 and M2 synthetic training data.

**Business rules for simulation:**
- Expected payout per disruption day for median worker (Priya profile): Base loss (7 missed deliveries × ₹18/delivery = ₹126) + Slab delta (40% probability of missing ₹120 bonus = ₹48) = ₹174 per disruption day
- Duration multiplier by flood tier: low=1.0×, medium=1.5×, high=2.0× (high-tier zones have longer disruption durations from documented Cyclone Michaung data)
- Climate adjustment factor: 1.1× applied to all expected payouts (forward-looking assumption)
- Target loss ratio: 65% (premium = expected_payout ÷ 0.65)
- Season multipliers for premium adjustment: NE_monsoon=1.4×, SW_monsoon=1.2×, heat=1.1×, dry=0.8×
- Weekly premium = annual target ÷ 52 × season_multiplier
- Hard floor: ₹49/week. Hard ceiling: ₹149/week.

Output: functions that take (avg_heavy_rain_days_yr, flood_tier_numeric, season_flag) and return weekly_premium_target. Used by synthetic_data.py for labels.

---

## 3.5 Script 3: synthetic_data.py

**Purpose:** Generate 10,000 synthetic worker-week records as training data for M1 and M2.

Each record represents one worker-week with:
- All 11 M2 features (see Section 1.8)
- Target label: weekly_premium computed from loss_ratio_simulation
- Add lognormal noise to premium label (std=0.05) to simulate real variance
- For workers with enrollment_week < 5: only generate 3 M1 features (flood_tier, season, platform), other M2 features can be placeholder
- For workers with enrollment_week ≥ 5: generate all 11 features including behavioral ones

Save to `backend/data/synthetic_training_data.csv`.

**Distribution of generated workers should reflect reality:**
- Zone cluster distribution: uniform across 20 clusters (with slight overweight on clusters 1–5 covering high-density Chennai areas)
- Season distribution: NE_monsoon 35%, SW_monsoon 25%, heat 20%, dry 20%
- Platform: 65% zomato, 35% swiggy
- Enrollment week: uniform 1–52
- Flood tier: 30% low, 40% medium, 30% high

---

## 3.6 Script 4: train_premium_models.py — Run on Kaggle

**Why Kaggle:** Fetching 80-year Open-Meteo archive for 50 pincode samples is slow locally. Kaggle's persistent compute + no rate limit issues makes this faster. Also, LightGBM training on 10,000 records is instant but keeping it on Kaggle makes reproducibility easy.

**Upload to Kaggle:** Upload `synthetic_training_data.csv` as a Kaggle dataset. Create new notebook. Upload this context document as reference.

**M1 — GLM Tweedie Cold-Start:**
- Training data: filter synthetic_training_data to enrollment_week < 5 (these workers have only 3 features)
- Features: flood_hazard_zone_tier, season_flag, platform (encode all as ordinal integers)
- Target: weekly_premium
- Model: statsmodels GLM with family=Tweedie(var_power=1.5, link=Log())
- Validate on holdout: RMSE should be < ₹15
- Save as glm_m1.joblib — must save the GLM result object + all LabelEncoders together as a dict

**M2 — LightGBM Weekly Premium:**
- Training data: filter to enrollment_week ≥ 5
- Features: all 11 features from Section 1.8
- Target: weekly_premium
- Model: LGBMRegressor(objective='tweedie', tweedie_variance_power=1.5, n_estimators=500, learning_rate=0.05, num_leaves=31, random_state=42)
- Categorical features: flood_hazard_zone_tier, platform, season_flag — pass as category dtype
- Use early stopping (patience=50) with validation set (20% holdout)
- Validate: RMSE < ₹12, no negative predictions
- Generate SHAP TreeExplainer and verify it computes values for a sample input
- Save as lgbm_m2.joblib, shap_explainer_m2.joblib, lgbm_m2_feature_list.joblib

**Download all .joblib files from Kaggle. Place in backend/app/ml/artifacts/. Push via Git LFS.**

---

## 3.7 app/ml/inference.py — Unified Premium Calculation

This is the main file Person 3's weekly renewal task and Person 1's onboarding endpoint will call.

**Single function signature:**
`calculate_premium(enrollment_week, flood_hazard_zone_tier, zone_cluster_id, platform, season_flag, delivery_baseline_30d, income_baseline_weekly, open_meteo_7d_precip_probability, activity_consistency_score, tenure_discount_factor, historical_claim_rate_zone, language) -> dict`

**What it must return:**
- `premium_amount` — final premium after recency multiplier and affordability cap, in ₹, rounded to 2 decimal places
- `model_used` — 'glm' or 'lgbm'
- `recency_multiplier` — 1.5, 1.25, or 1.0
- `shap_top3` — list of 3 Tamil/Hindi formatted explanation strings (empty list for GLM)
- `affordability_capped` — boolean

**Logic inside:**
1. Compute recency_multiplier: enrollment_week ≤ 2 → 1.5, ≤ 4 → 1.25, else 1.0
2. If enrollment_week < 5: use M1 GLM. Else: use M2 LightGBM.
3. Run inference. Get raw_premium.
4. Multiply by recency_multiplier.
5. Apply affordability cap: min(raw × recency, income_baseline_weekly × 0.025)
6. Apply floor ₹49 and ceiling ₹149.
7. For M2 only: run SHAP TreeExplainer, get top-3 features by absolute SHAP value, format into Tamil strings using pre-approved templates from Section 1.8. Return as shap_top3.
8. Load all model files at module import time (not per-call).

---

## 3.8 app/api/premium.py — Premium Router

**POST /api/v1/premium/calculate:**
Input: worker_id. Query worker_profiles and policies tables for all needed features. Call `calculate_premium(...)` from inference.py. Update policies table with new premium, model_used, shap_explanation_json. Write premium_calculated event to audit_events. Return full inference result.

**GET /api/v1/premium/history/{worker_id}:**
Query policies table for historical premium records. Return array of {week_number, premium_amount, model_used, shap_explanation_json, calculated_at}.

**POST /api/v1/premium/renew:**
Admin endpoint. Takes worker_id. Triggers premium recalculation immediately (outside the Sunday batch). Calls same logic as /calculate. Returns updated premium.

Also implement a utility function `get_current_season() -> str` based on current month:
- June–September → 'SW_monsoon'
- October–December → 'NE_monsoon'
- March–May → 'heat'
- January–February → 'dry'

---

## 3.9 Tests You Must Write (backend/tests/test_ml/)

**Model behaviour tests:**
- enrollment_week=3 → model_used='glm'
- enrollment_week=6 → model_used='lgbm'
- LightGBM model object: verify objective attribute is 'tweedie'
- 100 random valid inputs → all premium_amount values between ₹49 and ₹149
- income_baseline_weekly=1000 (low income worker) → premium ≤ ₹25 (2.5% cap applied)
- income_baseline_weekly=1000 → affordability_capped=True
- High flood tier + NE_monsoon + enrollment_week=10 → higher premium than low tier + dry + enrollment_week=10
- enrollment_week=1 → recency_multiplier=1.5, premium higher than enrollment_week=10 (same other inputs)
- enrollment_week=3 → recency_multiplier=1.25
- enrollment_week=5 → recency_multiplier=1.0
- Tamil language → shap_top3 contains Tamil strings (check for Tamil characters in output)
- SHAP top3 list has exactly 3 items for M2
- SHAP top3 list is empty for M1
- season=NE_monsoon, same zone → higher premium than season=dry

**API endpoint tests:**
- POST /calculate with valid worker_id → 200, premium_amount in response
- POST /calculate with unknown worker_id → 404
- GET /history with valid worker_id → 200, array response

**Data validation tests:**
- synthetic_training_data.csv: verify 10,000 rows, no nulls in required columns, all weekly_premium between ₹49 and ₹149

---

---

# PART 4 — PERSON 3
## Trigger Engine, Payout Pipeline, Celery Tasks, Claims API

---

## 4.1 What You Own

**Your branch:** `person3`

**Folders you create and own exclusively:**
- `backend/app/trigger/` — entire trigger engine (Open-Meteo 3-point query, IMD classifier, AQI monitor, composite scorer)
- `backend/app/payout/` — payout calculator (M6 slab estimator, cascade model, Razorpay client)
- `backend/app/tasks/` — all Celery tasks (trigger polling, weekly renewal, cascade recovery, AQI polling)
- `backend/app/api/trigger.py`
- `backend/app/api/claims.py`
- `backend/app/api/payout.py`
- `backend/tests/test_trigger/`
- `backend/tests/test_payout/`

**Folders you must never touch:**
- `backend/app/models/` — Person 1
- `backend/app/ml/` — Person 2
- `backend/app/fraud/` — Person 1
- `backend/app/core/` — Person 1
- `backend/migrations/` — Person 1

**What you import from other persons:**
- From Person 1: `app.models.*` (all SQLAlchemy models), `app.core.database.get_db`, `app.core.config.settings`, `app.fraud.scorer.compute_fraud_score`, `app.fraud.scorer.route_claim`, `app.fraud.behavioral.compute_activity_7d_score`
- From Person 2: `app.ml.inference.calculate_premium` (called in weekly_renewal Celery task)

**Integration checkpoint with Person 1:** On Day 5, Person 1 must have worker_profiles, policies, zone_clusters, audit_events models and get_db, fraud scorer all working. You can build trigger engine and payout calculator independently using mocked model objects before Day 5, then wire real imports after.

---

## 4.2 Trigger Engine to Build

### app/trigger/open_meteo.py — 3-Point Spatial Oversampling

This is the most critical architectural component. Single centroid query = SEWA 2023 failure. Must query exactly 3 points.

**Three query points per zone cluster:**
1. Centroid: (centroid_lat, centroid_lon) from zone_clusters table
2. NNE offset: centroid + 3km at bearing 22.5° (north-northeast)
3. SSW offset: centroid + 3km at bearing 202.5° (south-southwest)

**Bearing-to-coordinate offset formula:** Use spherical Earth calculation (R=6371km). Given (lat, lon, bearing_degrees, distance_km), compute new (lat, lon) using standard great-circle bearing formula. This must be a pure function with no external dependency.

**Open-Meteo query per point:**
- URL: `https://api.open-meteo.com/v1/forecast`
- Parameters: latitude, longitude, hourly=precipitation,temperature_2m, timezone=Asia/Kolkata, forecast_days=1, past_days=1
- Timeout: 15 seconds per request
- Handle failures gracefully: if a point query fails, log the failure but continue with remaining points

**Result:** Return max precipitation (sum of last 24h across all successful points) and max temperature (max 2m temperature across all successful points). If fewer than 2 of 3 points succeed, return result with a `degraded=True` flag.

**Historical query function (used by Person 2's scripts only):**
Separate function for Open-Meteo archive API (`archive-api.open-meteo.com/v1/archive`) used by zone_clustering.py to fetch 80-year rainfall history per pincode centroid.

### app/trigger/imd_classifier.py — Static Thresholds Config

Store IMD thresholds as constants — these are official government published values, do not modify:
- Heavy Rain: ≥ 64.5 mm/24h
- Very Heavy Rain: ≥ 115.6 mm/24h
- Extremely Heavy Rain: ≥ 204.4 mm/24h
- Severe Heatwave: ≥ 45°C for 4+ consecutive hours

CPCB AQI threshold: > 300 (Severe classification) for 4 consecutive hourly readings.

Expose `classify_rainfall(precip_24h_mm: float) -> dict` returning triggered (bool), category (str or None), signal_weight (float, 0.35 if triggered else 0.0).
Expose `classify_heat(max_temp_c: float) -> dict` returning triggered (bool), signal_weight (0.10 if triggered else 0.0).

### app/trigger/aqi_monitor.py — CPCB AQI

Poll CPCB NAMP API via data.gov.in. Endpoint: `https://api.data.gov.in/resource/3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69?api-key={DATA_GOV_IN_API_KEY}`. Returns last recorded reading per monitoring station.

Store hourly AQI readings in a simple in-memory dict keyed by zone_cluster_id (or persist to a small cache table). The AQI trigger requires 4 consecutive hourly readings above 300 — maintain a rolling buffer of last 4 readings per zone. Trigger activates only when all 4 are > 300.

For Chennai demo: AQI rarely hits 300+. The AQI trigger is primarily relevant for Delhi NCR expansion. In demo, the mock platform suspension + rainfall triggers are the primary demonstration signals.

### app/trigger/composite_scorer.py — Corroboration Gate

Implement `compute_composite_score(rainfall_triggered, rainfall_weight, gis_flood_activated, platform_suspended, aqi_triggered, heat_triggered) -> dict`.

Return dict with: composite_score (0.000–1.000), sources_confirmed (0–3), fast_path_used (bool), decision ('no_trigger', 'trigger_corroborated', 'trigger_fast_path').

Scoring rules (exactly as specified in Section 1.7):
- platform_suspended contributes 0.40
- rainfall_triggered contributes rainfall_weight (0.35)
- gis_flood_activated contributes 0.15
- aqi_triggered AND NOT heat_triggered contributes 0.10
- heat_triggered contributes 0.10
- AQI and heat are mutually exclusive — heat takes precedence if both are true

Source category counting for corroboration:
- Environmental = 1 source if rainfall OR aqi OR heat triggered
- Geospatial = 1 source if gis_flood_activated
- Operational = 1 source if platform_suspended

Decision rules: score < 0.5 → no_trigger. Score 0.5–0.9 AND sources_confirmed < 2 → no_trigger. Score 0.5–0.9 AND sources_confirmed ≥ 2 → trigger_corroborated. Score > 0.9 → trigger_fast_path (fast_path_used=True).

---

## 4.3 Payout Pipeline to Build

### app/payout/calculator.py — Payout Formula

Implement `compute_payout(worker, deliveries_completed_today, disruption_duration_hours, cascade_day, db) -> dict`.

**Step 1 — Base Loss:**
- Query worker's delivery_history for last 30 days: compute avg deliveries per hour for current day_of_week + time_slot (morning = before 12:00, afternoon = 12:00–17:00, evening = after 17:00)
- missed_deliveries = avg_hourly_deliveries × disruption_duration_hours
- Get zone_rate_mid from zone_clusters table for this worker's zone_cluster_id
- Compute declared_per_order_rate from delivery_history: avg(earnings_declared / deliveries_count) over last 30 days — if no declared earnings: use zone_rate_mid
- Apply cap: if declared_per_order_rate > zone_rate_mid × 1.5, use zone_rate_mid × 1.5
- base_loss = missed_deliveries × declared_per_order_rate

**Step 2 — Slab Delta (M6 SQL query):**
- Get next slab threshold above deliveries_completed_today from slab_config table for this worker's platform — the lowest threshold > deliveries_completed_today where is_active=TRUE
- If no higher threshold exists: slab_delta = 0 (already hit highest slab)
- Query delivery_history for last 30 days: among days with same day_of_week AND total daily deliveries between (deliveries_completed_today − 1) and (deliveries_completed_today + 1): what fraction of those days had final daily total ≥ next_threshold?
- That fraction = P(slab_missed)
- If fewer than 5 matching days: use default P(slab_missed) = 0.30
- slab_delta = P(slab_missed) × slab_bonus_value

**Step 3 — Monthly Proximity:**
- Check: is today in the final 7 days of the calendar month? If No: monthly_proximity = 0.
- Check: is worker's cumulative monthly delivery count within 30 orders of 200? If No: monthly_proximity = 0.
- deliveries_needed = 200 − cumulative_monthly_deliveries
- typical_daily_rate = avg daily deliveries from 30-day history
- remaining_days = days until month end
- P(would_hit_200) = min(1.0, (typical_daily_rate × remaining_days) / deliveries_needed) if deliveries_needed > 0 else 0
- Wait — if deliveries_needed ≤ 0: worker already at or past 200 threshold, monthly_proximity = 0
- monthly_proximity = P(would_hit_200) × ₹2,000

**Step 3b — Peak Context Multiplier (rain days only):**
- Check: is `trigger_type = 'heavy_rain'`? If No: skip (multiplier = 1.0, peak_multiplier_applied = False).
- Check: compute `zone_order_volume_ratio` = count of delivery_history rows for this zone_cluster_id in the last 60 minutes ÷ rolling average of same hourly window over the last 4 weeks. If insufficient history: use 1.0 (multiplier does NOT activate).
- If trigger_type is heavy_rain AND zone_order_volume_ratio > 1.20: apply 1.2× multiplier to (base_loss + slab_delta + monthly_proximity). Set `peak_multiplier_applied = True`.
- Otherwise: multiplier = 1.0, peak_multiplier_applied = False.
- This step runs BEFORE cascade taper (Step 4) so cascade taper is applied on top of the multiplied amount.

**Step 4 — Apply Cascade Taper:**
Multipliers: day 1=1.0, day 2=0.8, day 3=0.6, day 4=0.4, day 5=0.4. Days 6+: do not pay (cascade max is 5 days — close trigger event).
total_before_cap = (base_loss + slab_delta + monthly_proximity) × peak_context_multiplier × cascade_multiplier

**Step 5 — Hard Cap:**
weekly_baseline = worker's income_baseline_weekly from policies table (or compute from 30-day history if null).
final_payout = min(total_before_cap, weekly_baseline). Floor at ₹0.

Return dict with all components: base_loss, slab_delta, monthly_proximity, cascade_day, cascade_multiplier, total_payout, weekly_baseline_cap, and a breakdown_json with all intermediate values for audit trail.

### app/payout/razorpay_client.py — Razorpay Sandbox

Set up Razorpay Python SDK with test API keys from config. Implement:
- `validate_upi_vpa(vpa: str) -> bool` — format validation (contains '@', length 5–100) plus optional Razorpay VPA verify call
- `initiate_upi_payout(vpa: str, amount_rupees: float, claim_id: str) -> dict` — call Razorpay Payout API in test mode. Convert amount to paise (×100). Return {success, payout_id, status} or {success: False, error}

Razorpay test mode uses the same API endpoint and structure as production. RazorpayX test mode has its own dummy balance. No real money moves. Payout ID will start with 'pout_' in test mode.

---

## 4.4 Celery Tasks to Build

### app/tasks/celery_app.py

Configure Celery with Redis broker. Register all four tasks. Set beat schedule:
- trigger polling: every 1800 seconds (30 minutes)
- weekly renewal: crontab(hour=0, minute=0, day_of_week='sunday') — Sunday midnight IST
- cascade recovery check: every 43200 seconds (12 hours)
- AQI polling: every 3600 seconds (1 hour)

Timezone: Asia/Kolkata

### app/tasks/trigger_polling.py

Main Celery task `poll_all_zones()`:
1. Query all zone_clusters (id, centroid_lat, centroid_lon, flood_tier_numeric)
2. For each zone: call open_meteo 3-point query, classify rainfall and heat, get stored AQI status, get mock platform suspension status, run composite scorer
3. If decision is trigger_corroborated or trigger_fast_path:
   - Check if active trigger already exists for this zone — if yes, skip (cascade_recovery handles continuation)
   - Create trigger_events record with all signal values
   - Write trigger_fired event to audit_events
   - Call initiate_zone_payouts task asynchronously with trigger_event_id and zone_cluster_id

`initiate_zone_payouts(trigger_event_id, zone_cluster_id)`:
1. Query all active workers in this zone: join worker_profiles + policies where zone_cluster_id matches AND policy.status='active' AND is_active=TRUE
2. For each worker:
   - Check waiting period: enrollment_date + 28 days ≤ today — skip if not yet eligible
   - Call compute_payout from calculator.py
   - Query delivery_history for fraud signals: activity_7d_score, GPS history for zone_claim_match
   - Call compute_fraud_score from Person 1's fraud scorer
   - Call route_claim to get routing decision
   - Create claims record
   - If auto_approve or partial_review: call initiate_upi_payout from razorpay_client.py
   - Create payout_events record
   - Write payout_initiated event to audit_events
   - Commit DB transaction

For mock platform status in demo: maintain a simple set of suspended zone_cluster_ids that gets toggled by the /trigger/simulate admin endpoint.

### app/tasks/weekly_renewal.py

Celery task `renew_all_policies()` runs every Sunday midnight:
1. Query all policies with status='active' or status='waiting'
2. For each policy:
   - Increment coverage_week_number by 1
   - If status='waiting' AND (today − enrollment_date).days ≥ 28: set status='active', set coverage_start_date=today
   - Call calculate_premium from Person 2's inference.py with current features
   - Update policy: weekly_premium_amount, model_used, shap_explanation_json, next_renewal_at=next Sunday midnight
   - Deduct premium from UPI (log as pending — real UPI debit is out of scope for hackathon demo, record as audit event)
   - Increment enrollment_week in worker_profiles
   - Write policy_renewed event to audit_events

### app/tasks/cascade_recovery.py

Celery task `check_recovering_zones()` runs every 12 hours:
1. Query all trigger_events with status='active' or status='recovering'
2. For each trigger:
   - Re-query Open-Meteo 3-point for this zone
   - Re-check platform suspension status
   - Re-classify rainfall
   - If all sources report normal (no rainfall trigger, no platform suspension, AQI normal): set status='closed', closed_at=now. Write trigger_closed event to audit_events.
   - If still disrupted: compute cascade_day = floor((now − triggered_at).total_seconds() / 86400) + 1
   - If cascade_day ≤ 5: set status='recovering', call initiate_zone_payouts for cascade day N
   - If cascade_day > 5: set status='closed' (max 5-day cascade rule)

---

## 4.5 API Endpoints to Build

**app/api/trigger.py:**
- GET /zone/{zone_cluster_id}: Query trigger_events for this zone. Return current status (active/recovering/none), last composite score, triggered_at, trigger_type, sources_confirmed.
- POST /simulate: Admin endpoint. Accepts zone_cluster_id, trigger_type, duration_hours. Adds zone to mock suspended set. Creates a synthetic trigger_events record. Calls initiate_zone_payouts. Used for demo scenario.
- GET /active: Return all trigger_events with status in ('active', 'recovering'). Include zone info and current cascade day.
- GET /history: Return last 50 trigger events across all zones, ordered by triggered_at desc. Include composite_score, sources_confirmed, payout_count per event.

**app/api/claims.py:**
- GET /{worker_id}: Return worker's claim history ordered by claim_date desc. Include all payout amounts, fraud score, routing, status.
- GET /detail/{claim_id}: Return single claim with full fraud signal breakdown — zone_claim_match, activity_7d_score, fraud_score, routing, all payout components (base_loss, slab_delta, monthly_proximity).
- GET /pending: Admin. Return all claims with fraud_routing='partial_review' or status='held', ordered by fraud_score desc.
- PUT /{claim_id}/resolve: Admin. Accept resolution='approve' or 'reject'. If approve: trigger remaining payout (full amount minus what was already paid). If reject: update status='rejected'. Write claim_resolved event to audit_events.

**app/api/payout.py:**
- GET /{worker_id}/history: Return all payout_events for this worker ordered by initiated_at desc. Include amount, status, razorpay_payout_id, completed_at.
- POST /webhook/razorpay: Handle Razorpay payout status webhook. Verify webhook signature using RAZORPAY_KEY_SECRET. Update payout_events.status based on webhook event type ('payout.processed' → 'paid', 'payout.failed' → 'failed'). Write payout_status_updated event to audit_events.

---

## 4.6 Tests You Must Write (backend/tests/test_trigger/ and test_payout/)

**Trigger engine tests:**
- classify_rainfall(64.4) → triggered=False
- classify_rainfall(64.5) → triggered=True, category='heavy_rain'
- classify_rainfall(115.6) → category='very_heavy_rain'
- classify_rainfall(204.4) → category='extreme_heavy_rain'
- classify_heat(44.9) → triggered=False
- classify_heat(45.0) → triggered=True
- composite_score: all signals False → score=0.0, decision='no_trigger'
- composite_score: only platform suspended → score=0.40, sources_confirmed=1, decision='no_trigger' (only 1 source below 0.9 threshold)
- composite_score: platform + rainfall → score=0.75, sources_confirmed=2, decision='trigger_corroborated'
- composite_score: platform + rainfall + GIS → score=0.90, fast_path=False (boundary — 0.90 is not > 0.90)
- composite_score: platform + rainfall + GIS + heat → score=1.0, fast_path=True
- Heat and AQI both True → score same as heat alone (they share 0.10 slot, do not stack)
- 3-point oversampling: mock Open-Meteo returning 50mm, 80mm, 30mm for 3 points → result is 80mm (max)
- Bearing offset calculation: known input → verify output coordinates within 0.01° of expected

**Payout calculator tests:**
- cascade_day=1 → multiplier=1.0
- cascade_day=2 → multiplier=0.8
- cascade_day=3 → multiplier=0.6
- cascade_day=4 → multiplier=0.4
- cascade_day=5 → multiplier=0.4
- total_payout > weekly_baseline → capped at weekly_baseline
- deliveries_completed=10, next threshold=12 (₹120 bonus), P=0.6 → slab_delta=₹72
- monthly_proximity: not final 7 days of month → 0.0
- monthly_proximity: final 7 days, within 30 of 200 threshold → > 0 (exact value depends on delivery rate)
- waiting period: worker enrolled 10 days ago → skip payout (not eligible)
- Razorpay UPI VPA without '@' → validate_upi_vpa returns False
- Razorpay UPI VPA 'worker@okaxis' → validate_upi_vpa returns True

**Celery task tests (unit tests with mocked external calls):**
- trigger polling: mock Open-Meteo returning 80mm → composite scorer called with correct rainfall inputs
- trigger polling: composite_score < 0.5 → no trigger_events record created
- weekly renewal: worker in waiting period → status stays 'waiting'
- weekly renewal: worker at exactly 28 days → status changes to 'active'
- cascade recovery: mock all sources clear → trigger event closed
- cascade recovery: cascade_day=6 → trigger event closed regardless of conditions

---

---

# APPENDIX A — ENVIRONMENT VARIABLES REFERENCE

```
DATABASE_URL              Supabase PostgreSQL connection string
REDIS_URL                 Upstash Redis connection string (rediss:// for TLS)
RAZORPAY_KEY_ID           Razorpay test mode key ID (starts with rzp_test_)
RAZORPAY_KEY_SECRET       Razorpay test mode key secret
DATA_GOV_IN_API_KEY       data.gov.in API key for CPCB AQI
OPEN_METEO_BASE_URL       https://api.open-meteo.com/v1
OPEN_METEO_ARCHIVE_URL    https://archive-api.open-meteo.com/v1
EXPO_ACCESS_TOKEN         Expo push notification access token (Phase 3)
```

---

# APPENDIX B — COMPLETE PYTHON PACKAGES LIST

```
fastapi==0.111.0
uvicorn==0.29.0
pydantic==2.7.1
pydantic-settings==2.2.1
python-dotenv==1.0.1
sqlalchemy==2.0.29
alembic==1.13.1
psycopg2-binary==2.9.9
geoalchemy2==0.15.1
celery==5.3.6
redis==5.0.3
lightgbm==4.3.0
scikit-learn==1.4.2
shap==0.45.0
pyod==2.0.1
statsmodels==0.14.1
joblib==1.3.2
pandas==2.2.1
numpy==1.26.4
geopandas==0.14.4
shapely==2.0.4
networkx==3.3
razorpay==1.4.1
httpx==0.27.0
requests==2.31.0
pytest==8.2.0
pytest-asyncio==0.23.6
pytest-cov==5.0.0
```

---

# APPENDIX C — DAY-BY-DAY INTEGRATION CHECKPOINTS

**Day 1–2 (Person 1):** Repo initialised, all tables migrated to Supabase, slab_config seeded, main.py running at localhost:8000/docs, get_db and config.py working. Team can all run uvicorn locally.

**Day 2–4 (Person 2 parallel):** zone_clustering.py run against Supabase — zone_clusters table populated. synthetic_data.py generates training CSV. train_premium_models.py run on Kaggle — .joblib files pushed to Git LFS.

**Day 3–5 (Person 1 continues):** Onboarding endpoints complete, GIS spatial join working for Chennai pincodes, fraud scorer loading .joblib files and returning scores.

**Day 5 — Integration Checkpoint:**
- POST /onboarding/register → worker created in Supabase → policy created → POST /premium/calculate called internally → premium in response
- Person 1 and Person 2 merge to dev branch. Person 3 pulls dev.

**Day 5–9 (Person 3):** Trigger engine built. Payout calculator built. Celery tasks wired. Razorpay sandbox integration. All endpoints complete.

**Day 9–11:** Full end-to-end scenario: POST /trigger/simulate → trigger fires → workers in zone get payouts → fraud queue populated → admin dashboard shows data.

**Day 13–14:** Demo video recorded. All tests passing. Tag v0.2.0-phase2 on main.
