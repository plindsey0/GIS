# VAHomeMath Growth Intelligence System (GIS)
## Product Requirements Document — Version 3.0

**Date:** August 29, 2026  
**Status:** Build-ready product specification  
**Initial property:** VAHomeMath  
**Initial tenant:** Tenant 001 — VAHomeMath  
**Architecture:** Multi-tenant, multi-site capable from inception  
**Product category:** Growth Decision Intelligence  
**Initial operating mode:** Internal VAHomeMath growth system and commercial-product discovery environment

---

## 1. Executive Summary

The **Growth Intelligence System (GIS)** is a continuously operating decision-intelligence platform that integrates search, market, competitive, behavioral, technical, financial, content, authority, and first-party business evidence to determine:

> **What should we change next, why should we change it, what economic outcome should we expect, and did the intervention actually work?**

GIS originated as the growth intelligence infrastructure for VAHomeMath but shall be architected from inception as a potentially standalone, multi-tenant SaaS platform.

VAHomeMath serves simultaneously as:

1. The first production implementation of GIS.
2. Tenant 001.
3. The primary dogfood environment.
4. A controlled environment for validating recommendations.
5. The initial source of intervention/outcome observations.
6. The proving ground for future commercialization.

GIS shall not attempt to recreate SEMrush, Ahrefs, BuiltWith, Google Analytics, Search Console, CRM platforms, backlink indexes, or global SERP databases.

Instead, GIS sits **above existing data systems** and transforms heterogeneous evidence into prioritized decisions.

The fundamental operating loop is:

\[
\boxed{
Evidence
\rightarrow
Detection
\rightarrow
Opportunity
\rightarrow
Hypothesis
\rightarrow
Recommendation
\rightarrow
Decision
\rightarrow
Intervention
\rightarrow
Outcome
\rightarrow
Learning
}
\]

GIS v3.0 expands this model with a second major loop for authority acquisition:

\[
\boxed{
Data
\rightarrow
Finding
\rightarrow
Story
\rightarrow
ResearchAsset
\rightarrow
Outreach
\rightarrow
Coverage
\rightarrow
Citation
\rightarrow
Authority
\rightarrow
SearchOutcome
\rightarrow
EconomicOutcome
}
\]

The long-term strategic asset is not the software itself, nor third-party search data. It is the accumulated, rights-permitted dataset describing:

\[
\boxed{
Context + Intervention + Outcome
}
\]

This creates the possibility of eventually estimating:

\[
P(\text{Positive Outcome}\mid\text{Context, Intervention})
\]

and recommending interventions based on empirical historical effectiveness rather than generic SEO or marketing best practices.

---

# 2. Product Vision

GIS shall become the **decision and learning layer above the growth technology stack**.

Existing systems primarily answer observational questions:

**Google Search Console:** How did Google expose the site?

**GA4:** What did visitors do?

**SEMrush/Ahrefs:** What does the search market look like?

**BuiltWith:** What technologies are competitors using?

**CRM:** Which prospects converted?

**Revenue systems:** What was economically valuable?

**Git:** What changed?

**Market datasets:** What external conditions changed?

GIS shall answer:

> **Given everything currently known, what is the highest-value intervention available to us?**

After implementation:

> **Did the intervention produce the expected result?**

Over time:

> **What have we learned about which interventions work under which conditions?**

---

# 3. Product Positioning

GIS shall not be positioned commercially as:

- another SEO platform;
- another analytics dashboard;
- another rank tracker;
- another AI content generator;
- another backlink database;
- another business-intelligence tool.

The proposed category is:

# Growth Decision Intelligence

**Category definition:**

> Growth Decision Intelligence software integrates market, competitive, acquisition, behavioral, operational, financial, and other relevant evidence to identify, prioritize, recommend, measure, and learn from interventions intended to increase business growth.

The initial commercial wedge, if productized, shall be narrower:

> **GIS Search-to-Revenue identifies the highest-value changes a digital business should make based on its search, behavioral, competitive, and revenue data—and measures whether those changes worked.**

---

# 4. Core Product Question

Every major GIS feature shall ultimately contribute toward answering:

> **What should we do next?**

Every recommendation should explain:

1. **What happened?**
2. **Why does it matter?**
3. **What evidence supports the conclusion?**
4. **What action should be taken?**
5. **Why this action rather than alternatives?**
6. **What is the expected impact?**
7. **How confident is GIS?**
8. **What will implementation cost?**
9. **How will success be measured?**
10. **What happened after implementation?**
11. **What should GIS learn from the result?**

---

# 5. Product Principles

## 5.1 Own the intelligence layer

GIS shall acquire commodity observations where appropriate but concentrate proprietary development on:

- normalization;
- evidence synthesis;
- detection;
- opportunity discovery;
- economic prioritization;
- recommendation;
- intervention tracking;
- experimentation;
- outcome measurement;
- learning.

---

## 5.2 Observations are immutable

Historical observations shall generally be appended rather than overwritten.

GIS must preserve what was known at a given point in time.

---

## 5.3 Separate facts from interpretation

The system shall explicitly distinguish:

\[
Observation
\neq
Detection
\neq
Hypothesis
\neq
Recommendation
\]

Example:

**Observation**

Organic sessions decreased 18%.

**Detection**

Traffic decline anomaly.

**Hypothesis**

Ranking loss for Cluster X caused the decline.

**Recommendation**

Update Page A and strengthen internal links.

These must remain separate objects.

---

## 5.4 Deterministic analysis precedes AI reasoning

Whenever feasible:

\[
RawData
\rightarrow
SQL/Statistics
\rightarrow
DerivedEvidence
\rightarrow
AI
\]

rather than:

\[
RawData\rightarrow LLM\rightarrow Answer
\]

LLMs explain, synthesize, contextualize, and recommend.

They do not establish numerical ground truth.

---

# 6. Product Architecture

```text
                         GIS PLATFORM

                              │
                    DATA RIGHTS ENGINE
                              │
        ┌─────────────────────┼────────────────────┐
        │                     │                    │
      NATIVE                 BYOD              LICENSED
        │                     │                    │
 Public/Gov Data          GSC / GA4           Commercial
 GIS-collected Data       CRM / Git           Intelligence
                          Warehouse            Providers
                          Revenue
        │                     │                    │
        └─────────────────────┼────────────────────┘
                              │
                       INGESTION LAYER
                              │
                              ▼
                      RAW OBSERVATIONS
                              │
                       RIGHTS FILTERING
                              │
                              ▼
                    CANONICAL DATA MODEL
                              │
                              ▼
                         DBT / MARTS
                              │
        ┌─────────────────────┼──────────────────────┐
        ▼                     ▼                      ▼
    DETECTION             OPPORTUNITY            EVENTS
     ENGINE                 ENGINE                ENGINE
        │                     │                      │
        └─────────────────────┼──────────────────────┘
                              ▼
                         AI ANALYST
                              │
                              ▼
                      RECOMMENDATION
                              │
                         HUMAN REVIEW
                              │
                              ▼
                        INTERVENTION
                              │
                     GIT / DEPLOYMENT
                              │
                              ▼
                         MEASUREMENT
                              │
                              ▼
                           OUTCOME
                              │
                              ▼
                          LEARNING
```

