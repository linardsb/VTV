# Riga City Bus Management CMS — Master Plan

**Project:** CMS Webportal for Rīgas Satiksme Bus Operations
**Version:** 1.0 | **Date:** 2026-02-11
**Effort Level:** DETERMINED | **Analysis Depth:** 6 parallel agents, ~300k tokens of research

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
   - 1.5 [Product Strategy — Why RS Would Actually Pay](#15-product-strategy--why-rs-would-actually-pay-for-this)
     - [Assumption Stress-Test Results](#assumption-stress-test-results)
     - [The Three Things That Must Be Right](#the-three-things-that-must-be-right)
     - [Revised Go-To-Market Sequence](#revised-go-to-market-sequence)
     - [Financial Impact — What RS Saves](#155-financial-impact--what-rs-saves)
     - [Total Financial Impact Summary](#f-total-financial-impact-summary)
2. [Research Findings](#2-research-findings)
   - 2.2.1 [Competitive Advantage Synthesis](#221-competitive-advantage-synthesis--what-we-take-from-each)
   - 2.2.2 [Why RS Would Buy This](#222-why-rīgas-satiksme-would-buy-this)
   - 2.2.3 [Reliability Architecture](#223-reliability-architecture)
3. [Revised Architecture](#3-revised-architecture)
4. [Technology Stack](#4-technology-stack)
5. [Database Schema](#5-database-schema)
6. [API Design](#6-api-design)
7. [UI/UX Design](#7-uiux-design)
8. [AI Agent Design](#8-ai-agent-design)
9. [Real-Time Tracking](#9-real-time-tracking)
10. [Implementation Roadmap](#10-implementation-roadmap)
11. [Risk Register](#11-risk-register)
12. [ISC Verification](#12-isc-verification)
13. [5 Critical Questions Before Implementation](#5-critical-questions-before-implementation)

---

## 1. Executive Summary

### What We're Building

A **unified CMS webportal** for managing Riga's city bus operations — routes, schedules, fleet, and drivers — with a live tracking map and an AI assistant for dispatchers. The system consumes and produces GTFS-compliant data, integrates with Rīgas Satiksme's existing infrastructure, and complies with EU/GDPR regulations.

### Key Architecture Decisions (Post-Analysis)

Six parallel analysis streams (Council debate, First Principles, RedTeam stress-test, competitive analysis, Riga transit research, tech stack review) converged on these critical revisions to the original proposal:

| Original Proposal | Revised Decision | Rationale |
|---|---|---|
| Next.js + FastAPI microservices | **Modular monolith in Next.js** | 20 technologies reduced to 12. One language, one runtime. |
| Prisma ORM | **Drizzle ORM** | Native PostGIS support. Prisma requires raw SQL for all spatial queries. |
| Mapbox GL JS | **MapLibre GL JS + self-hosted tiles** | Eliminates vendor lock-in and $250+/month cost risk. |
| PostgreSQL + PostGIS + TimescaleDB | **PostgreSQL + PostGIS on Supabase** | TimescaleDB premature at 100 vehicles (20 writes/sec is trivial). |
| Redis Pub/Sub + SSE | **Polling Phase 1, SSE Phase 2** | Redis unnecessary for ~100 vehicles on a single instance. |
| Claude Opus 4.6 AI Agent from Day 1 | **No AI in Phase 1. Advisory-only Sonnet 4.5 in Phase 2** | $60-90/month API cost. Build good UI first, add AI when dispatcher pain points are validated. |
| Google OR-Tools route optimization | **Removed entirely** | City bus routes are fixed. OR-Tools solves VRP for dynamic routing, not fixed-route transit. |
| 2 languages (TypeScript + Python) | **TypeScript only** | Eliminates Python/FastAPI. One language, one ecosystem. |

### Budget

| Component | Monthly Cost |
|---|---|
| Supabase Pro (PostgreSQL + PostGIS + Auth + Realtime) | $25 |
| Railway / Fly.io (Next.js hosting) | $5-20 |
| MapLibre + OpenFreeMap tiles | $0 |
| Upstash Redis (Phase 2+, if needed) | $0-10 |
| Claude API (Phase 2+, advisory mode) | $30-60 |
| Domain + SSL | $1-2 |
| **Total Phase 1** | **$31-47/month** |
| **Total Phase 2+** | **$61-117/month** |

### Timeline (AI-Accelerated)

> **3x speedup vs traditional development.** Coding bottleneck eliminated — timeline now gated by human review, external service setup, and real-world testing.

| Phase | Duration | Team | Deliverables |
|---|---|---|---|
| **Phase 1: Core CMS** | 2-3 weeks | Claude Opus 4.6 + human review | Auth, GTFS import/export, route/stop/schedule CRUD, static map |
| **Phase 2: Live Operations** | 2-3 weeks | Claude Opus 4.6 + human review | Real-time tracking (SSE), fleet management, driver management, analytics |
| **Phase 3: Intelligence** | 2-3 weeks | Claude Opus 4.6 + human review | AI assistant (advisory), schedule suggestions, NeTEx/SIRI, advanced dashboards |
| **Total** | **6-9 weeks** | | **Down from 24 weeks (traditional) — 62-75% reduction** |

**Phase breakdown (what takes the time):**
- ~20% coding (Opus 4.6 — hours, not weeks)
- ~30% human review, testing, and iteration
- ~25% integration testing with real GTFS data and external services
- ~25% deployment, configuration, and UX polish

---

## 1.5 Product Strategy — Why RS Would Actually Pay For This

> *Output of First Principles analysis (Opus 4.6). Challenges every assumption about the product's viability.*

### The Core Insight

**This is not a "transit CMS." It is a compliance-first integration layer** for mid-size European transit agencies, sold modularly below procurement thresholds, built on open-source foundations, and validated through co-funded pilots.

RS will not pay to replace what works. They will pay to:
1. **Comply** — NeTEx/SIRI is an EU mandate with deadlines and consequences
2. **Integrate** — their GPS, scheduling, payment, and passenger info systems don't talk to each other
3. **Optimize** — 1,097 vehicles × even 2-3% scheduling improvement = hundreds of thousands of euros saved annually

### Assumption Stress-Test Results

| # | Assumption | Verdict | Strategic Implication |
|---|---|---|---|
| 1 | RS would pay for a new CMS | **MODIFY** | They pay to integrate and comply, not to replace. Position as overlay, not replacement. |
| 2 | Small team can compete with $1.3B companies | **REJECT as stated** | Don't compete on features. Compete on **fit**: Latvian context, EU compliance, procurement simplicity, price. |
| 3 | AI adds genuine value | **MODIFY** | Only in 2 places: arrival prediction (Swiftly proved it) and schedule optimization (Optibus proved it). Everything else is conventional software with honest labeling. |
| 4 | Open-source positioning wins | **MODIFY** | Affordability and auditability win. "Open-source" is a means, not the sales message. Lead with "lower cost, no lock-in, EU-compliant." |
| 5 | Technical superiority matters in procurement | **REJECT** | Procurement fit, price, and references matter more. Build to pass every checkbox, then win on price + local presence. |
| 6 | Product scales beyond Riga | **MODIFY** | Scales to mid-size CEE agencies (Tallinn, Vilnius, Bratislava, Ljubljana) on a 5-7 year path. Not Western Europe. |

### The Three Things That Must Be Right

**1. NeTEx/SIRI compliance is the wedge product — not scheduling, not AI, not the dashboard.**
- It's the only problem with an external deadline and legal consequences
- It's narrow enough for a small team to build well
- It creates the beachhead: once you process all of RS's operational data for compliance output, you become the integration layer. From there, expand to scheduling, analytics, AI.
- The big players (Trapeze, INIT) bundle NeTEx/SIRI into €500K+ platforms. A standalone compliance solution is genuinely differentiated.

**2. Get a paid pilot before building the full product.**
- RS will not be the first customer for an unproven product. But they might participate in a co-funded pilot.
- Latvia has access to EU Structural Funds, CEF (Connecting Europe Facility) for transport digitalization, and Horizon Europe.
- A transparent, EU-co-funded pilot with published results is the opposite of backroom deals — critical in the post-corruption context.
- Build *with* RS, not *for* RS. This produces a product that actually fits, a reference, and revenue from day one.

**3. Price below the open-tender threshold. Structure as modular SaaS.**
- Above **€143,000**: RS must run full EU-wide tender (12-18 months, Trapeze/INIT will bid, you lose on references)
- Below **€42,000**: Simplified procurement procedures
- Structure as independent modules, each procurable below thresholds:

| Module | Price | Procurement |
|---|---|---|
| NeTEx/SIRI Compliance Feed | €2,500/month (€30K/year) | Below simplified threshold |
| Real-Time Operations Dashboard | €2,000/month (€24K/year) | Below simplified threshold |
| Schedule Management + GTFS | €2,500/month (€30K/year) | Below simplified threshold |
| AI Scheduling Assistant | €1,500/month (€18K/year) | Below simplified threshold |
| **Full Platform** | **€8,500/month (€102K/year)** | Below full EU tender threshold |

RS can start with one module and expand. Monthly billing means they can cancel if it doesn't work. For a post-scandal organization, **reversibility is a feature.**

### Revised Go-To-Market Sequence

```
Phase 0: PILOT (Weeks 1-4)
├── Approach RS with NeTEx/SIRI compliance pitch
├── Propose EU-co-funded pilot (CEF or Structural Funds)
├── Build NeTEx feed generator from their existing GTFS data
├── Deliver working compliance module → FIRST REFERENCE
└── Revenue from day one (even if subsidized)

Phase 1: EXPAND (Weeks 5-12)
├── Add GTFS management + schedule editor on top of compliance layer
├── Integration with existing RS GPS feeds
├── Static map visualization (MapLibre)
└── RS is now using the platform daily

Phase 2: DEEPEN (Weeks 13-20)
├── Real-time tracking overlay (consume GTFS-RT, not replace AVL)
├── Dispatch dashboard with fleet status
├── Driver management (GDPR-compliant)
└── RS sees operational value beyond compliance

Phase 3: INTELLIGENCE (Weeks 21-28)
├── AI arrival predictions (where Swiftly proved the value)
├── AI scheduling suggestions (where Optibus proved the value)
├── Advanced analytics and reporting
└── RS is dependent on the platform for daily operations

Phase 4: SCALE (Month 7+)
├── Pitch Tallinn (similar context, geographic proximity)
├── Pitch Vilnius, Kaunas
├── Use Baltic references for CEE expansion
└── 5-7 year path to 10-20 agencies
```

### Competitive Position After This Analysis

**Before (naive):** "We're building a cheaper Trapeze"
**After (strategic):** "We're the only EU-compliance-first integration layer priced for mid-size CEE transit agencies"

The moat is not technical superiority. The moat is:
1. **Procurement fit** — modular pricing below tender thresholds
2. **Integration approach** — enhances existing systems, doesn't replace them
3. **Geographic focus** — Latvian/Baltic/CEE expertise that enterprise vendors lack
4. **Compliance specialization** — NeTEx/SIRI as entry point, not afterthought
5. **Transparency** — audit trails, exportable data, open-source foundations (post-corruption selling point)

### 1.5.5 Financial Impact — What RS Saves

> Based on confirmed RS financial data: €167.4M operating costs (2023), 115.9M passengers (2024), €35.4M fare revenue, 1,097 vehicles, ~€155M city subsidy. Sources: RS official reports, BNN, Riga Municipality budget documents.

#### A. Direct Cost Savings (Schedule Optimization)

Optibus case studies show **5-10% fleet reduction** and **5% reduction in driver duties** through AI scheduling. At RS scale:

| Metric | RS Current (est.) | Conservative (2%) | Moderate (5%) | Optimistic (10%) |
|---|---|---|---|---|
| Fleet utilization (1,097 vehicles) | Baseline | 22 vehicles freed | 55 vehicles freed | 110 vehicles freed |
| Operating cost per vehicle/year¹ | ~€152K | — | — | — |
| **Fleet savings/year** | — | **€3.3M** | **€8.4M** | **€16.7M** |
| Deadhead km reduction² | ~15% baseline | -1.5% points | -3% points | -5% points |
| **Fuel savings/year³** | — | **€680K** | **€1.4M** | **€2.3M** |
| Driver duty optimization | ~3,500 staff | 1% hours saved | 3% hours saved | 5% hours saved |
| **Labor cost savings/year⁴** | — | **€840K** | **€2.5M** | **€4.2M** |

¹ €167.4M ÷ 1,097 vehicles = ~€152K/vehicle/year
² Typical European urban transit deadhead: 10-15%. RS est. at 15% of ~80M vehicle-km/year = 12M deadhead km
³ At €0.85/km diesel fuel cost (European average, 50L/100km × €1.70/L)
⁴ Average Latvian transport sector salary ~€1,685/month gross (2024). With employer costs: ~€2,000/month.

| Scenario | Total Direct Savings/Year |
|---|---|
| **Conservative (2%)** | **€4.8M** |
| **Moderate (5%)** | **€12.3M** |
| **Optimistic (10%)** | **€23.2M** |

#### B. Revenue Uplift (Better On-Time Performance → More Riders)

Swiftly case studies: WMATA achieved **6.2% systemwide OTP increase**, Oulu (Finland) **20%+ improvement**. Better reliability → higher ridership → more fare revenue.

| Metric | Current | With Platform |
|---|---|---|
| Annual passengers | 115.9M | — |
| Average fare/passenger⁵ | €0.31 | — |
| On-time performance improvement | Baseline | +5-15% OTP |
| Ridership increase from better service⁶ | — | +1-3% |
| **Additional passengers/year** | — | **1.2M - 3.5M** |
| **Additional fare revenue/year** | — | **€370K - €1.1M** |
| **Additional subsidy justification⁷** | — | **€1.7M - €5.0M** |

⁵ €35.4M fare revenue ÷ 115.9M passengers = €0.31/passenger (low due to monthly passes, student/senior discounts)
⁶ Industry rule of thumb: 1% OTP improvement ≈ 0.3-0.5% ridership increase
⁷ RS receives €155M city subsidy. Higher ridership strengthens case for maintained/increased subsidy at ~€1.34/passenger

#### C. Avoided Costs (What RS Doesn't Have to Spend)

| Cost Category | Enterprise Alternative | Our Platform | **RS Saves** |
|---|---|---|---|
| CAD/AVL + scheduling suite (Trapeze/INIT) | €500K-2M setup + €100-400K/year | €102K/year (full platform) | **€400K-1.9M Year 1** |
| Annual maintenance (enterprise) | €100-400K/year ongoing | Included in SaaS | **€100-300K/year** |
| NeTEx/SIRI compliance consultant | €50-150K one-time + ongoing | Built-in | **€50-150K** |
| Manual GTFS feed maintenance⁸ | ~1 FTE = €24K/year | Automated | **€24K/year** |
| Dispatch process inefficiency⁹ | ~2 FTE equivalent waste | Streamlined | **€48K/year** |
| IT infrastructure (on-premise servers) | €30-80K/year | Cloud SaaS | **€30-80K/year** |

⁸ RS currently maintains GTFS feed manually. Automating saves ~1 full-time equivalent.
⁹ Estimated: dispatchers manually bridging disconnected systems, copying data between tools.

| Category | Year 1 Savings | Annual Ongoing |
|---|---|---|
| **Avoided enterprise software** | **€400K - €1.9M** | **€100-300K** |
| **Avoided compliance costs** | **€50-150K** | **€20-50K** |
| **Automated manual processes** | **€72-102K** | **€72-102K** |

#### D. EU Funding Opportunities (Available Capital)

| Fund | Latvia Allocation (2021-2027) | Relevance | Realistic for RS |
|---|---|---|---|
| **CEF Transport** | €25.8B EU-wide (Latvia received €928M for Rail Baltica) | ITS digitalization eligible | €200K-1M per project application |
| **EU Structural Funds** | €5.4B total Latvia allocation | Transport + digital transformation | €500K-2M competitive bid |
| **Recovery & Resilience Facility** | €365.3M Latvia digital transformation | Smart city / public services | €100K-500K |
| **Horizon Europe** | Open calls | Innovation in transport | €200K-1M consortium |
| **ERDF (Regional Development)** | Part of €5.4B structural | Urban sustainable transport | €300K-1M |

**Realistic EU co-funding scenario:**
- Pilot project: €100-300K from CEF/Structural Funds (covers 50-70% of development)
- RS co-funds remaining 30-50%
- RS effective cost for pilot: **€50-150K** (vs. €500K-2M for enterprise alternative)

#### E. Compliance Risk Avoided

| Risk | Consequence | Probability Without Platform | Financial Exposure |
|---|---|---|---|
| NeTEx/SIRI non-compliance | EU infringement proceedings | Medium-High | €5K-50K/day penalty payments |
| GDPR violation (driver GPS data) | DPA fine | Medium | Up to 4% of revenue = **€7.3M** |
| Degraded EU funding eligibility | Reduced competitiveness for transport grants | High | **€500K-5M** in lost funding |
| Passenger info quality gap | Riders switch to cars, ridership drops | Medium | **€1-3M/year** in lost fare + subsidy |

#### F. Total Financial Impact Summary

| Category | Conservative/Year | Moderate/Year | Optimistic/Year |
|---|---|---|---|
| Schedule optimization savings | €4.8M | €12.3M | €23.2M |
| Revenue uplift (ridership) | €2.1M | €3.5M | €6.1M |
| Avoided enterprise costs | €572K | €1.1M | €2.3M |
| EU co-funding (amortized) | €50K | €150K | €300K |
| Compliance risk reduction | €100K | €500K | €2M |
| **TOTAL ANNUAL VALUE** | **€7.6M** | **€17.6M** | **€33.9M** |
| **Platform cost** | **€102K/year** | **€102K/year** | **€102K/year** |
| **ROI** | **74:1** | **172:1** | **332:1** |

> **The pitch in one line:** For €102K/year (0.06% of operating budget), RS gains €7.6-33.9M in savings, revenue uplift, and risk reduction — a **74x-332x return on investment.**

**Important caveats:**
- Conservative scenario assumes only 2% optimization improvement (Optibus achieves 5-10%)
- Revenue uplift depends on fare policy and subsidy structure
- EU funding requires competitive applications (not guaranteed)
- Full savings require Phase 2-3 features (scheduling optimization, AI predictions)
- Schedule optimization savings assume RS doesn't already have equivalent software

---

## 2. Research Findings

### 2.1 Rīgas Satiksme — Current State

| Metric | Value |
|---|---|
| Total fleet | 1,097 vehicles (476 buses, 354 trolleybuses, 267 trams) |
| Bus routes | ~60 routes |
| GTFS feed | **Available**: `saraksti.rigassatiksme.lv/gtfs.zip` |
| SIRI API | **Available**: `saraksti.rigassatiksme.lv/siri-stop-departures.php?stopid=STOPID` |
| Existing tech | GPS tracking, APC, e-talons payment, WiFi, Papercast e-paper displays |
| Procurement | 100 new trolleybuses + 24 new trams planned |
| Infrastructure | Tram Line 7 extension opening May 2026 |
| Regulation | Sabiedriskā transporta pakalpojumu likums (2007) + EU PSO regulation |

**Critical insight:** Rīgas Satiksme already has GPS tracking and publishes GTFS feeds. This CMS is an **integration and management layer** on top of existing infrastructure, not a replacement.

### 2.2 Competitive Landscape

| System | Type | Strength | Gap |
|---|---|---|---|
| **Optibus** ($1.3B) | Scheduling SaaS | Best AI/ML scheduling, GenAI rules | No dispatch, no tracking |
| **Swiftly** | Analytics SaaS | Best predictions, GTFS-RT leader | Analytics only, no management |
| **Trapeze** | Full CAD/AVL | Complete dispatch system | Legacy UI, expensive |
| **INIT** | Full suite | Best crew/fare management | Very expensive |
| **Clever Devices** | CAD/AVL | Disruption management | North America focused |
| **OneBusAway** | Open-source | Passenger-facing, white-label | No back-office management |
| **OpenTripPlanner** | Open-source | Trip planning, NeTEx support | API only, no dispatch |

**Market gap we fill:** No affordable, integrated, EU-compliant (NeTEx/SIRI) transit management platform exists for mid-size European agencies (50-500 vehicles). Commercial solutions cost $500-2,000+/month. Open-source tools are fragmented.

### 2.2.1 Competitive Advantage Synthesis — What We Take From Each

The strategy is not to out-build $1.3B companies. It's to **cherry-pick the best ideas from each competitor** and deliver them as a unified, affordable, Riga-native platform.

| From Competitor | What We Adopt | How We Implement It |
|---|---|---|
| **Optibus** — GenAI rules | Natural language scheduling queries | Claude AI assistant understands "show me all Route 22 trips arriving late on weekdays" — no SQL needed. Phase 3. |
| **Optibus** — AI schedule analysis | "What changed?" comparative analysis | AI tool compares two schedule versions, highlights differences, estimates impact. Phase 3. |
| **Swiftly** — Multi-source GPS fusion | Consume all available RS data feeds | Ingest GTFS-RT vehicle positions + SIRI API + any additional AVL data RS exposes. Single unified map. Phase 2. |
| **Swiftly** — Overlay approach | Enhance, don't replace existing systems | CMS sits on top of RS's existing GPS, e-talons, and GTFS infrastructure. Zero disruption to current operations. |
| **Trapeze** — IDS decision support | AI-assisted incident response | When delay detected, AI suggests: reroute, hold, short-turn, or express. Dispatcher approves with one click. Phase 3. |
| **Trapeze** — NeTEx/SIRI native | EU compliance from architecture | NeTEx export + SIRI feed generation built into the data model, not bolted on. Phase 3. |
| **INIT** — Crew management | Driver shift assignment with GDPR | Pseudonymized driver records, shift calendar, vehicle assignment. Compliant with Latvian Data Protection Law. Phase 2. |
| **INIT** — Integrated scheduling | Schedule → dispatch → tracking pipeline | Single data flow: create schedule → assign vehicles → track execution → report adherence. No data silos. |
| **Clever Devices** — Disruption management | Service alert cascade system | Create alert → automatically updates GTFS-RT feed → Moovit/Google Maps notified → dispatcher dashboard highlighted. Phase 2. |
| **OneBusAway** — Open data ethos | GTFS/GTFS-RT/NeTEx feeds published | Every data change automatically generates updated feeds. Moovit, Google Maps, Transit App always current. |
| **OpenTripPlanner** — Trip planning | Link to existing RS route planner | Don't rebuild trip planning. Link to `saraksti.rigassatiksme.lv` and expose data for OTP integration. |

### 2.2.2 Why Rīgas Satiksme Would Buy This

**Understanding the buyer:**
- Municipal company, post-corruption scandal — **procurement transparency** matters
- €300M debt — **cost sensitivity** is extreme, but they still spend on modernization (100 new trolleybuses, 24 trams)
- 3,500 employees — decisions go through committees, not a single buyer
- Already have basic systems working — they need **improvement, not revolution**
- EU open data front-runner — they care about **standards compliance**

**The pitch to RS:**

| RS Pain Point | How We Solve It | Competitor Can't Because |
|---|---|---|
| **No unified operations view** — GPS, schedules, fleet data in separate systems | Single-screen dispatch dashboard combining map, schedule adherence, fleet status, alerts | Optibus/Swiftly only cover fragments; Trapeze/INIT cost €500K+ |
| **GTFS feed maintenance is manual** | Auto-generated GTFS/GTFS-RT from schedule editor. Edit schedule → feeds update instantly | Open-source tools require manual export. Commercial tools are closed. |
| **EU compliance pressure** (NeTEx/SIRI mandate) | Native NeTEx export + SIRI feed from same data model. No conversion tools needed. | Optibus doesn't support NeTEx. Swiftly is GTFS-only. |
| **New fleet integration** (100 trolleybuses, 24 trams, hydrogen vehicles) | Vehicle management with type-specific tracking (battery level for electric, hydrogen for fuel cell) | Legacy systems designed for diesel buses only |
| **Cost** — enterprise systems quote €100K-500K+ | SaaS at **€500-1,500/month** (or self-hosted for even less). No hardware. No multi-year lock-in. | Trapeze, INIT, Clever Devices require enterprise contracts |
| **Latvian language + local context** | Full LV/EN bilingual UI. Understands Riga geography, RS route numbering, local regulations. | All competitors are English-first with generic localization |
| **Post-corruption transparency** | Full audit trail. Every change logged with user, timestamp, reason. Open-source core. | Proprietary systems are black boxes |

### 2.2.3 Reliability Architecture

For a transit agency, reliability isn't a feature — it's the entire product. Dispatchers can't have the system go down during rush hour.

**Tier 1: Core Reliability (Phase 1)**
| Measure | Implementation |
|---|---|
| **Offline-capable dispatch view** | Service worker caches last-known vehicle positions + schedule. Map works offline with cached tiles. |
| **Zero-downtime deployments** | Vercel preview → production promotion. No maintenance windows. |
| **Automatic data backups** | Supabase daily backups + point-in-time recovery (included in Pro plan) |
| **Input validation at every boundary** | Zod schemas on tRPC, GTFS validation on import, sanitized AI outputs |
| **Health monitoring** | `/api/health` endpoint + Uptime Robot (free) → Slack/email alerts |

**Tier 2: Operational Reliability (Phase 2)**
| Measure | Implementation |
|---|---|
| **Stale data detection** | Vehicle markers gray out after 60s without update. Dispatcher sees "last seen" timestamp. |
| **Graceful degradation** | If Redis down → fall back to polling. If Claude API down → hide AI panel, dispatch works normally. |
| **Connection recovery** | SSE auto-reconnect with exponential backoff. No lost positions. |
| **Rate limiting** | Per-user and per-IP rate limits on all endpoints. GPS ingestion rate-limited per device. |
| **Audit trail** | Every data mutation logged: who, what, when, previous value. Immutable log table. |

**Tier 3: Enterprise Reliability (Phase 3)**
| Measure | Implementation |
|---|---|
| **SLA dashboard** | Internal metrics page showing uptime, response times, feed freshness |
| **Anomaly detection** | AI flags unusual patterns: "Route 22 has no vehicles reporting — possible feed issue" |
| **Data integrity checks** | Nightly job validates GTFS output against MobilityData validator |
| **Disaster recovery plan** | Documented RTO < 1 hour. Database restore + redeploy from git. |
| **Penetration testing** | Pre-launch security audit of SSE auth, GPS ingestion, admin endpoints |

### 2.2.4 Competitive Positioning Summary

```
                        AFFORDABLE ←─────────────────→ EXPENSIVE
                            │                              │
              FRAGMENTED    │    ★ OUR POSITION            │
              (open-source) │    Unified + Affordable      │
                   │        │    + EU-Compliant             │
                   ▼        │                              │
    ┌─────────────────────┐ │                              │
    │ OTP + OneBusAway    │ │                              │
    │ + TransitClock      │ │                              │
    │ (Free, but 3 tools  │ │                              │
    │  no dispatch, no UI)│ │                              │
    └─────────────────────┘ │                              │
                            │                              │
    ┌──────────────┐        │         ┌────────────────┐   │
    │ Swiftly      │        │         │ Trapeze        │   │
    │ (Analytics   │        │         │ (Full CAD/AVL  │   │
    │  only)       │        │         │  Legacy UI)    │   │
    └──────────────┘        │         └────────────────┘   │
    ┌──────────────┐        │         ┌────────────────┐   │
    │ Optibus      │        │         │ INIT           │   │
    │ (Scheduling  │        │         │ (Full suite    │   │
    │  only)       │        │         │  €500K+)       │   │
    └──────────────┘        │         └────────────────┘   │
                            │                              │
              PARTIAL ──────┼──────────────── COMPLETE     │
              (single       │              (full ops)      │
               function)    │                              │
```

**Our moat:** The only platform that is simultaneously:
1. **Affordable** (€500-1,500/month vs €100K+ enterprise)
2. **Complete** (schedule + dispatch + tracking + AI in one tool)
3. **EU-native** (NeTEx/SIRI from day one, not converted from GTFS)
4. **Riga-specific** (Latvian UI, RS feed integration, local regulatory knowledge)
5. **Transparent** (open audit trail, exportable data, no vendor lock-in)

### 2.3 RedTeam Key Findings

18 vulnerabilities identified. Top 5 by severity:

| # | Finding | Severity | Mitigation |
|---|---|---|---|
| 1 | 20 technologies / 2 languages is CRITICAL complexity | CRITICAL | Reduced to 12 tech / 1 language |
| 2 | GDPR not architected (GPS = personal data in EU) | CRITICAL | Privacy-by-design from day 1 |
| 3 | SSE authentication gap (EventSource has no custom headers) | CRITICAL | Cookie-based auth with httpOnly |
| 4 | Scope is a 6-month project, not 4 weeks | CRITICAL | Phased delivery with 8-week cycles |
| 5 | AI agent may solve wrong problem for fixed routes | HIGH | Defer to Phase 2, validate with dispatchers |

### 2.4 First Principles Verdict

| Assumption | Verdict |
|---|---|
| Need a custom CMS | **MODIFY** — build integration dashboard, not full CMS |
| Next.js is right | **KEEP** — council and tech research confirm App Router is production-ready |
| PostGIS needed | **MODIFY** — start with plain PostGIS on Supabase, not TimescaleDB |
| AI agent essential | **REJECT for MVP** — add Phase 2 after dispatcher validation |
| Custom real-time | **MODIFY** — consume existing GTFS-RT/AVL feeds first |
| GTFS compliance | **KEEP** — Riga publishes GTFS, EU mandates it |
| $50-150/month | **ACHIEVABLE** — with simplified stack ($31-47 Phase 1) |
| OR-Tools | **REJECT** — fixed routes don't need VRP solver |
| TimescaleDB | **REJECT** — 20 writes/sec is trivial for standard PostgreSQL |

---

## 3. Revised Architecture

### 3.1 System Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────┐
│                        CLIENTS                                   │
│  ┌─────────────┐  ┌─────────────┐  ┌──────────────────────────┐ │
│  │  Dispatcher  │  │   Admin     │  │  Public Schedule Viewer  │ │
│  │  Dashboard   │  │   Portal    │  │  (Future)                │ │
│  └──────┬───────┘  └──────┬──────┘  └───────────┬──────────────┘ │
│         │                 │                      │                │
└─────────┼─────────────────┼──────────────────────┼────────────────┘
          │                 │                      │
          ▼                 ▼                      ▼
┌──────────────────────────────────────────────────────────────────┐
│              NEXT.JS 15 APP ROUTER (MODULAR MONOLITH)            │
│                                                                   │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐            │
│  │  Routes  │ │Schedules │ │  Fleet   │ │  GTFS    │            │
│  │  Module  │ │  Module  │ │  Module  │ │  Module  │            │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘            │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐            │
│  │ Tracking │ │    AI    │ │  Auth    │ │ Reports  │            │
│  │  Module  │ │  Module  │ │  Module  │ │  Module  │            │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘            │
│                                                                   │
│  ┌────────────────────────────────────────────────────┐          │
│  │              tRPC v11 API Layer                     │          │
│  │  (Type-safe procedures + SSE subscriptions)         │          │
│  └────────────────────────────────────────────────────┘          │
│                                                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐           │
│  │  Drizzle ORM │  │  Auth.js v5  │  │  MapLibre    │           │
│  │  (PostGIS)   │  │  (RBAC)      │  │  (Client)    │           │
│  └──────┬───────┘  └──────────────┘  └──────────────┘           │
└─────────┼────────────────────────────────────────────────────────┘
          │
          ▼
┌──────────────────────────────────────────────────────────────────┐
│                     DATA LAYER                                    │
│                                                                   │
│  ┌─────────────────────────────┐  ┌────────────────────────────┐ │
│  │    Supabase PostgreSQL      │  │    Upstash Redis           │ │
│  │    + PostGIS Extension      │  │    (Phase 2+ only)         │ │
│  │                             │  │    - SSE fan-out            │ │
│  │    - GTFS-aligned schema    │  │    - Position cache         │ │
│  │    - Vehicle positions      │  │                             │ │
│  │    - Spatial indexes        │  └────────────────────────────┘ │
│  │    - User/auth data         │                                 │
│  └─────────────────────────────┘                                 │
│                                                                   │
│  ┌─────────────────────────────┐  ┌────────────────────────────┐ │
│  │  External Data Sources      │  │  Claude API (Phase 2+)     │ │
│  │  - RS GTFS Feed             │  │  - Sonnet 4.5 (primary)    │ │
│  │  - SIRI Stop Departures     │  │  - Haiku 4.5 (simple)      │ │
│  │  - GPS Hardware (AVL)       │  │  - Advisory mode only      │ │
│  └─────────────────────────────┘  └────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
```

### 3.2 Module Boundaries

```
src/
├── app/                          # Next.js App Router pages
│   ├── (auth)/                   # Auth pages (login, register)
│   ├── (dashboard)/              # Protected dashboard layout
│   │   ├── routes/               # Route management pages
│   │   ├── schedules/            # Schedule/timetable pages
│   │   ├── stops/                # Stop management pages
│   │   ├── fleet/                # Vehicle management (Phase 2)
│   │   ├── drivers/              # Driver management (Phase 2)
│   │   ├── tracking/             # Live map dashboard (Phase 2)
│   │   ├── reports/              # Analytics (Phase 2)
│   │   └── assistant/            # AI helper (Phase 3)
│   ├── api/                      # tRPC + GTFS endpoints
│   │   ├── trpc/[trpc]/          # tRPC handler
│   │   ├── gtfs/                 # GTFS import/export
│   │   └── positions/            # GPS ingestion (Phase 2)
│   └── layout.tsx                # Root layout
├── server/                       # Server-side logic
│   ├── trpc/                     # tRPC routers
│   │   ├── routes.ts
│   │   ├── schedules.ts
│   │   ├── stops.ts
│   │   ├── fleet.ts              # Phase 2
│   │   ├── drivers.ts            # Phase 2
│   │   ├── tracking.ts           # Phase 2
│   │   └── assistant.ts          # Phase 3
│   ├── gtfs/                     # GTFS import/export logic
│   │   ├── importer.ts
│   │   ├── exporter.ts
│   │   └── validator.ts
│   ├── tracking/                 # Real-time tracking (Phase 2)
│   │   ├── ingestion.ts
│   │   ├── broadcast.ts
│   │   └── geofence.ts
│   └── ai/                       # AI agent (Phase 3)
│       ├── agent.ts
│       ├── tools.ts
│       └── prompts.ts
├── components/                   # React components
│   ├── map/                      # MapLibre components
│   ├── tables/                   # Data tables (Tanstack)
│   ├── forms/                    # Form components
│   └── ui/                       # Shadcn/ui components
├── db/                           # Drizzle schema + migrations
│   ├── schema/
│   │   ├── gtfs.ts               # GTFS-aligned tables
│   │   ├── fleet.ts              # Vehicle/driver tables
│   │   ├── tracking.ts           # Position history
│   │   └── auth.ts               # User/role tables
│   └── migrations/
├── lib/                          # Shared utilities
│   ├── gtfs/                     # GTFS parsing utilities
│   ├── geo/                      # Geospatial utilities (Turf.js)
│   └── i18n/                     # LV/EN translations
└── public/                       # Static assets
    └── map-styles/               # MapLibre style JSON
```

---

## 4. Technology Stack

### 4.1 Final Stack (12 Technologies, 1 Language)

| Layer | Technology | Version | Justification |
|---|---|---|---|
| **Language** | TypeScript | 5.x | Single language eliminates Python/FastAPI complexity |
| **Framework** | Next.js | 15.x | Production-ready App Router. Server Components for CRUD pages. |
| **UI Components** | Shadcn/ui + Tailwind v4 | Latest | CSS variable theming for agency branding. No framework lock-in. |
| **Data Tables** | TanStack Table | v8 | Server-side search, filter, pagination for route/schedule lists |
| **API** | tRPC v11 | 11.x | Type-safe API + SSE subscriptions for real-time (Phase 2) |
| **ORM** | Drizzle ORM | Latest | **Native PostGIS point type support.** Better than Prisma for spatial. |
| **Database** | PostgreSQL + PostGIS | 16+ | Supabase managed. GTFS-aligned schema with spatial indexes. |
| **Maps** | MapLibre GL JS | 4.x | Open-source Mapbox fork. Self-hosted tiles via OpenFreeMap. $0/month. |
| **Auth** | Auth.js v5 | 5.x | Self-hosted RBAC. Data sovereignty for municipal government. |
| **Cache** | Upstash Redis | Serverless | Phase 2+ only. SSE fan-out + position cache. Free tier to start. |
| **AI** | Claude API (Sonnet 4.5) | Latest | Phase 2+ only. Advisory mode with spending caps. |
| **Hosting** | Railway / Fly.io | - | $5-20/month for Next.js. Docker deployment. |

### 4.2 What Was Explicitly Removed and Why

| Removed | Why |
|---|---|
| Python / FastAPI | One language policy. Eliminates 2nd ecosystem. |
| Google OR-Tools | Fixed bus routes don't need VRP solver. Use OSRM for detours. |
| TimescaleDB | 20 writes/sec is trivial. Standard PostgreSQL with partitioning suffices. |
| Prisma ORM | No native PostGIS support. Drizzle has built-in geometry types. |
| Mapbox GL JS | Vendor lock-in + cost risk. MapLibre is API-compatible and free. |
| Redis (Phase 1) | In-process pub/sub handles 100 vehicles on single instance. |
| Claude API (Phase 1) | Build good UI first. Validate dispatcher needs before adding AI. |
| Monorepo tooling | Single repo with clean folder structure. 2-3 dev team doesn't need Turborepo. |

---

## 5. Database Schema

### 5.1 GTFS-Aligned Core Schema (Drizzle ORM)

```typescript
// db/schema/gtfs.ts — Core GTFS tables

// Agencies (transit operators)
export const agencies = pgTable('agencies', {
  id: text('id').primaryKey(),                    // GTFS agency_id
  name: text('name').notNull(),                   // "Rīgas Satiksme"
  url: text('url'),
  timezone: text('timezone').default('Europe/Riga'),
  lang: text('lang').default('lv'),
  phone: text('phone'),
});

// Routes (bus lines)
export const routes = pgTable('routes', {
  id: text('id').primaryKey(),                    // GTFS route_id
  agencyId: text('agency_id').references(() => agencies.id),
  shortName: text('short_name'),                  // "22"
  longName: text('long_name'),                    // "Jugla - Centrs"
  type: integer('type').default(3),               // 3 = Bus
  color: text('color'),                           // "FF0000"
  textColor: text('text_color'),
  description: text('description'),
  // Internal fields (beyond GTFS)
  isActive: boolean('is_active').default(true),
  createdAt: timestamp('created_at').defaultNow(),
  updatedAt: timestamp('updated_at').defaultNow(),
});

// Stops (bus stops with geolocation)
export const stops = pgTable('stops', {
  id: text('id').primaryKey(),                    // GTFS stop_id
  name: text('name').notNull(),
  nameLv: text('name_lv'),                        // Latvian name
  lat: doublePrecision('lat').notNull(),
  lon: doublePrecision('lon').notNull(),
  // PostGIS geometry for spatial queries
  geom: geometry('geom', { type: 'point', srid: 4326 }),
  code: text('code'),                             // Stop code for passengers
  locationType: integer('location_type').default(0),
  wheelchairBoarding: integer('wheelchair_boarding').default(0),
  // Internal fields
  shelter: boolean('shelter').default(false),
  bench: boolean('bench').default(false),
  display: boolean('electronic_display').default(false),
}, (table) => ({
  geomIdx: index('stops_geom_idx').using('gist', table.geom),
  latLonIdx: index('stops_lat_lon_idx').on(table.lat, table.lon),
}));

// Calendar (service patterns)
export const calendar = pgTable('calendar', {
  serviceId: text('service_id').primaryKey(),
  monday: boolean('monday').notNull(),
  tuesday: boolean('tuesday').notNull(),
  wednesday: boolean('wednesday').notNull(),
  thursday: boolean('thursday').notNull(),
  friday: boolean('friday').notNull(),
  saturday: boolean('saturday').notNull(),
  sunday: boolean('sunday').notNull(),
  startDate: text('start_date').notNull(),        // YYYYMMDD format
  endDate: text('end_date').notNull(),
});

// Calendar Dates (exceptions: holidays, special events)
export const calendarDates = pgTable('calendar_dates', {
  serviceId: text('service_id').references(() => calendar.serviceId),
  date: text('date').notNull(),                   // YYYYMMDD
  exceptionType: integer('exception_type').notNull(), // 1=added, 2=removed
}, (table) => ({
  pk: primaryKey({ columns: [table.serviceId, table.date] }),
}));

// Trips (specific journey on a route)
export const trips = pgTable('trips', {
  id: text('id').primaryKey(),                    // GTFS trip_id
  routeId: text('route_id').references(() => routes.id),
  serviceId: text('service_id').references(() => calendar.serviceId),
  headsign: text('headsign'),                     // "Centrs"
  directionId: integer('direction_id'),           // 0 or 1
  blockId: text('block_id'),                      // Vehicle block
  shapeId: text('shape_id'),
  wheelchairAccessible: integer('wheelchair_accessible').default(0),
});

// Stop Times (the actual schedule data)
export const stopTimes = pgTable('stop_times', {
  tripId: text('trip_id').references(() => trips.id),
  stopId: text('stop_id').references(() => stops.id),
  arrivalTime: text('arrival_time').notNull(),    // HH:MM:SS (can exceed 24:00)
  departureTime: text('departure_time').notNull(),
  stopSequence: integer('stop_sequence').notNull(),
  pickupType: integer('pickup_type').default(0),
  dropOffType: integer('drop_off_type').default(0),
}, (table) => ({
  pk: primaryKey({ columns: [table.tripId, table.stopSequence] }),
  tripIdx: index('stop_times_trip_idx').on(table.tripId),
  stopIdx: index('stop_times_stop_idx').on(table.stopId),
}));

// Shapes (route geometry as encoded polylines)
export const shapes = pgTable('shapes', {
  id: text('id').primaryKey(),                    // GTFS shape_id
  encodedPolyline: text('encoded_polyline'),      // Google encoded polyline
  geom: geometry('geom', { type: 'linestring', srid: 4326 }),
}, (table) => ({
  geomIdx: index('shapes_geom_idx').using('gist', table.geom),
}));
```

### 5.2 Fleet & Operations Schema (Phase 2)

```typescript
// db/schema/fleet.ts

export const vehicles = pgTable('vehicles', {
  id: text('id').primaryKey(),
  registrationNumber: text('registration_number').unique(),
  type: text('type').notNull(),                   // 'bus', 'trolleybus', 'tram'
  make: text('make'),
  model: text('model'),
  year: integer('year'),
  capacity: integer('capacity'),
  isAccessible: boolean('is_accessible').default(false),
  status: text('status').default('active'),       // active, maintenance, retired
  gpsDeviceId: text('gps_device_id'),
});

export const drivers = pgTable('drivers', {
  id: text('id').primaryKey(),
  // GDPR: pseudonymized identifier, not real name
  employeeCode: text('employee_code').unique().notNull(),
  licenseCategory: text('license_category'),
  licenseExpiry: date('license_expiry'),
  status: text('status').default('active'),
  // No personal data stored — linked via HR system
});

// db/schema/tracking.ts — Vehicle positions (Phase 2)

export const vehiclePositions = pgTable('vehicle_positions', {
  id: serial('id').primaryKey(),
  vehicleId: text('vehicle_id').references(() => vehicles.id),
  tripId: text('trip_id').references(() => trips.id),
  lat: doublePrecision('lat').notNull(),
  lon: doublePrecision('lon').notNull(),
  bearing: real('bearing'),
  speed: real('speed'),
  timestamp: timestamp('timestamp', { withTimezone: true }).notNull(),
  // Derived fields
  scheduleAdherence: integer('schedule_adherence_seconds'),
  congestionLevel: text('congestion_level'),
}, (table) => ({
  vehicleTimeIdx: index('vp_vehicle_time_idx').on(table.vehicleId, table.timestamp),
  timestampIdx: index('vp_timestamp_idx').on(table.timestamp),
}));

// Current vehicle positions cache (latest only)
export const currentPositions = pgTable('current_positions', {
  vehicleId: text('vehicle_id').primaryKey().references(() => vehicles.id),
  tripId: text('trip_id'),
  routeId: text('route_id'),
  lat: doublePrecision('lat').notNull(),
  lon: doublePrecision('lon').notNull(),
  bearing: real('bearing'),
  speed: real('speed'),
  timestamp: timestamp('timestamp', { withTimezone: true }).notNull(),
  status: text('status').default('in_service'),
  updatedAt: timestamp('updated_at').defaultNow(),
});
```

### 5.3 Auth Schema

```typescript
// db/schema/auth.ts — Auth.js v5 compatible

export const users = pgTable('users', {
  id: text('id').primaryKey(),
  email: text('email').unique().notNull(),
  name: text('name'),
  role: text('role').default('viewer'),           // admin, dispatcher, editor, viewer
  hashedPassword: text('hashed_password'),
  createdAt: timestamp('created_at').defaultNow(),
});

// Roles: admin (full access), dispatcher (tracking + operations),
//        editor (routes/schedules), viewer (read-only)
```

---

## 6. API Design

### 6.1 tRPC Router Catalog

```
routes.router
├── routes.list          GET    — List all routes with filters
├── routes.getById       GET    — Get route with stops and shape
├── routes.create        MUTATION — Create new route
├── routes.update        MUTATION — Update route details
├── routes.delete        MUTATION — Delete route (admin only)
└── routes.getShape      GET    — Get route geometry for map

schedules.router
├── schedules.getByRoute GET    — Get timetable for a route
├── schedules.getTrips   GET    — Get trips for a service day
├── schedules.createTrip MUTATION — Add trip to schedule
├── schedules.updateStopTimes MUTATION — Edit stop times
├── schedules.cloneService MUTATION — Clone schedule pattern
└── schedules.getCalendar GET   — Get service calendar

stops.router
├── stops.list           GET    — List all stops with spatial filter
├── stops.nearby         GET    — Stops within radius (PostGIS ST_DWithin)
├── stops.getById        GET    — Get stop with departures
├── stops.create         MUTATION — Create stop with coordinates
├── stops.update         MUTATION — Update stop details
└── stops.search         GET    — Full-text search by name

gtfs.router
├── gtfs.import          MUTATION — Import GTFS ZIP file
├── gtfs.export          GET    — Generate and download GTFS ZIP
├── gtfs.validate        GET    — Validate current data against GTFS spec
└── gtfs.status          GET    — Last import status + data freshness

fleet.router (Phase 2)
├── fleet.vehicles.list  GET    — List vehicles with status
├── fleet.vehicles.assign MUTATION — Assign vehicle to trip
└── fleet.vehicles.updateStatus MUTATION — Change vehicle status

tracking.router (Phase 2)
├── tracking.positions   SUBSCRIPTION — SSE stream of vehicle positions
├── tracking.ingest      MUTATION — Receive GPS data from vehicles
└── tracking.history     GET    — Historical positions for playback

assistant.router (Phase 3)
├── assistant.chat       MUTATION — Send message to AI agent
└── assistant.suggestions GET   — Get proactive AI suggestions
```

### 6.2 GTFS Endpoints (REST)

```
POST  /api/gtfs/import    — Upload GTFS ZIP, parse, validate, import
GET   /api/gtfs/export    — Generate GTFS ZIP from database
GET   /api/gtfs/feed.zip  — Public GTFS feed download
GET   /api/gtfs-rt/vehicle-positions  — GTFS-Realtime VehiclePosition (Phase 2)
GET   /api/gtfs-rt/trip-updates       — GTFS-Realtime TripUpdate (Phase 2)
```

---

## 7. UI/UX Design

### 7.1 Layout Structure (Multi-Panel Dashboard)

```
┌─────────────────────────────────────────────────────────────────┐
│  [Logo]  Riga Transit CMS     🔍 Search...   🔔 Alerts   👤   │
├──────┬──────────────────────────────────────────┬───────────────┤
│      │                                          │               │
│  📍  │          MAIN CONTENT AREA               │  DETAIL       │
│Routes│                                          │  PANEL        │
│      │  (Map / Table / Form / Calendar)         │               │
│  📅  │                                          │  (Selected    │
│Sched │                                          │   item info,  │
│      │                                          │   edit form,  │
│  🚌  │                                          │   AI chat)    │
│Fleet │                                          │               │
│      │                                          │               │
│  👤  │                                          │               │
│Driver│                                          │               │
│      │                                          │               │
│  📊  │                                          │               │
│Report│                                          │               │
│      │                                          │               │
├──────┴──────────────────────────────────────────┴───────────────┤
│  Status Bar: 🟢 42 in service  🟡 3 delayed  🔴 1 alert       │
└─────────────────────────────────────────────────────────────────┘
```

### 7.2 Key Pages

**Route Management (`/routes`)**
- Left: Filterable route list (Tanstack Table) with color swatches
- Center: MapLibre map showing selected route shape + stops
- Right: Route detail panel (name, short name, type, edit form)
- Action: Click route → highlight on map → show stops in sequence

**Schedule Editor (`/schedules`)**
- Timetable grid: Rows = trips, Columns = stops, Cells = times
- Calendar selector: Service pattern (weekday/weekend/holiday)
- Time-distance diagram (Marey chart) for visual verification
- Inline editing with conflict detection

**Live Tracking (`/tracking`) — Phase 2**
- Full-screen MapLibre map with vehicle markers
- Vehicle markers: route number + color-coded adherence halo
- Click vehicle → sidebar with details (route, driver, ETA, speed)
- Bottom strip: route timeline / headway view
- Color coding: 🟢 on-time, 🟡 1-5 min late, 🔴 >5 min late

**AI Assistant (`/assistant`) — Phase 3**
- Chat interface in right sidebar
- Read-only queries: "Which buses are late?", "Show Route 22 status"
- No write operations through AI — suggestions only with approve/reject
- Token usage meter visible to dispatchers

### 7.3 Color Coding Standards

| Color | Meaning |
|---|---|
| 🟢 Green `#22c55e` | On-time / Normal / Active |
| 🟡 Amber `#f59e0b` | Minor delay (1-5 min) / Warning |
| 🔴 Red `#ef4444` | Major delay (>5 min) / Alert |
| 🔵 Blue `#3b82f6` | Informational / Selected |
| ⚪ Gray `#6b7280` | Out of service / Inactive / Stale data |

### 7.4 Internationalization

- **Primary:** Latvian (LV)
- **Secondary:** English (EN)
- Use `next-intl` for i18n
- GTFS data stored with both `name` and `name_lv` fields
- UI language selector in user profile

---

## 8. AI Agent Design (Phase 3)

### 8.1 Architecture: Advisory Mode Only

```
┌──────────────────────────────────────────────────┐
│                 DISPATCHER UI                     │
│                                                   │
│  "Which buses are running late?"                  │
│           │                                       │
│           ▼                                       │
│  ┌────────────────────────────┐                  │
│  │     QUERY CLASSIFIER       │                  │
│  │  (Haiku 4.5 — fast/cheap)  │                  │
│  └────────────┬───────────────┘                  │
│               │                                   │
│    Simple ────┤──── Complex                       │
│               │                                   │
│  ┌────────────▼───────────────┐                  │
│  │     QUERY EXECUTOR          │                  │
│  │  (Sonnet 4.5 — balanced)    │                  │
│  │                              │                  │
│  │  Tools:                      │                  │
│  │  - query_bus_status          │                  │
│  │  - get_route_schedule        │                  │
│  │  - get_ridership_data        │                  │
│  │  - check_driver_availability │                  │
│  │  - search_stops              │                  │
│  │                              │                  │
│  │  READ-ONLY. No mutations.    │                  │
│  └────────────┬───────────────┘                  │
│               │                                   │
│               ▼                                   │
│  ┌────────────────────────────┐                  │
│  │     RESPONSE + SUGGESTION   │                  │
│  │  "3 buses are >5 min late:  │                  │
│  │   Route 22, Route 7,        │                  │
│  │   Route 15.                  │                  │
│  │   [View on Map] [Dismiss]"   │                  │
│  └────────────────────────────┘                  │
└──────────────────────────────────────────────────┘
```

### 8.2 Cost Controls

| Control | Implementation |
|---|---|
| **Model routing** | Haiku 4.5 ($1/$5/MTok) for classification, Sonnet 4.5 ($3/$15/MTok) for reasoning |
| **Prompt caching** | Cache system prompt + tool definitions (0.1x cost on cache hits) |
| **Token budget** | Hard cap per user per day (e.g., 50 queries/user/day) |
| **Spending cap** | Hard limit on Anthropic account ($100/month) |
| **Fallback** | When API is unavailable → show "AI assistant is offline. Use search." |

### 8.3 Tools (Read-Only)

```typescript
const tools = [
  {
    name: 'query_bus_status',
    description: 'Get current status of buses (delayed, on-time, out of service)',
    parameters: { routeId: 'optional', status: 'optional' }
  },
  {
    name: 'get_route_schedule',
    description: 'Get schedule/timetable for a specific route',
    parameters: { routeId: 'required', date: 'optional' }
  },
  {
    name: 'search_stops',
    description: 'Search for bus stops by name or proximity',
    parameters: { query: 'optional', lat: 'optional', lon: 'optional', radius: 'optional' }
  },
  {
    name: 'get_adherence_report',
    description: 'Get on-time performance metrics',
    parameters: { routeId: 'optional', dateRange: 'optional' }
  },
  {
    name: 'check_driver_availability',
    description: 'Check which drivers are available for assignments',
    parameters: { date: 'required', shiftType: 'optional' }
  },
];
// NO write tools. AI cannot create, update, or delete anything.
```

---

## 9. Real-Time Tracking (Phase 2)

### 9.1 Data Flow

```
GPS Hardware (Bus)
    │
    │  HTTP POST /api/positions
    │  {vehicleId, lat, lon, speed, bearing, timestamp}
    │  (Authenticated with device certificate)
    │
    ▼
┌──────────────────────────┐
│   GPS Ingestion Endpoint  │
│                           │
│   1. Validate input       │
│   2. Distance filter      │  (Skip if moved < 10m)
│   3. Write to DB          │  (vehicle_positions + current_positions)
│   4. Broadcast via SSE    │  (In-process pub/sub → tRPC subscription)
└──────────────────────────┘
    │
    │  tRPC SSE subscription
    │  (tracking.positions)
    │
    ▼
┌──────────────────────────┐
│   MapLibre Dashboard      │
│                           │
│   - GeoJSON source layer  │
│   - Symbol layer markers  │
│   - 5-second update cycle │
│   - Color-coded adherence │
└──────────────────────────┘
```

### 9.2 Consuming Existing Feeds

Before building custom GPS ingestion, consume Rīgas Satiksme's existing data:

```typescript
// Poll SIRI stop departures API every 30 seconds
const pollSiriDepartures = async (stopId: string) => {
  const response = await fetch(
    `https://saraksti.rigassatiksme.lv/siri-stop-departures.php?stopid=${stopId}`
  );
  return response.json();
};

// Import GTFS feed for schedule data
const importGtfsFeed = async () => {
  const zip = await fetch('https://saraksti.rigassatiksme.lv/gtfs.zip');
  // Parse CSV files, validate, bulk insert into database
};
```

### 9.3 Stale Data Handling

| Condition | Display | Action |
|---|---|---|
| Position < 30s old | Normal marker | — |
| Position 30-120s old | Grayed marker + "Last seen X sec ago" | — |
| Position > 120s old | Ghost marker + warning icon | Alert dispatcher |
| No position ever received | Hidden from map | Show in "untracked vehicles" list |

---

## 10. Implementation Roadmap

### Phase 1: Core CMS (Weeks 1-8)

```
Week 1-2: Foundation
├── Initialize Next.js 16 + TypeScript project
├── Configure Drizzle ORM + Supabase PostgreSQL
├── Set up Auth.js v5 with role-based access
├── Implement tRPC v11 base router
├── Configure Tailwind v4 + Shadcn/ui
├── Set up MapLibre GL JS with OpenFreeMap tiles
├── ** SPIKE: Drizzle + PostGIS spatial query proof-of-concept **
└── Docker + GitHub Actions CI/CD

Week 3-4: GTFS Import & Data Model
├── GTFS ZIP parser (agencies, routes, stops, trips, stop_times, calendar, shapes)
├── Bulk import pipeline with validation
├── GTFS export (generate valid ZIP from database)
├── GTFS data integrity checks
└── Seed database with Rīgas Satiksme GTFS feed

Week 5-6: Route & Stop Management
├── Route list page (Tanstack Table, filters, search)
├── Route detail page with map visualization
├── Route CRUD (create, edit, delete with confirmation)
├── Stop list with proximity search
├── Stop management with map-based coordinate picker
├── Route shape display on MapLibre map
└── Stop sequence editor for routes

Week 7-8: Schedule Editor & Polish
├── Timetable grid view (trips × stops)
├── Service calendar management (weekday/weekend/holiday)
├── Calendar exception editor (holidays, events)
├── Schedule validation (conflict detection, GTFS compliance)
├── GTFS export verification
├── i18n (LV/EN) for all UI text
├── Basic search and filter across all entities
└── Testing, bug fixes, documentation

DELIVERABLE: Working CMS where dispatchers can view and edit
routes, stops, and schedules. GTFS import from Rīgas Satiksme.
```

### Phase 2: Live Operations (Weeks 9-16)

```
Week 9-10: Vehicle & Driver Management
├── Vehicle inventory CRUD
├── Driver management (pseudonymized, GDPR-compliant)
├── Vehicle-trip assignment
├── Driver-vehicle assignment
└── Maintenance status tracking

Week 11-12: Real-Time Tracking
├── GPS ingestion API endpoint (authenticated)
├── Vehicle position storage (current + historical)
├── In-process pub/sub for position broadcasting
├── tRPC SSE subscription for live positions
├── MapLibre real-time vehicle markers (symbol layer)
├── Vehicle detail sidebar on click
└── Stale data indicators

Week 13-14: Operational Dashboard
├── Fleet status overview (in-service, delayed, OOS counts)
├── On-time performance metrics
├── Route adherence monitoring
├── Basic alert/notification system
├── Schedule adherence calculation
└── Add Upstash Redis for SSE fan-out (if needed)

Week 15-16: Analytics & Reporting
├── Ridership data display (from APC if available)
├── On-time performance charts (Shadcn/ui charts)
├── Historical position playback on map
├── Export reports (CSV/PDF)
├── GTFS-Realtime VehiclePosition feed generation
└── Testing, hardening, GDPR audit

DELIVERABLE: Live tracking dashboard showing real-time bus
positions. Fleet and driver management. Basic analytics.
```

### Phase 3: Intelligence (Weeks 17-24)

```
Week 17-18: AI Assistant Foundation
├── Claude API integration (Sonnet 4.5 primary, Haiku 4.5 routing)
├── Tool definitions (5 read-only tools)
├── Prompt engineering with transit domain context
├── Chat UI in sidebar
├── Prompt caching for system prompt + tools
└── Token budget and spending cap implementation

Week 19-20: AI Enhancement & Suggestions
├── Proactive delay alerting
├── Schedule adherence analysis
├── Natural language search across all entities
├── Conversation history management
└── Fallback UI when API unavailable

Week 21-22: EU Standards Compliance
├── NeTEx export capability (EU requirement)
├── SIRI real-time information feed
├── GTFS-Realtime TripUpdate feed
├── Data validation against EU standards
└── Accessibility compliance (WCAG 2.1 AA)

Week 23-24: Advanced Features & Launch
├── Advanced dashboard layouts (parallel routes)
├── Keyboard shortcuts for dispatcher workflow
├── Performance optimization (Server Components, caching)
├── Security hardening (rate limiting, input validation)
├── Load testing (100+ vehicles)
├── GDPR Data Protection Impact Assessment (with legal counsel)
└── Production deployment

DELIVERABLE: Full-featured transit management CMS with AI
assistant, EU standards compliance, and production hardening.
```

---

## 11. Risk Register

| # | Risk | Probability | Impact | Mitigation |
|---|---|---|---|---|
| 1 | Drizzle + PostGIS integration fails | Medium | High | Week 1 spike. Fallback: raw SQL + Kysely. |
| 2 | Mapbox-to-MapLibre map quality gap | Low | Medium | Test with Riga data in Week 1. Tiles from OpenFreeMap. |
| 3 | GDPR violation from GPS tracking | High | Critical | Privacy-by-design. Engage Latvian DPA lawyer before Phase 2. |
| 4 | Claude API costs exceed budget | Medium | Medium | Hard spending cap ($100/month). Model routing (Haiku for simple). |
| 5 | Rīgas Satiksme GTFS feed format changes | Low | High | Validate on import. Alert on schema mismatch. |
| 6 | SSE connection limits under load | Low | Medium | HTTP/2 required. Single subscriber fan-out pattern. |
| 7 | Scope creep beyond 24-week plan | High | High | Strict phase gates. No Phase 2 features in Phase 1. |
| 8 | DST handling bugs | Medium | Medium | All timestamps UTC. Europe/Riga timezone at display only. |
| 9 | GPS signal loss in Old Town | Medium | Medium | Dead reckoning. Stale data visual indicators. |
| 10 | Auth.js v5 complexity for RBAC | Medium | Medium | Simple role enum (4 roles). JWT + middleware pattern. |

---

## 12. ISC Verification

### Updated ISC Status (Post-THINK Phase)

| # | What Ideal Looks Like | Source | Status |
|---|---|---|---|
| 1 | Route CRUD with map editing | EXPLICIT | ⏳ Phase 1 |
| 2 | Schedule management with calendar | EXPLICIT | ⏳ Phase 1 |
| 3 | Stop management with geolocation | EXPLICIT | ⏳ Phase 1 |
| 4 | Fleet/vehicle management | EXPLICIT | ⏳ Phase 2 |
| 5 | Driver management (GDPR-compliant) | EXPLICIT | ⏳ Phase 2 |
| 6 | Role-based access (4 roles) | IMPLICIT | ⏳ Phase 1 |
| 7 | Live map with vehicle positions | EXPLICIT | ⏳ Phase 2 |
| 8 | AI assistant (advisory, read-only) | EXPLICIT | ⏳ Phase 3 |
| 9 | GTFS import/export | INFERRED | ⏳ Phase 1 |
| 10 | GTFS-Realtime feed generation | INFERRED | ⏳ Phase 2 |
| 11 | Latvian language support | EXPLICIT | ⏳ Phase 1 |
| 12 | GDPR privacy-by-design | IMPLICIT | ⏳ Phase 2 |
| 13 | EU NeTEx/SIRI compliance | IMPLICIT | ⏳ Phase 3 |
| 14 | $31-117/month budget | INFERRED | ✅ Validated |
| 15 | 12 technologies, 1 language | INFERRED | ✅ Validated |
| 16 | Phased roadmap (3 × 8 weeks) | EXPLICIT | ✅ Documented |
| 17 | Architecture diagrams | IMPLICIT | ✅ Documented |
| 18 | Database schema | IMPLICIT | ✅ Documented |
| 19 | API catalog | IMPLICIT | ✅ Documented |
| 20 | UI wireframes | IMPLICIT | ✅ Documented |

### What Was Deliberately Excluded

| Feature | Reason | When to Reconsider |
|---|---|---|
| Google OR-Tools | Fixed routes don't need VRP solver | If demand-responsive transit is added |
| TimescaleDB | 20 writes/sec doesn't justify it | When fleet exceeds 500 vehicles |
| Microservices | 2-3 dev team can't maintain | When team grows to 6+ |
| WebSockets | SSE sufficient for unidirectional | If bidirectional driver chat is needed |
| Public passenger map | Scope limited to operator CMS | When passenger-facing features are requested |
| Fare management | Existing e-talons system handles this | When fare integration is needed |

---

## 5 Critical Questions Before Implementation

1. **Does Rīgas Satiksme have an existing AVL API beyond public GTFS-RT?** If yes, Phase 2 tracking simplifies dramatically — we consume their feed rather than building custom GPS ingestion.
2. **Who are the primary users — dispatchers, planners, or executives?** Interview actual staff to validate Phase 2-3 features and prioritize UI workflows accordingly.
3. **Deployment target — cloud (Railway/Vercel) or on-premise?** Cloud is assumed in cost estimates; on-premise municipal infrastructure changes the architecture significantly.
4. **GDPR — engage Latvian data protection counsel before Phase 2 GPS tracking.** Driver location data is personal data under GDPR. A Data Protection Impact Assessment (DPIA) is legally required before processing begins.
5. **Build-vs-buy analysis against Swiftly/Optibus pricing.** Get actual quotes to validate that a custom build is justified versus SaaS alternatives at $6,000-12,000/year.

---