---

# 7. Multi-Tenant Architecture

GIS shall be multi-tenant capable from inception.

Primary hierarchy:

```text
Tenant
   │
   ├── Organization
   │
   ├── Site
   │
   ├── Domain
   │
   ├── Data Sources
   │
   ├── Users
   │
   └── Policies
```

VAHomeMath shall be:

```text
Tenant 001
    │
    └── VAHomeMath.com
```

All appropriate records shall include:

```text
tenant_id
site_id
```

where applicable.

Tenant isolation must exist at the data-model level even if the initial user interface supports only VAHomeMath.

---

# 8. Data Integration Architecture

GIS shall support three integration classes.

## 8.1 Native GIS Sources

Sources GIS may acquire directly under appropriate terms.

Potential examples:

- Census;
- VA public datasets;
- FHFA datasets;
- other government/open datasets;
- GIS-generated site observations;
- properly licensed public economic data.

---

## 8.2 Bring Your Own Data — BYOD

Customer authorizes GIS to access customer-controlled systems.

Examples:

- Google Search Console;
- GA4;
- CRM;
- GitHub;
- customer databases;
- PostgreSQL;
- Snowflake;
- BigQuery;
- product analytics;
- revenue systems;
- customer files.

Typical architecture:

```text
Customer
   ↓
OAuth / API Key
   ↓
Provider
   ↓
GIS
```

---

## 8.3 Licensed Enrichment

Sources requiring GIS-specific commercial rights shall be handled separately.

Potential examples include commercial search, competitive, social, or technology-intelligence providers whose standard subscriptions do not necessarily permit third-party SaaS processing.

No provider shall be treated as BYOD merely because a customer possesses an API key.

---

# 9. Data Rights & Provenance Policy Engine

This becomes a first-class GIS subsystem.

Each source shall maintain machine-readable rights metadata.

Minimum fields:

```text
source_id
provider
connection_type

commercial_use_allowed
third_party_processing_allowed

deterministic_analysis_allowed
ai_inference_allowed
model_training_allowed

raw_storage_allowed
derived_storage_allowed

retention_days

raw_display_allowed
derived_display_allowed

aggregation_allowed
cross_tenant_learning_allowed

attribution_required
attribution_text

license_type
license_version
license_url
license_review_date

policy_notes
```

Each observation inherits applicable rights.

The policy engine determines whether the observation can participate in:

1. storage;
2. deterministic analytics;
3. AI inference;
4. customer-facing display;
5. aggregation;
6. training;
7. cross-tenant learning.

---

# 10. Separate Analytics, Inference and Learning

GIS shall treat these as distinct processing purposes.

### Deterministic analytics

```text
Observation
    ↓
SQL/statistics
    ↓
Metric
```

### AI inference

```text
Evidence
    ↓
LLM
    ↓
Recommendation
```

### Model learning

```text
Historical evidence
+ interventions
+ outcomes
    ↓
statistical/ML model
```

Permission for one shall not imply permission for another.

---

# 11. Customer-Side Execution

Future enterprise versions should support optional customer-side processing.

```text
CUSTOMER ENVIRONMENT

Warehouse
CRM
Analytics
Third-party sources
       │
       ▼
GIS Execution Agent
       │
       ▼
Permitted derived evidence
       │
       ▼
GIS Platform
```

Potential environments:

- AWS;
- Azure;
- GCP;
- Snowflake;
- BigQuery;
- PostgreSQL.

This capability may reduce:

- licensing exposure;
- privacy concerns;
- security concerns;
- raw-data movement.

---

# 12. Core Data Sources

## P0

- Google Search Console
- GA4
- first-party calculator telemetry
- lead/conversion telemetry
- Git/deployment history

## P1

- Census
- VA public data
- housing-market data
- mortgage-rate data
- Google Ads Keyword Planner
- Google Trends when operationally available
- direct SERP observations
- market/geographic data

## P2

- SEMrush where licensed
- Ahrefs where licensed
- DataForSEO
- BuiltWith where licensed
- Bing Webmaster
- competitor crawling
- Wayback
- Reddit/community intelligence where permitted
- YouTube
- autocomplete/related searches

## P3

- Common Crawl
- broader proprietary datasets
- customer-specific industry intelligence
- additional advertising platforms
- expanded economic datasets

---

# 13. Canonical Data Model

Major entities:

```text
Tenant
Organization
Site
Domain

Page
PageVersion

Keyword
KeywordCluster

SearchObservation
SERPObservation

Competitor
CompetitorPage
CompetitorEvent

TechnologyObservation
DomainRelationship
RedirectObservation

BacklinkObservation
AuthorityOpportunity

MarketObservation
GeographicObservation
UXObservation

Session
Event
CalculatorRun

Conversion
RevenueEvent

Commit
Deployment

Detection
Opportunity
Recommendation

Intervention
Experiment
Outcome

ResearchDataset
ResearchFinding
ResearchAsset

StoryOpportunity
OutreachTarget
OutreachActivity
MediaCoverage

Citation
EarnedBacklink

DataSource
DataRightsPolicy
```

---

# 14. Provenance Model

Every observation should support:

```text
observation_id
tenant_id
source_id
source_record_id

observed_at
ingested_at

effective_start
effective_end

raw_payload_reference

confidence
quality_flag

rights_policy_id
```

The objective is complete traceability:

\[
Recommendation
\rightarrow
Evidence
\rightarrow
Observation
\rightarrow
Source
\]

---

# 15. Search-to-Revenue Funnel

GIS shall maintain the canonical funnel:

\[
Impression
\rightarrow
Click
\rightarrow
Landing
\rightarrow
CalculatorStart
\rightarrow
CalculatorComplete
\rightarrow
CTA
\rightarrow
Lead
\rightarrow
Revenue
\]

Core metrics include:

\[
CTR=\frac{Clicks}{Impressions}
\]

\[
CSR=\frac{CalculatorStarts}{LandingSessions}
\]

\[
CCR=\frac{CalculatorCompletions}{CalculatorStarts}
\]

\[
LCR=\frac{Leads}{OrganicSessions}
\]

\[
ROV=\frac{Revenue}{OrganicSessions}
\]

---

# 16. Market Intelligence Layer

GIS shall incorporate exogenous market conditions so it does not incorrectly attribute every outcome to site changes.

Examples:

- interest rates;
- home prices;
- inflation;
- income;
- geography;
- population;
- housing transactions;
- veteran population;
- industry conditions.

Conceptually:

\[
ObservedOutcome=
InterventionEffect+
MarketEffect+
Seasonality+
Competition+
Noise
\]

GIS shall explicitly model these factors when practical.

---

# 17. VAHomeMath Research & Data Platform

A major new workstream shall establish VAHomeMath as a quantitative authority on veteran housing and VA lending.

Proposed public section:

```text
/research/

/va-loan-statistics/

/va-loans-by-state/

/va-loans-by-county/

/va-lenders/

/veteran-home-affordability/

/va-buying-power/

/va-loan-market-share/

/veteran-homeownership/

/reports/

/datasets/
```

A public **VA Loan Data Explorer** should eventually allow interactive exploration by:

- state;
- county;
- year;
- loan type;
- lender;
- affordability;
- buying power;
- utilization.

---

# 18. VA Purchase Penetration

Preferred definition:

\[
\boxed{
VAPP_{g,t}
=
\frac{VAPurchaseLoans_{g,t}}
{VeteranHouseholds_{g,t}}
\times1000
}
\]

Interpretation:

> Number of VA-financed home purchases per 1,000 veteran households during the period.

Fallback:

\[
\frac{VA Purchase Loans}{VeteranPopulation}\times1000
\]

when veteran-household estimates are unavailable.

The denominator must always be clearly disclosed.

---

# 19. VA Purchase Market Share

This shall remain distinct from penetration.

\[
\boxed{
VAMS=
\frac{VA Purchase Loans}
{All Financed Home Purchases}
\times100
}
\]

Potential source for denominator: appropriately processed mortgage-origination data such as HMDA.

This answers:

> What percentage of financed purchases in this market use VA financing?

---

# 20. VA Buying Power

Buying power shall first be calculated as an economically meaningful dollar value.

Given household income \(I\):

\[
HousingBudget=
\frac{I}{12}\theta
\]

where \(\theta\) is the standardized housing-cost threshold.

Initial research standard:

\[
\theta=0.30
\]

Subtract:

- property tax;
- insurance;
- HOA where appropriate;
- other modeled housing costs.

Maximum principal-and-interest payment:

\[
PI_{max}
=
HousingBudget
-
Taxes
-
Insurance
-
HOA
\]

Invert the mortgage formula:

\[
\boxed{
L_{max}
=
PI_{max}
\frac{(1+r)^n-1}
{r(1+r)^n}
}
\]

Then adjust for funding-fee and down-payment assumptions to derive:

\[
\boxed{VA Buying Power=\$P_{max}}
\]

---

# 21. VA Buying Power Index

The index shall measure purchasing capacity relative to a national veteran benchmark rather than local housing prices.

\[
\boxed{
BPI_{g,t}
=
100
\frac{VABuyingPower_{g,t}}
{NationalVeteranBuyingPower_t}
}
\]

Interpretation:

**100:** national benchmark

**120:** 20% more purchasing capacity

**80:** 20% less purchasing capacity

---

# 22. VA Affordability Index

GIS shall compare veteran household income with the income required to afford the representative local home.

Monthly housing cost:

\[
MHC=
PI+
Taxes+
Insurance+
HOA
\]

Required income:

\[
RequiredIncome=
\frac{12MHC}{\theta}
\]

Then:

\[
\boxed{
VAHI=
100
\frac{MedianVeteranHouseholdIncome}
{RequiredIncome}
}
\]

Interpretation:

**100:** representative veteran household can exactly afford representative home under index assumptions.

**120:** income is 20% above requirement.

**80:** income equals only 80% of requirement.

---

# 23. VA Affordability Gap

A more journalistically accessible companion measure:

\[
\boxed{
AffordabilityGap=
VABuyingPower-
RepresentativeHomePrice
}
\]

Example:

\[
\$310K-\$350K=-\$40K
\]

Interpretation:

> The representative veteran household is approximately $40,000 short of being able to afford the representative local home.

---

# 24. VA Housing Advantage

Compare standardized purchasing capacity using VA versus alternative financing.

\[
\boxed{
VAHousingAdvantage=
P_{max}^{VA}-P_{max}^{Alternative}
}
\]

Potential alternatives:

- conventional 5% down;
- conventional 10% down;
- FHA.

This allows statements such as:

> VA financing provides approximately $31,000 of additional modeled buying power for the representative household.

---

# 25. VA Utilization Opportunity

GIS shall identify markets where VA financing appears underutilized relative to underlying conditions.

Conceptually:

\[
UtilizationOpportunity
=
f(
Affordability,
VeteranPopulation,
HousingActivity,
VAPenetration,
VAMarketShare
)
\]

High-opportunity markets generally exhibit:

- substantial veteran population;
- adequate affordability;
- active housing market;
- unusually low VA utilization.

This is an analytical signal, not proof of unmet demand or discriminatory behavior.

---

# 26. Research Dataset

Canonical geography-period dataset should eventually contain:

```text
geography_id
period

veteran_population
veteran_households
veteran_median_household_income

va_purchase_loans
va_purchase_volume
va_refinance_loans
va_cashout_loans
va_average_purchase_loan

all_purchase_mortgages

representative_home_price
home_price_growth
property_tax_rate
insurance_cost
hoa_estimate

mortgage_rate
funding_fee_assumption
term
housing_cost_threshold

va_purchase_penetration
va_purchase_market_share

va_buying_power
va_buying_power_index

va_affordability_index
va_affordability_gap

va_housing_advantage
va_utilization_opportunity
```

Historical observations must not be overwritten.

---

# 27. Research Asset Engine

GIS shall distinguish raw datasets from publishable research assets.

Potential asset types:

```text
STATISTICS_PAGE
DATASET
INDEX
RANKING
INTERACTIVE_TOOL
CALCULATOR
RESEARCH_REPORT
MAP
CHART
METHODOLOGY
EXPERT_ANALYSIS
NEWS_RELEASE
```

GIS should identify opportunities where proprietary analysis could create an authoritative reference resource.

---

# 28. Authority Intelligence

GIS v3.0 expands backlink analysis into **Authority Intelligence**.

The objective is not:

> Get backlinks.

The objective is:

> Create and distribute assets that reputable sources have legitimate reasons to cite.

Authority intelligence shall combine:

- backlink observations;
- competitor backlinks;
- linking domains;
- linked pages;
- content type;
- citation context;
- domain relevance;
- authority;
- acquired links;
- referral traffic;
- subsequent search outcomes.

---

# 29. Link Reason Classification

GIS should classify why a third party linked to an asset.

Initial taxonomy:

```text
STATISTIC
DATASET
RESEARCH
CALCULATOR
TOOL
EXPERT_QUOTE
NEWS_STORY
RESOURCE_PAGE
ORGANIZATION_REFERENCE
POLICY_REFERENCE
METHODOLOGY
DIRECTORY
PARTNERSHIP
OTHER
```

This enables GIS to move beyond:

> Competitor has 500 links.

toward:

> 37 reputable domains link to competitor statistical resources, while this site has no equivalent asset.

That creates an actionable authority opportunity.

---

# 30. Authority Opportunity Engine

The engine shall analyze:

\[
LinkingDomain
\rightarrow
Competitor
\rightarrow
LinkedAsset
\rightarrow
ReasonForLink
\]

and recommend opportunities such as:

> Create authoritative statistics page.

> Publish original dataset.

> Build embeddable tool.

> Produce research answering frequently cited question.

> Offer expert commentary.

> Update an obsolete reference resource.

---

# 31. Linkability Score

Proposed asset-level metric:

\[
\boxed{
L=
w_1D+
w_2O+
w_3N+
w_4U+
w_5J+
w_6R
}
\]

where:

- \(D\) = data uniqueness;
- \(O\) = originality;
- \(N\) = newsworthiness;
- \(U\) = utility;
- \(J\) = journalist usefulness;
- \(R\) = reference longevity.

Normalized:

\[
0\le L\le100
\]

GIS should prioritize assets with high expected citation utility rather than simply high keyword volume.

---

# 32. Digital PR Intelligence

GIS shall identify findings with potential media value.

The workflow:

```text
Dataset refresh
      ↓
Derived metrics
      ↓
Anomaly detection
      ↓
Finding
      ↓
Newsworthiness score
      ↓
Story opportunity
      ↓
Target audience
      ↓
Supporting assets
      ↓
Outreach
      ↓
Coverage
      ↓
Citation/backlink
      ↓
Traffic/ranking
      ↓
Economic outcome
```

---

# 33. Newsworthiness Score

Proposed:

\[
\boxed{
N=
w_1U+
w_2M+
w_3H+
w_4T+
w_5L+
w_6C
}
\]

where:

- \(U\) = unexpectedness;
- \(M\) = magnitude;
- \(H\) = human impact;
- \(T\) = timeliness;
- \(L\) = localization potential;
- \(C\) = counterintuitiveness.

Normalized to 0–100.

A high-value finding should not merely be statistically unusual. It should also have a plausible human story.

---

# 34. Story Opportunity Object

GIS shall create structured story opportunities.

Example:

```text
story_opportunity_id
tenant_id
finding_id

headline_candidate
summary
newsworthiness_score
confidence

geography
population_affected

timeliness_trigger

national_relevance
localization_potential

target_audience

supporting_dataset
supporting_chart
supporting_methodology
supporting_tool

recommended_outreach_date
status
```

---

# 35. Initial VAHomeMath Story Taxonomy

GIS should actively search for findings supporting stories involving:

### Affordability

- veterans being priced out;
- improving affordability;
- deteriorating affordability;
- affordability gaps;
- most/least affordable markets.

### Military communities

- military-town affordability;
- installation-adjacent markets;
- veteran-heavy communities.

### Buying power

- interest-rate shocks;
- income changes;
- home-price changes;
- purchasing-power losses/gains.

### VA utilization

- low utilization;
- high utilization;
- unexplained regional differences;
- VA market share.

### Financing advantage

- VA versus conventional;
- VA versus FHA;
- funding-fee impact;
- exemptions.

### Geography

- state rankings;
- county rankings;
- metros;
- migration;
- regional divergence.

### Policy

- VA rule changes;
- state veteran benefits;
- property-tax exemptions;
- housing-policy effects.

### Ownership costs

- insurance;
- taxes;
- HOA;
- disaster exposure.

### Demographics

- age cohorts;
- income groups where supportable;
- first-time buyer patterns where supportable.

### Lending industry

- largest VA lenders;
- fastest-growing lenders;
- lender exits;
- lender concentration;
- regional lender dominance.

### Technology/AI

- accuracy of AI-generated VA-loan guidance;
- changing search behavior;
- AI visibility of authoritative VA information.

---

# 36. Localization Engine

A single national finding should be evaluated for state, county and metro derivatives.

Example:

```text
National:
Veteran affordability fell 6%.

Florida:
Veteran affordability fell 11%.

Miami:
Veteran affordability fell 17%.

County X:
Affordability gap reached -$118K.
```

GIS should identify which local observations materially diverge from national baselines.

This creates potentially hundreds of legitimate localized story opportunities from a single dataset.

---

# 37. Outreach Management

GIS is not initially intended to become a full CRM.

However, it should maintain enough information to measure authority-acquisition interventions.

Entities:

```text
OutreachTarget
Journalist
Publication
Organization
OutreachCampaign
OutreachActivity
MediaCoverage
Citation
Backlink
```

Initial states:

```text
IDENTIFIED
QUALIFIED
CONTACTED
RESPONDED
INTERESTED
COVERED
DECLINED
NO_RESPONSE
```

---

# 38. Coverage and Citation Measurement

GIS shall track:

\[
ResearchAsset
\rightarrow
Outreach
\rightarrow
Coverage
\rightarrow
Backlink
\]

and then:

\[
Backlink
\rightarrow
RankingChange
\rightarrow
TrafficChange
\rightarrow
ConversionChange
\rightarrow
RevenueChange
\]

This allows authority acquisition itself to become measurable.

---

# 39. Competitive Intelligence

Competitive intelligence shall consist of three layers.

## 39.1 Content Intelligence

Scrapy + Playwright.

Observe:

- pages;
- headings;
- metadata;
- structured data;
- tools;
- calculators;
- content changes;
- internal links;
- new content clusters.

## 39.2 Technology Intelligence

Where properly licensed:

- technology adoption;
- technology removal;
- analytics;
- experimentation;
- CRM;
- advertising;
- hosting;
- CMS;
- related domains;
- redirects.

## 39.3 Market Intelligence

Where properly licensed:

- rankings;
- keywords;
- backlinks;
- traffic estimates;
- SERP features;
- search demand.

---

# 40. Competitor Event Model

```text
event_id
tenant_id
organization_id
domain_id

event_date
event_type

source_id
confidence

description
evidence
```

Initial taxonomy:

```text
TECHNOLOGY_ADDED
TECHNOLOGY_REMOVED

PAGE_CREATED
PAGE_REMOVED
PAGE_CHANGED

KEYWORD_GAIN
KEYWORD_LOSS

BACKLINK_SURGE

DOMAIN_REDIRECT
NEW_RELATED_DOMAIN

SERP_GAIN
SERP_LOSS

UX_CHANGE
NEW_CONTENT_CLUSTER
NEW_CALCULATOR_OR_TOOL
POSITIONING_CHANGE

NEW_RESEARCH_ASSET
MEDIA_COVERAGE_SURGE
AUTHORITY_GAIN
```

---

# 41. Lender Intelligence

VAHomeMath research should eventually maintain lender-level longitudinal observations.

Potential metrics:

- VA purchase volume;
- total VA volume;
- purchase/refinance mix;
- geography;
- growth;
- decline;
- market share;
- concentration.

Lender concentration may use:

\[
\boxed{
HHI=\sum_i s_i^2
}
\]

where \(s_i\) represents lender market share.

This enables industry-level research in addition to consumer research.

---

# 42. Content Provenance Intelligence

GIS shall analyze the authority structure of important content.

Potential graph:

\[
Page\rightarrow Claim\rightarrow Source
\]

Capture:

```text
claim_id
page_id
claim_text
source_url
source_type
publication_date
accessed_at
authority_class
citation_status
```

Potential source classes:

```text
PRIMARY_GOVERNMENT
ACADEMIC
REGULATORY
INDUSTRY
NEWS
COMMERCIAL
INTERNAL_RESEARCH
OTHER
```

GIS should recommend improvements where important claims lack appropriate authoritative support.

---

# 43. Detection Engine

P0/P1 detections:

- ranking opportunity;
- ranking decline;
- traffic decline;
- traffic surge;
- CTR underperformance;
- emerging query;
- conversion anomaly;
- high-value page;
- calculator anomaly;
- tracking failure;
- ingestion failure.

Expanded detections:

- competitor displacement;
- content gap;
- keyword gap;
- backlink gap;
- authority gap;
- internal-link opportunity;
- cannibalization;
- new competitor;
- competitor technology change;
- competitor content change;
- SERP feature change;
- market shock;
- affordability anomaly;
- penetration anomaly;
- buying-power change;
- research opportunity;
- PR opportunity;
- citation opportunity;
- linkable-asset opportunity.

---

# 44. Opportunity Engine

Generalized opportunity score:

\[
\boxed{
O=
w_1D+
w_2V+
w_3I+
w_4P+
w_5C+
w_6E+
w_7S+
w_8N
-
w_9K
-
w_{10}U
}
\]

where:

- \(D\) = demand magnitude;
- \(V\) = demand velocity;
- \(I\) = intent value;
- \(P\) = position potential;
- \(C\) = conversion potential;
- \(E\) = economic value;
- \(S\) = strategic fit;
- \(N\) = newsworthiness/authority value where applicable;
- \(K\) = implementation cost;
- \(U\) = uncertainty.

Not every opportunity type must use every factor.

---

# 45. AI Analyst

The AI analyst shall consume controlled functions rather than arbitrary database access.

Functions include:

```text
get_page_performance
get_keyword_performance
get_query_cluster

get_market_context
get_geographic_context

get_conversion_metrics
get_calculator_metrics

get_serp_context

get_competitor_rankings
get_competitor_events
get_technology_changes

get_backlink_gap
get_authority_profile
get_link_reasons

get_content_gap
get_ux_gap

get_page_changes
get_deployments

get_research_findings
get_newsworthy_anomalies

get_previous_interventions
get_similar_experiments

get_source_provenance
get_data_rights
```

---

# 46. Recommendation Object

```text
recommendation_id
tenant_id
site_id

type
priority
confidence

finding
hypothesis

evidence[]

recommended_actions[]

expected_impact
expected_economic_value

implementation_effort
implementation_risk

measurement_plan

generated_at
status
```

---

# 47. Recommendation Taxonomy

```text
TECHNICAL
CONTENT
KEYWORD
INTERNAL_LINKING

AUTHORITY
BACKLINK
RESEARCH
DIGITAL_PR

CTR
UX
CALCULATOR
CONVERSION

NEW_CONTENT
NEW_TOOL

COMPETITIVE_RESPONSE
SERP
GEOGRAPHIC

PROVENANCE
MARKET_TIMING

DATA_QUALITY
INTEGRATION
```

---

# 48. AI Guardrails

GIS AI shall:

- cite internal evidence;
- distinguish fact from hypothesis;
- expose uncertainty;
- never fabricate metrics;
- respect data-rights policies;
- never expose one tenant's raw data to another;
- never send prohibited source data to external models;
- never automatically publish production content in v1;
- never directly modify production systems in v1;
- never perform arbitrary SQL;
- produce measurable recommendations.

---

# 49. Growth Queue

The principal GIS interface should emphasize decisions rather than dashboards.

Example:

```text
YOUR GROWTH QUEUE

──────────────────────────────────

$47K OPPORTUNITY                 91
Create state affordability pages

Confidence: 84%
Evidence: 7 sources
Effort: Medium

[Investigate] [Accept]

──────────────────────────────────

AUTHORITY OPPORTUNITY            89
Publish 2027 VA Affordability Index

Expected citation potential: High
Newsworthiness: 93
Effort: Medium

[Investigate] [Accept]

──────────────────────────────────

$21K OPPORTUNITY                 87
Improve calculator completion

Confidence: 91%
Effort: Low

[Investigate] [Accept]
```

Dashboards support analysis.

The **Growth Queue drives action.**

---

# 50. Recommendation Workflow

Statuses:

```text
PROPOSED
ACCEPTED
REJECTED
DEFERRED
IMPLEMENTED
MEASURING
SUCCESSFUL
NEUTRAL
NEGATIVE
INCONCLUSIVE
```

Rejected recommendations should capture a reason where possible.

---

# 51. Intervention Tracking

```text
intervention_id
tenant_id

recommendation_id
page_id

accepted_at
implemented_at

implementation_commit
deployment_id

intervention_type

estimated_cost
actual_cost

status
```

---

# 52. Experimentation

Initial methodology:

\[
28dBefore
\quad vs \quad
28dAfter
\]

where appropriate.

Measure:

- rankings;
- impressions;
- clicks;
- CTR;
- sessions;
- calculator starts;
- completions;
- leads;
- revenue;
- backlinks;
- referring domains.

Later versions should support:

- control groups;
- seasonality adjustment;
- market adjustment;
- algorithm-update controls;
- difference-in-differences;
- Bayesian inference;
- causal models.

GIS must not equate correlation with causation.

---

# 53. Authority Intervention Measurement

Research/PR interventions require additional outcomes:

```text
outreach_targets
outreach_attempts
responses
coverage_count
citations
earned_backlinks
referring_domains
referral_sessions

ranking_change
organic_traffic_change
conversion_change
revenue_change
```

Potential efficiency metric:

\[
AuthorityROI=
\frac{EstimatedEconomicBenefit}
{ResearchCost+OutreachCost}
\]

---

# 54. Learning Layer

The canonical learning object:

\[
Context
\rightarrow
Intervention
\rightarrow
Outcome
\]

Context should include where permitted:

- site type;
- page type;
- industry;
- intent;
- starting rank;
- traffic;
- conversion;
- authority;
- market;
- competition;
- season;
- intervention cost.

Eventually GIS should estimate:

\[
P(Success\mid Context,Intervention)
\]

---

# 55. Cross-Tenant Learning

Cross-tenant learning shall occur only where:

1. customer agreements permit it;
2. upstream source rights permit it;
3. privacy/security policies permit it;
4. sufficient aggregation/de-identification exists.

Rights engine:

```text
Observation
      ↓
Rights Evaluation
      │
 ┌────┴──────────────┐
 ▼                   ▼
Tenant-only      Learning eligible
```

The preferred long-term learning dataset emphasizes:

\[
CustomerOwnedContext
+
GISRecommendation
+
Intervention
+
Outcome
\]

rather than reproducing proprietary third-party datasets.

---

# 56. Analytical Marts

Required/planned marts:

```text
mart_site_daily
mart_page_daily
mart_keyword_daily
mart_keyword_page_daily

mart_conversion_daily
mart_calculator_performance
mart_search_funnel

mart_market_geo
mart_serp_visibility

mart_competitor_daily
mart_competitor_events
mart_technology_changes

mart_backlink_gap
mart_authority_profile
mart_authority_opportunities

mart_content_gap
mart_ux_gap

mart_va_lending
mart_va_affordability
mart_va_buying_power
mart_va_penetration
mart_va_lenders

mart_research_findings
mart_story_opportunities

mart_page_opportunities
mart_keyword_opportunities
mart_market_opportunities

mart_content_changes

mart_experiment_results
mart_authority_results

mart_recommendation_effectiveness
```

---

# 57. Reporting

## Daily

Only meaningful anomalies:

- tracking failures;
- API failures;
- severe ranking changes;
- traffic anomalies;
- conversion anomalies;
- major competitor events;
- major market events.

## Weekly Growth Brief

Automatically generated:

1. performance summary;
2. major gains;
3. major losses;
4. emerging demand;
5. competitor movements;
6. conversion findings;
7. authority findings;
8. research findings;
9. story opportunities;
10. top five recommended interventions;
11. active experiment status;
12. completed intervention results.

## Monthly

Emphasis on:

\[
Search\rightarrow Traffic\rightarrow Lead\rightarrow Revenue
\]

plus:

\[
Recommendation\rightarrow Intervention\rightarrow Outcome\rightarrow Learning
\]

and:

\[
Research\rightarrow Coverage\rightarrow Authority\rightarrow SearchOutcome
\]

---

# 58. Dashboards

Metabase initially.

Required dashboards:

### Executive

Growth, revenue, opportunities.

### Search

Keywords, rankings, CTR, SERPs.

### Pages

Page-level performance.

### Calculators

Product engagement and conversion.

### Market

External demand and geography.

### Competition

Competitor events and gaps.

### Authority

Backlinks, referring domains, citation opportunities.

### Research

VA statistics, affordability, penetration, buying power.

### PR

Story opportunities, outreach, coverage.

### Experiments

Interventions and outcomes.

### Recommendations

Queue, status, effectiveness.

### Data Health

Freshness, failures, rights status.

---

# 59. Technical Stack

Initial architecture:

- **Application:** existing Next.js application/admin
- **Database:** PostgreSQL
- **Ingestion:** Python
- **Transformation:** dbt Core
- **BI:** Metabase OSS
- **Crawler:** Scrapy
- **Browser automation:** Playwright
- **Containers:** Docker Compose
- **Scheduling:** cron/systemd initially
- **Source control:** Git
- **AI:** Ollama + suitable open model and/or swappable API adapter
- **Semantic memory:** pgvector later
- **Secrets:** appropriate environment/secret-management service

Avoid initially:

- Kafka;
- Kubernetes;
- Spark;
- Snowflake unless required by scale/customer;
- dedicated data lake;
- complex orchestration platforms;
- custom foundation models.

---

# 60. Product Epics

## Epic 1 — Data Platform Foundation — P0

Implement PostgreSQL schemas, tenants, sites, provenance, source registry and historical observations.

## Epic 2 — Search Console Integration — P0

Automated daily GSC ingestion.

## Epic 3 — GA4 Integration — P0

Automated behavioral analytics ingestion.

## Epic 4 — First-Party Product Telemetry — P0

Calculator, CTA, lead and conversion events.

## Epic 5 — Analytical Transformation — P0

dbt models and core marts.

## Epic 6 — Growth Dashboard — P0

Initial operational dashboards.

## Epic 7 — Detection & Opportunity Engine — P1

Rules, anomaly detection and opportunity scoring.

## Epic 8 — AI Recommendation Engine — P1

Evidence-controlled recommendations.

## Epic 9 — Intervention & Experiment Tracking — P1

Closed recommendation-to-outcome loop.

## Epic 10 — Data Rights & Provenance Engine — P1

Machine-readable source rights and enforcement.

## Epic 11 — Market Intelligence — P1

Veteran, housing, geographic and economic context.

## Epic 12 — VA Research Dataset — P1

Canonical longitudinal VA housing/lending dataset.

## Epic 13 — VA Metrics Engine — P1

Calculate penetration, market share, buying power, affordability, affordability gap and related metrics.

## Epic 14 — VA Research & Data Experience — P1/P2

Statistics pages, datasets and Data Explorer.

## Epic 15 — SERP & Experience Intelligence — P1/P2

SERP composition and CrUX/experience intelligence.

## Epic 16 — External Search Intelligence — P2

Provider-independent commercial search intelligence.

## Epic 17 — Competitive Content Intelligence — P2

Scrapy + Playwright.

## Epic 18 — Competitive Technology Intelligence — P2

Properly licensed technology and domain intelligence.

## Epic 19 — Competitive Event Synthesis — P2

Cross-source competitor events.

## Epic 20 — Authority Intelligence — P2

Backlink analysis, link-reason classification and authority gaps.

## Epic 21 — Research Asset Opportunity Engine — P2

Recommend linkable data/research/tools.

## Epic 22 — Newsworthiness Engine — P2

Detect findings and score media potential.

## Epic 23 — Digital PR Workflow — P2

Story opportunities, outreach and coverage measurement.

## Epic 24 — Content Provenance Intelligence — P2

Claim/source graph and authority analysis.

## Epic 25 — Historical Web Intelligence — P2/P3

Wayback/Common Crawl where appropriate.

## Epic 26 — Emerging Demand Intelligence — P2

Trends, community, autocomplete and other early signals.

## Epic 27 — Learning Layer — P2/P3

Recommendation/intervention effectiveness.

## Epic 28 — Semantic Memory — P3

pgvector/RAG where justified.

## Epic 29 — Multi-Site Portfolio Intelligence — P3

Cross-site resource allocation.

## Epic 30 — Commercial Multi-Tenant GIS — P3

Authentication, billing, onboarding, tenant administration and commercial controls.

## Epic 31 — Customer-Side Execution — P3

Enterprise BYOC/BYOD execution agent.

---

# 61. Recommended Delivery Phases

## Phase 0 — Foundation

Epics 1–6.

Objective:

> Establish trustworthy automated observation infrastructure.

---

## Phase 1 — Closed Decision Loop

Epics 7–10.

Objective:

\[
Observation
\rightarrow Recommendation
\rightarrow Intervention
\rightarrow Outcome
\]

This is the most important GIS validation.

---

## Phase 2 — VAHomeMath Proprietary Intelligence

Epics 11–14.

Objective:

> Transform VAHomeMath from a calculator site into a proprietary veteran-housing research and data property.

This phase has now become strategically important.

---

## Phase 3 — Search & Competition

Epics 15–19.

Objective:

> Understand the external search and competitive environment.

---

## Phase 4 — Authority & Media

Epics 20–24.

Objective:

\[
Research
\rightarrow Story
\rightarrow Citation
\rightarrow Authority
\]

This establishes the reputable backlink acquisition engine.

---

## Phase 5 — Expanded Intelligence

Epics 25–26.

Objective:

> Detect earlier signals and reconstruct historical market behavior.

---

## Phase 6 — Learning

Epics 27–29.

Objective:

> Learn which interventions work under which conditions.

---

## Phase 7 — GIS Commercialization

Epics 30–31.

Objective:

> Convert validated internal infrastructure into a sellable Growth Decision Intelligence platform.

---

# 62. MVP Definition

The **GIS MVP should remain considerably smaller than the complete vision**.

Required:

```text
PostgreSQL
GSC
GA4
First-party telemetry
Git/deployment observations
dbt
Metabase

Detection engine
Opportunity engine

AI recommendations
Growth Queue

Intervention tracking
Outcome measurement

Tenant-aware schema
Source provenance
Basic data-rights model
```

Do **not** put into the core MVP:

- SEMrush;
- Ahrefs;
- BuiltWith;
- Common Crawl;
- Reddit;
- full competitor crawling;
- sophisticated PR tooling;
- pgvector;
- custom ML;
- commercial billing;
- enterprise BYOC.

The first question to prove is:

> **Can GIS reliably identify useful interventions for VAHomeMath and learn from their outcomes?**

---

# 63. VA Research MVP

This should run immediately after or partially parallel to the core GIS MVP.

Initial deliverable:

## VA Loan Statistics & Affordability Dataset v1

Start with:

- state;
- county where data quality permits;
- year/quarter;
- veteran population;
- veteran households;
- veteran income;
- VA purchase loans;
- VA loan volume;
- home-price estimate;
- mortgage-rate assumption;
- taxes where feasible;
- insurance where feasible.

Calculate:

1. VA Purchase Penetration
2. VA Buying Power
3. VA Buying Power Index
4. VA Affordability Index
5. VA Affordability Gap

Then publish:

### VA Loan Statistics

### VA Loans by State

### Veteran Home Affordability

### VA Buying Power

plus a downloadable methodology.

This should produce the first real test of the:

\[
Research\rightarrow Authority
\]

hypothesis.

---

# 64. MVP Acceptance Criteria

Core GIS MVP is complete when:

- GSC automatically ingests daily;
- GA4 automatically ingests daily;
- calculator telemetry is captured;
- pages, queries and sessions associate correctly;
- history is preserved;
- dbt marts build reliably;
- at least five detection rules operate;
- opportunities receive explainable scores;
- AI receives controlled evidence;
- AI recommendations are structured;
- recommendations appear in Growth Queue;
- users can accept/reject/defer;
- accepted recommendations become interventions;
- interventions can associate with Git/deployment changes;
- outcomes can be measured;
- basic provenance exists;
- basic source-rights policies exist;
- a second `tenant_id` and `site_id` can be introduced without schema redesign.

---

# 65. VA Research Acceptance Criteria

The research system is successful when:

- authoritative source provenance is retained;
- geographic joins are reproducible;
- calculation methodology is versioned;
- historical values are preserved;
- buying-power calculations are reproducible;
- affordability calculations are reproducible;
- penetration calculations disclose denominators;
- national and state comparisons are generated automatically;
- statistically notable changes can be detected;
- methodology can be published publicly;
- research outputs can feed GIS recommendations.

---

# 66. Authority Intelligence Acceptance Criteria

Successful when GIS can:

- ingest or receive backlink observations from an authorized source;
- associate links with target assets;
- classify link reason;
- identify competitor assets earning reputable links;
- detect authority gaps;
- recommend an appropriate linkable asset;
- score linkability;
- associate subsequent coverage/backlinks with the asset;
- measure downstream search performance.

---

# 67. PR Intelligence Acceptance Criteria

Successful when GIS can:

1. detect a notable research finding;
2. calculate Newsworthiness Score;
3. identify geographic scope;
4. generate plausible story framing;
5. identify appropriate audience categories;
6. identify supporting data/assets;
7. track outreach;
8. record coverage;
9. record citations/backlinks;
10. measure subsequent authority/search effects.

AI-generated headlines remain suggestions requiring human judgment.

---

# 68. Commercialization Readiness Gates

Do not commercialize GIS merely because the software works.

Recommended gates:

### Gate 1 — Recommendation usefulness

At least:

\[
50-100
\]

real GIS recommendations generated.

### Gate 2 — Intervention evidence

At least:

\[
20-30
\]

measured interventions.

### Gate 3 — Positive signal

Evidence that accepted GIS recommendations produce useful economic or growth outcomes often enough to justify continued use.

### Gate 4 — External portability

GIS operates successfully on:

\[
3-5
\]

sites unrelated to VAHomeMath.

### Gate 5 — Design partners

Test with:

\[
10-20
\]

external users/organizations.

### Gate 6 — Integration viability

Required commercial data-source rights and OAuth/API requirements are understood.

### Gate 7 — Multi-tenant security

Tenant isolation, authentication, secrets, deletion and audit controls are production-ready.

Only then invest heavily in commercial SaaS polish.

---

# 69. Initial Commercial ICP

If productized, prioritize businesses with:

- $2M–$50M revenue;
- meaningful digital acquisition;
- measurable conversion;
- substantial organic/search exposure;
- multiple disconnected growth systems;
- limited internal data-science capacity.

Candidate industries:

- financial lead generation;
- mortgage;
- insurance;
- legal;
- healthcare;
- education;
- SaaS;
- marketplaces;
- directories;
- travel;
- home services.

Secondary ICP:

### Agencies

GIS could become intelligence infrastructure across many clients.

### Multi-site operators

Portfolio companies, publishers, directories, franchise systems and lead-generation portfolios.

---

# 70. Commercial Onboarding Strategy

Do not initially require 15 integrations.

### Stage 1

```text
Website
+
GSC
+
GA4
```

Promise:

> **Here are the five highest-value things to investigate this week.**

### Stage 2

Add:

```text
CRM
Revenue
```

### Stage 3

Add:

```text
Search intelligence
Backlinks
```

### Stage 4

Add:

```text
Competition
Technology
Market data
```

### Stage 5

Add:

```text
Custom datasets
Product analytics
Paid media
AI-search intelligence
```

Each connection should visibly increase GIS confidence or capability.

---

# 71. Success Metrics

## Product usage

\[
RecommendationAcceptanceRate=
\frac{Accepted}{Generated}
\]

\[
ImplementationRate=
\frac{Implemented}{Accepted}
\]

## Recommendation quality

\[
PositiveInterventionRate=
\frac{PositiveOutcomes}{MeasuredInterventions}
\]

Track:

- recommendation precision;
- false-alert rate;
- time to insight;
- time to intervention.

## Economic impact

\[
IncrementalEconomicValue=
Revenue_{actual}-Revenue_{counterfactual}
\]

where sufficiently estimable.

## Research

- research assets published;
- dataset citations;
- referring domains;
- media mentions;
- dataset downloads;
- Data Explorer usage.

## Authority

- reputable referring domains acquired;
- earned-link rate;
- coverage rate;
- links per research asset;
- authority opportunity conversion;
- ranking improvement after authority interventions.

## Learning

- measured interventions;
- contextual completeness;
- recommendation types with sufficient outcome history;
- prediction calibration.

---

# 72. Data Quality Metrics

Every important source should expose:

```text
last_successful_ingestion
expected_frequency
record_count
freshness
completeness
error_rate
schema_status
rights_status
```

GIS must never silently make recommendations from stale or failed data.

---

# 73. Security Requirements

Minimum:

- encryption in transit;
- encryption at rest;
- least-privilege credentials;
- encrypted API/OAuth tokens;
- tenant isolation;
- audit logs;
- role-based access;
- secrets management;
- deletion workflows;
- retention enforcement;
- source-specific permissions.

Commercialization shall require stronger formal controls.

---

# 74. Privacy Requirements

First-party calculator telemetry should avoid unnecessary collection of sensitive financial or personal information.

Prefer:

```text
home_price_bucket
rate_bucket
down_payment_bucket
state
loan_term
funding_fee_status
```

rather than retaining unnecessary exact financial profiles when aggregated values satisfy analytical requirements.

Personally identifiable information should be separated from analytical telemetry whenever practical.

---

# 75. Data Governance

Every source must have:

- owner;
- provenance;
- ingestion method;
- rights policy;
- freshness expectation;
- retention policy;
- quality controls;
- downstream-use restrictions.

No integration enters production merely because its API is technically accessible.

---

# 76. Major Risks

## Risk 1 — Recommendation commoditization

Generic AI recommendations become ubiquitous.

**Mitigation:** build intervention/outcome learning.

---

## Risk 2 — Third-party licensing

Some providers may prohibit intended processing.

**Mitigation:** provider abstraction, BYOD, licensed integrations, rights engine, alternative sources.

---

## Risk 3 — Attribution

Search and revenue changes have multiple causes.

**Mitigation:** experiments, controls, market context and explicit uncertainty.

---

## Risk 4 — Insufficient intervention volume

Learning may take years.

**Mitigation:** VAHomeMath dogfood + design partners + eventual multi-tenant deployment.

---

## Risk 5 — AI hallucination

**Mitigation:** controlled functions and deterministic evidence.

---

## Risk 6 — Research methodology errors

Public research creates reputational exposure.

**Mitigation:** versioned methodology, reproducible calculations, authoritative sources and human review.

---

## Risk 7 — Low-quality programmatic content

Thousands of geographic pages could become thin or repetitive.

**Mitigation:** publish only where sufficient unique data and analytical value exist.

---

## Risk 8 — Link-building incentives corrupt research

Research could devolve into clickbait.

**Mitigation:** methodological standards and separate Newsworthiness from evidentiary confidence.

---

# 77. Non-Goals

GIS shall not initially:

- recreate SEMrush;
- recreate Ahrefs;
- build a global backlink index;
- crawl the entire web;
- replace GA4;
- replace GSC;
- become a CRM;
- become a journalist database;
- become an email marketing platform;
- automatically publish AI content;
- automatically modify production;
- train a foundation model;
- deploy Kubernetes;
- build a massive data lake;
- optimize primarily for vanity SEO metrics.

---

# 78. Strategic Product Decisions

### Decision 1

**GIS is multi-tenant capable from inception.**

### Decision 2

**VAHomeMath remains Tenant 001 and primary dogfood environment.**

### Decision 3

**GIS owns intelligence, not commodity datasets.**

### Decision 4

**Third-party providers are replaceable adapters.**

### Decision 5

**Data rights are part of the architecture.**

### Decision 6

**AI does not establish numerical truth.**

### Decision 7

**Every recommendation should eventually produce a measurable outcome.**

### Decision 8

**Authority acquisition is a growth intervention, not a standalone SEO activity.**

### Decision 9

**VAHomeMath should create proprietary research rather than manufacture backlinks.**

### Decision 10

**Research findings should be systematically evaluated for media value.**

### Decision 11

**VAHomeMath should seek to become a reference source for veteran housing and VA mortgage statistics.**

### Decision 12

**The long-term GIS moat is intervention intelligence.**

---

# 79. The VAHomeMath Strategic Flywheel

The expanded product creates a particularly attractive flywheel:

\[
Calculators
\rightarrow
Users
\rightarrow
FirstPartyBehavior
\]

combined with:

\[
PublicData
\rightarrow
ProprietaryResearch
\]

produces:

\[
BetterInsights
\rightarrow
ResearchAssets
\rightarrow
MediaCoverage
\rightarrow
Backlinks
\rightarrow
Authority
\]

which produces:

\[
HigherRankings
\rightarrow
MoreTraffic
\rightarrow
MoreUsers
\rightarrow
MoreBehavioralEvidence
\]

while GIS simultaneously records:

\[
Recommendation
\rightarrow
Intervention
\rightarrow
Outcome
\]

creating:

\[
BetterRecommendations
\]

The complete loop becomes:

\[
\boxed{
Data
\rightarrow
Insight
\rightarrow
Action
\rightarrow
Authority
\rightarrow
Traffic
\rightarrow
Conversion
\rightarrow
Revenue
\rightarrow
Learning
\rightarrow
BetterAction
}
\]

---

# 80. Long-Term Product Vision

GIS should ultimately know that:

> Pages of type X, with search intent Y, ranking position Z, authority level A, competitive environment B and conversion characteristics C historically respond best to Intervention Q.

Or:

> Research assets with characteristics X, Y and Z historically earn citations from these types of organizations.

Or:

> A competitor event of type X followed by market signal Y historically predicts a meaningful search-market shift.

The mature system therefore moves from:

\[
\text{What happened?}
\]

to:

\[
\text{Why did it happen?}
\]

to:

\[
\text{What should we do?}
\]

and ultimately:

\[
\boxed{\text{What action has the highest probability of creating economic value?}}
\]

That is the long-term definition of GIS.

---

# 81. Immediate Recommended Build Sequence

Based on everything we've developed, I would now implement in this order:

1. **Core GIS data platform** — PostgreSQL, tenant/site/source/provenance architecture.
2. **GSC + GA4 + first-party telemetry** — establish the basic search-to-revenue observation layer.
3. **Git/deployment integration** — establish change history.
4. **dbt analytical marts** — establish trustworthy derived evidence.
5. **Detection + Opportunity Engine** — make the system discover things.
6. **Growth Queue + AI Analyst** — make GIS useful operationally.
7. **Intervention/outcome tracking** — start accumulating the most strategically valuable dataset immediately.
8. **VA Research Dataset v1** — ingest VA + Census + housing/rate data.
9. **VA Metrics Engine** — buying power, affordability, gap and penetration.
10. **VA Loan Statistics/Research pages** — establish the first linkable assets.
11. **Research Finding + Newsworthiness Engine** — systematically discover stories in the dataset.
12. **Authority Intelligence** — identify what reputable sites cite in this market and why.
13. **Digital PR measurement** — close the research-to-backlink-to-outcome loop.
14. **External competitive/search providers** — add SEMrush/Ahrefs/DataForSEO/BuiltWith or alternatives only as rights and economics justify them.
15. **Cross-intervention learning** — begin estimating what works.
16. **External design partners** — prove GIS works outside VAHomeMath.
17. **Commercial GIS architecture/UI** — only after evidence supports productization.

The most important change from PRD v2.0 is therefore **not merely adding more data sources or features**. GIS v3.0 now has **three interconnected intelligence systems**:

\[
\boxed{
\text{Growth Intelligence}
}
\]

What should VAHomeMath change?

\[
\boxed{
\text{Research \& Authority Intelligence}
}
\]

What can VAHomeMath discover and publish that others will cite?

\[
\boxed{
\text{Intervention Intelligence}
}
\]

Which actions actually work, under which conditions?

If those three loops work together, VAHomeMath becomes much more than the first website using GIS. It becomes the **experimental environment that teaches GIS how to turn heterogeneous evidence into measurable growth**—which is the capability that could ultimately justify GIS as a standalone Growth Decision Intelligence product.
