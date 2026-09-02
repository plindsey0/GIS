export type DocLink = {label: string; href: string};
export type DocSection = {
  id: string;
  title: string;
  paragraphs?: string[];
  bullets?: string[];
  steps?: string[];
  links?: DocLink[];
  callout?: {title: string; text: string};
  diagram?: string[];
  terms?: {term: string; definition: string}[];
};
export type DocPage = {slug: string; title: string; summary: string; group: string; sections: DocSection[]};

export const docs: DocPage[] = [
  {
    slug: "overview", title: "What is GIS?", group: "Start here",
    summary: "The purpose, value, and boundaries of the Growth Intelligence System.",
    sections: [
      {id:"definition", title:"An integrated intelligence system", paragraphs:["GIS is a governed growth-intelligence system. It combines first-party, licensed, public, and derived information to understand a digital market, observe change, assemble trustworthy evidence, identify conditions worth attention, and support human decisions.", "GIS is not merely an SEO dashboard, crawler, analytics screen, AI recommender, or collection of APIs. Those can be inputs or capabilities. GIS connects observation, market context, evidence, governance, decisions, action, and learning into one traceable system."], callout:{title:"The short version", text:"GIS helps an operator decide what deserves attention, why it deserves attention, and what evidence supports that judgment—without taking control away from people."}},
      {id:"value", title:"What value GIS provides", terms:[
        {term:"Unified observation",definition:"Multiple sources enter a common, governed analytical model instead of remaining isolated reports."},
        {term:"Market awareness",definition:"Metrics are interpreted inside a defined market of queries, domains, URLs, participants, and observations."},
        {term:"Evidence-based intelligence",definition:"Signals and opportunities depend on explicit evidence packages, quality checks, conflicts, and gaps."},
        {term:"Explainability",definition:"Users can trace intelligence to observations, sources, lineage, rights policies, and collection runs."},
        {term:"Governance",definition:"Rights, cost, provenance, and human approval boundaries are visible and machine-readable."},
        {term:"Continuous collection",definition:"Important targets can be observed repeatedly so GIS can distinguish a moment from a trend."},
        {term:"Decision support",definition:"GIS surfaces conditions that deserve review; it does not automatically take action."},
        {term:"Learning",definition:"Interventions, experiments, and outcomes can become new evidence as the system matures."}
      ]},
      {id:"boundaries",title:"What GIS does not do",bullets:["It does not treat every metric movement as an opportunity.","It does not treat unknown rights as permission.","It does not guarantee ROI, causality, or future performance.","It does not turn recommendations into external changes without separate human decisions.","It does not hide sparse data or missing operational history behind a confident score."],links:[{label:"Governance and trust",href:"/docs/governance"},{label:"Current limitations",href:"/docs/limitations"}]}
    ]
  },
  {
    slug:"getting-started",title:"Getting started",group:"Start here",summary:"A practical first workflow for a GIS operator.",sections:[
      {id:"workflow",title:"A sensible review sequence",steps:["Open Overview and read the decision workflow and current state.","Check System for disabled, stale, failing, or history-limited pipelines.","Review Market to understand the defined environment and current coverage.","Review Evidence for sufficiency, freshness, conflicts, and explicit gaps.","Review Collection to see targets, priorities, schedules, rights, cost, and blockers.","Review Opportunities. A zero result can be correct.","For any candidate, inspect its evidence and detector-condition diagnostics.","Review Recommendations when available; evaluate the evidence and governance context.","Accept a recommendation only when appropriate. Acceptance creates a draft, not autonomous execution.","Approve an intervention separately when its action and measurement plan are ready.","Define an experiment when controlled measurement is appropriate.","Review outcomes over time, preserving the difference between an observed result and a causal claim."]},
      {id:"empty-states",title:"How to read empty states",paragraphs:["An empty section can mean no object currently qualifies, a source is not configured, collection is blocked, evidence is insufficient, or the feature has no history yet. Empty never silently means zero. Read the nearby explanation and follow links upstream to Evidence, Collection, or System."],callout:{title:"Start with trust",text:"Before interpreting an intelligence result, confirm that its source, freshness, rights, evidence quality, and operational pipeline are suitable for the decision."}},
      {id:"shortcuts",title:"Useful live views",links:[{label:"Open Overview",href:"/"},{label:"Inspect System",href:"/system"},{label:"Review Evidence",href:"/evidence"},{label:"Review Collection",href:"/collection"},{label:"Review Opportunities",href:"/opportunities"}]}
    ]
  },
  {
    slug:"how-gis-works",title:"How GIS works",group:"Start here",summary:"How governed observations become intelligence, decisions, and learning.",sections:[
      {id:"flow",title:"Observe → Understand → Decide → Act → Learn",paragraphs:["This conceptual path is the operator-friendly view of GIS. The live System data-flow view uses registered sources, pipeline dependencies, data assets, and lineage for the operational version."],diagram:["OBSERVE  Sources → Collectors → Observations","UNDERSTAND  Observations → Signals → Market intelligence → Evidence packages","DECIDE  Evidence → Opportunity evaluation → Opportunities → Recommendations","ACT  Recommendations → Draft interventions → Human approval → Experiments / execution","LEARN  Outcomes → New evidence → Updated intelligence"],links:[{label:"Open the live data-flow map",href:"/system/data-flow"}]},
      {id:"observations-to-evidence",title:"From facts to supported claims",paragraphs:["Observations preserve source-derived facts. Deterministic services can derive signals and market context from them. Evidence packages then collect the relevant items, test compatibility and rights, record conflicts and gaps, and expose whether downstream evaluation has enough trustworthy support."],links:[{label:"Explore current evidence",href:"/evidence"}]},
      {id:"human-loop",title:"The human decision loop",paragraphs:["A qualifying opportunity is an evidence-supported condition, not an instruction. A recommendation is a governed suggestion. Accepting one may create a draft intervention. Approval is a separate human decision, and approval does not necessarily trigger external execution. Experiments and outcomes preserve measurement and learning without overstating causality."]}
    ]
  },
  {
    slug:"core-concepts",title:"Core concepts",group:"Understand GIS",summary:"The objects and distinctions that make GIS understandable and trustworthy.",sections:[
      {id:"market",title:"Market",paragraphs:["A GIS market defines the observable environment in which a site competes or serves demand. Its definition connects participants, queries, URLs, domains, geography, language, device, method, and time-bounded observations. Defining the market makes coverage, visibility, demand, change, and collection priorities interpretable."],links:[{label:"Explore Markets",href:"/markets"}]},
      {id:"collection-target",title:"Collection target",paragraphs:["A collection target is something GIS may observe: a QUERY, DOMAIN, or URL. CANDIDATE means discovered and evaluated but not promoted into an applied plan. ACTIVE, PAUSED, DORMANT, REJECTED, and RETIRED represent later lifecycle decisions. A target can have a computed priority but remain effectively paused because of rights, cost, capability, or another blocker."],links:[{label:"Explore Collection",href:"/collection"}]},
      {id:"observation",title:"Observation",paragraphs:["An observation is a source-derived fact stored with time, provenance, rights, and ingestion context. An observation is not itself a conclusion. Historical observations remain append-oriented so change can be evaluated over time."]},
      {id:"signal",title:"Signal",paragraphs:["A signal is a deterministic analytical pattern or change derived from observations—for example demand velocity or competitive change. A signal describes evidence in a repeatable way; it does not automatically create an opportunity."]},
      {id:"evidence-package",title:"Evidence package",paragraphs:["An evidence package assembles the items needed to support a defined claim or detector. It records completeness, source independence, method and scope compatibility, freshness, rights usability, conflicts, gaps, and provenance. Its sufficiency can gate downstream intelligence."],links:[{label:"Explore Evidence",href:"/evidence"}]},
      {id:"evidence-gap",title:"Evidence gap",paragraphs:["An evidence gap records something GIS knows it does not know or cannot yet support. Gaps prevent silence from being mistaken for evidence and can inform collection planning."]},
      {id:"opportunity",title:"Opportunity",paragraphs:["An opportunity is an evidence-supported condition that warrants operator attention under a published detector. It is not a guaranteed recommendation, probability, ROI estimate, or automatic action. Zero qualifying opportunities can be a valid result."],links:[{label:"Review Opportunities",href:"/opportunities"}]},
      {id:"recommendation",title:"Recommendation",paragraphs:["A recommendation is a governed suggestion for human consideration. It should retain its evidence and generation context. It does not execute itself, and external AI is not implied merely because the data model supports recommendations."],links:[{label:"Review Recommendations",href:"/recommendations"}]},
      {id:"intervention",title:"Intervention",paragraphs:["An intervention is a proposed or approved action. Recommendation acceptance may create a DRAFT intervention. Approval is separate from drafting, and execution remains bounded by the configured workflow."],links:[{label:"Review Interventions",href:"/interventions"}]},
      {id:"experiment",title:"Experiment",paragraphs:["An experiment defines controlled measurement of an intervention: what changes, what is measured, over what period, and against which comparison when available."],links:[{label:"Review Experiments",href:"/experiments"}]},
      {id:"outcome",title:"Outcome",paragraphs:["An outcome is an observed result following activity. It may contribute new evidence. Temporal sequence alone is not a causal claim; experiment design and measurement quality determine what can responsibly be concluded."],links:[{label:"Review Outcomes",href:"/outcomes"}]},
      {id:"operations",title:"Source, collector, pipeline, schedule, and obligation",terms:[{term:"Data source",definition:"The first-party or external origin of information."},{term:"Collector",definition:"Software that retrieves information from a source under configured rights, credentials, cost, and scope."},{term:"Pipeline",definition:"A registered workflow that retrieves or transforms information."},{term:"Schedule",definition:"The preferred execution cadence and time for a pipeline."},{term:"Data obligation",definition:"A durable requirement to satisfy a defined reporting window. It remains open across a missed clock time, retry, or provider delay until satisfied, blocked, failed, or expired."}],links:[{label:"Live source catalog",href:"/system/sources"},{label:"Live pipeline catalog",href:"/system/pipelines"}]},
      {id:"trust-concepts",title:"Provenance and rights",terms:[{term:"Provenance",definition:"The ability to trace intelligence through evidence and derived assets to upstream observations, source records, methods, and runs."},{term:"Rights",definition:"The permitted uses of data, tracked separately from whether the data is technically accessible. Unknown is not permission."}],links:[{label:"Governance and trust",href:"/docs/governance"}]}
    ]
  },
  {
    slug:"workbench-guide",title:"Using the Workbench",group:"Operate GIS",summary:"What each primary area answers and how it connects to the rest of GIS.",sections:[
      {id:"overview",title:"Overview — What should I know right now?",paragraphs:["Look for the decision workflow, top metrics, evidence health, market state, and collection health. Use it to choose the next drill-down, not as a substitute for the evidence behind a number."],links:[{label:"Open Overview",href:"/"}]},
      {id:"opportunities",title:"Opportunities — Where might the site improve?",paragraphs:["Look for qualified conditions, near-misses, and exact detector failures. Inspect evidence upstream. Zero opportunities can correctly mean that no package meets every published condition."],links:[{label:"Open Opportunities",href:"/opportunities"}]},
      {id:"recommendations",title:"Recommendations — What should I consider doing?",paragraphs:["Review the suggestion, supporting evidence, constraints, and status. A recommendation remains inside a human-review boundary and does not execute itself."],links:[{label:"Open Recommendations",href:"/recommendations"}]},
      {id:"interventions",title:"Interventions — What have I decided to do?",paragraphs:["Distinguish DRAFT from approved work. Drafting, approval, and execution are separate boundaries. Use interventions to preserve the planned action and measurement context."],links:[{label:"Open Interventions",href:"/interventions"}]},
      {id:"evidence",title:"Evidence — What does GIS know, and how reliable is it?",paragraphs:["Look for package sufficiency, freshness, sources, quality dimensions, conflicts, and gaps. Drill down to provenance and detector diagnostics. Evidence is upstream of trustworthy opportunities."],links:[{label:"Open Evidence",href:"/evidence"}]},
      {id:"market",title:"Market — What environment am I competing in?",paragraphs:["Review the market definition, participants, observations, metrics, demand, visibility, and coverage. A market describes an observable digital environment; it is not automatically an economic market-size estimate."],links:[{label:"Open Market",href:"/markets"}]},
      {id:"collection",title:"Collection — What are we observing, what is missing, and why?",paragraphs:["Review QUERY, DOMAIN, and URL targets, priority, cadence, evidence, collector plans, and blockers. Follow gaps upstream and schedules downstream. Candidate does not mean actively collected."],links:[{label:"Open Collection",href:"/collection"}]},
      {id:"experiments",title:"Experiments — What are we deliberately testing?",paragraphs:["Review the intervention, hypothesis, measurement contract, period, and comparison. Experiments connect action to responsible learning."],links:[{label:"Open Experiments",href:"/experiments"}]},
      {id:"outcomes",title:"Outcomes — What happened after we acted?",paragraphs:["Review observed results and measurement quality. Keep observed change distinct from a causal conclusion, and follow the result back to its experiment and intervention."],links:[{label:"Open Outcomes",href:"/outcomes"}]},
      {id:"system",title:"System — Can GIS currently produce trustworthy intelligence?",paragraphs:["Inspect source health separately from automation health. Source health explains ingestion freshness and provider reporting lag; automation health explains schedules, executor liveness, obligations, retries, and orchestration history. An enabled schedule is not healthy when its scheduler or worker is offline."],links:[{label:"Open System",href:"/system"}]}
    ]
  },
  {
    slug:"example",title:"Example intelligence walkthrough",group:"Operate GIS",summary:"A hypothetical query journey through GIS, from discovery to learning.",sections:[
      {id:"va-loan-calculator",title:"Hypothetical: “va loan calculator”",callout:{title:"Illustrative only",text:"This walkthrough explains the possible product flow. It does not claim these objects or results currently exist in production."},diagram:["Query discovered","↓ Collection target","↓ SERP, GSC, or governed provider observations","↓ Demand observations","↓ Deterministic demand signal","↓ Evidence package","↓ Opportunity evaluation","↓ Opportunity, only if every detector condition qualifies","↓ Governed recommendation","↓ Draft intervention","↓ Separate human approval","↓ Experiment or bounded execution","↓ Observed outcome → new evidence"]},
      {id:"interpretation",title:"How to interpret the journey",paragraphs:["Discovery creates something worth considering for observation, not an opportunity. Observations preserve facts. Signals summarize repeatable patterns. Evidence tests whether the relevant support is sufficient and usable. Detectors apply explicit conditions. Recommendations and interventions retain human control. Experiments and outcomes close the learning loop without turning correlation into certainty."],links:[{label:"See how GIS works",href:"/docs/how-gis-works"},{label:"Review core concepts",href:"/docs/core-concepts"}]}
    ]
  },
  {
    slug:"governance",title:"Governance and trust",group:"Trust GIS",summary:"The boundaries that keep intelligence traceable, permitted, and human-controlled.",sections:[
      {id:"rights",title:"Rights are not the same as access",paragraphs:["Public availability or technical accessibility does not automatically permit every use. GIS records reviewed policies and permitted uses such as deterministic analysis, storage, display, aggregation, AI inference, and model training. UNKNOWN is never silently interpreted as ALLOWED."],links:[{label:"Inspect live source rights",href:"/system/sources"}]},
      {id:"provenance",title:"Provenance",paragraphs:["Important outputs should be traceable through evidence items and data lineage to observations, source records, methods, and runs. Provenance supports explanation, review, correction, and responsible reuse."],links:[{label:"Open live data flow",href:"/system/data-flow"}]},
      {id:"quality",title:"Evidence quality",paragraphs:["Incomplete, stale, incompatible, conflicted, restricted, or insufficiently independent evidence can limit or block downstream intelligence. A gap is preferable to an unsupported conclusion."]},
      {id:"cost",title:"Cost and operational constraints",paragraphs:["Paid collection can be disabled, paused, budget-constrained, or blocked when cost is unknown. A technically available collector is not automatically authorized to run."],links:[{label:"Inspect pipelines and costs",href:"/system/pipelines"}]},
      {id:"human-control",title:"Human control",paragraphs:["Recommendations do not execute themselves. Acceptance may create a DRAFT intervention. Intervention approval is a separate decision, and approval does not necessarily cause external execution. These boundaries preserve operator accountability."]},
      {id:"ai",title:"AI boundaries",paragraphs:["Where AI capabilities are introduced, they must operate inside the same evidence, rights, provenance, cost, and review boundaries. The presence of recommendation models or AI-ready schema does not imply that an external LLM is currently active."]}
    ]
  },
  {
    slug:"sources-and-pipelines",title:"Sources and pipelines",group:"Trust GIS",summary:"Conceptual source and workflow families, connected to live operational details.",sections:[
      {id:"catalog-boundary",title:"Documentation explains purpose; System shows current state",paragraphs:["This guide intentionally does not copy the operational catalog. Documentation explains what a source or pipeline family contributes. System shows its current connection, schedule, last run, records, reliability, cost, rights, and dependencies."],links:[{label:"Live data-source catalog",href:"/system/sources"},{label:"Live pipeline catalog",href:"/system/pipelines"}]},
      {id:"source-families",title:"Source families",terms:[{term:"First-party performance",definition:"Sources such as Google Search Console and GA4 describe owned visibility and behavior."},{term:"First-party product telemetry",definition:"Customer-side events and calculator runs describe product use under first-party governance."},{term:"Public and government data",definition:"Reviewed public datasets can provide market or contextual observations within their permitted uses."},{term:"Licensed search and authority data",definition:"Commercial providers can contribute SERP, demand, backlink, or technology information when rights, cost, and configuration permit."},{term:"Direct collection",definition:"Governed HTTP, browser, or crawler capabilities can observe public web properties without bypassing rights or operational controls."}]},
      {id:"pipeline-families",title:"Pipeline families",terms:[{term:"Collectors",definition:"Retrieve source records and preserve ingestion provenance."},{term:"Normalization and analytics",definition:"Transform typed observations into comparable staging models and analytical marts."},{term:"Market and demand intelligence",definition:"Build market context and deterministic signals from governed observations."},{term:"Evidence and detection",definition:"Assemble quality-controlled evidence and apply published opportunity conditions."},{term:"Decision and learning",definition:"Support recommendations, interventions, experiments, outcomes, and eventual evidence feedback."}],links:[{label:"Inspect live dependencies",href:"/system/data-flow"}]}
    ]
  },
  {
    slug:"architecture",title:"Architecture overview",group:"Reference",summary:"A conceptual technical map for operators who support GIS.",sections:[
      {id:"application",title:"Application layers",diagram:["Workbench → GIS API → domain services → PostgreSQL","PostgreSQL → dbt staging / marts → analytical views","Metabase → analytical marts","Workbench → operational intelligence, review, governance, and drill-down"]},
      {id:"data",title:"Data path",diagram:["External and first-party sources","↓ governed collectors and connections","↓ append-oriented raw observations","↓ normalized and derived intelligence","↓ evidence packages and gaps","↓ opportunity evaluation and human decisions"]},
      {id:"roles",title:"What each surface is for",terms:[{term:"Workbench",definition:"Operational intelligence, explanation, governance, review, and navigation across live objects."},{term:"GIS API",definition:"Tenant- and site-scoped application access to domain services and governed records."},{term:"PostgreSQL",definition:"Typed durable storage for core entities, observations, provenance, rights, and operations."},{term:"dbt",definition:"Deterministic analytical transformations, tests, and marts."},{term:"Metabase",definition:"Analytical exploration over governed marts; it does not replace the operational Workbench."}],callout:{title:"Security boundary",text:"Architecture documentation describes responsibilities and flow. It never exposes credentials, secret references, or unsafe operational instructions."}}
    ]
  },
  {
    slug:"limitations",title:"Current limitations",group:"Reference",summary:"What the product cannot claim and what the current environment may not yet support.",sections:[
      {id:"product",title:"Product limitations",bullets:["GIS supports decisions; it does not guarantee future performance or ROI.","Observed outcomes do not establish causality without an appropriate design.","Detector qualification is rule-based evidence evaluation, not a probability estimate.","A recommendation is not autonomous execution.","Technical accessibility does not establish permitted use.","Operational reliability needs enough scheduled history before a meaningful rate can be reported."]},
      {id:"environment",title:"Current environment and data limitations",paragraphs:["The live callout on this page derives counts from current API state. For detailed and changing limitations, inspect System, Evidence, Market, Collection, and Opportunities rather than relying on maintained prose."],bullets:["Longitudinal SERP or field-experience coverage may be sparse.","Some commercial providers can remain intentionally disabled because of rights, cost, or configuration.","CrUX field data or provider quota telemetry may be unavailable.","Evidence packages can remain limited or have explicit gaps.","Pipelines can have insufficient history for reliability statistics.","There may be zero qualifying opportunities or no intervention/outcome history."],links:[{label:"Inspect live system health",href:"/system"},{label:"Inspect current evidence",href:"/evidence"},{label:"Inspect opportunity diagnostics",href:"/opportunities"}]},
      {id:"reading",title:"How to use a limitation",paragraphs:["Treat a limitation as decision context. Follow it upstream to the missing source, target, observation, evidence item, right, schedule, or run. Resolve it only through governed collection or configuration—not by assuming a value or weakening a detector."]}
    ]
  },
  {
    slug:"glossary",title:"Glossary",group:"Reference",summary:"Actual GIS terminology and lifecycle semantics.",sections:[
      {id:"terms",title:"A–Z",terms:[
        {term:"Active",definition:"Eligible for current use or collection under the applicable lifecycle; operational blockers can still affect execution."},
        {term:"Blocked",definition:"Prevented from proceeding because a required condition such as rights, cost, evidence, configuration, or capability is not satisfied."},
        {term:"Candidate",definition:"A collection target that was discovered and evaluated but not promoted into an applied collection plan."},
        {term:"Collector",definition:"Software that retrieves information from a source."},
        {term:"Connection",definition:"A tenant- or site-scoped configuration connecting GIS to a registered data source without storing plaintext secrets."},
        {term:"Data asset",definition:"A registered table, model, evidence layer, or other governed data product with lineage metadata."},
        {term:"Demand observation",definition:"A time-bounded observation describing measured or provider-reported demand while preserving its method semantics."},
        {term:"Demand signal",definition:"A deterministic pattern or change derived from demand observations."},
        {term:"Domain target",definition:"A hostname or domain selected for possible repeated observation."},
        {term:"Evidence gap",definition:"An explicit record of required evidence that is missing, insufficient, or unresolved."},
        {term:"Evidence item",definition:"A governed observation or derived record included in an evidence package for a defined role."},
        {term:"Evidence package",definition:"A quality- and rights-evaluated collection of evidence supporting a defined claim or detector input."},
        {term:"Experiment",definition:"A controlled measurement plan associated with an intervention."},
        {term:"Freshness",definition:"How current evidence or operational output is relative to its expected cadence or decision need."},
        {term:"Ingestion run",definition:"A record of external collection, including source connection, timing, counts, errors, and provenance."},
        {term:"Intervention",definition:"A proposed or approved action with lifecycle and measurement context."},
        {term:"Lineage",definition:"Registered upstream and downstream relationships among sources, pipelines, observations, and data assets."},
        {term:"Market",definition:"A versioned definition of the observable digital environment GIS is evaluating."},
        {term:"Market participant",definition:"A domain, URL, organization, or other entity observed within a defined market."},
        {term:"Observation",definition:"A source-derived, time-aware fact stored with provenance and rights context."},
        {term:"Opportunity",definition:"An evidence-supported condition that satisfies a published detector and warrants operator attention."},
        {term:"Outcome",definition:"An observed result associated with an intervention or experiment; not automatically a causal claim."},
        {term:"Permitted use",definition:"A specific allowed, prohibited, or unknown use under a rights policy."},
        {term:"Pipeline",definition:"A registered workflow that collects or transforms information."},
        {term:"Processing run",definition:"A recorded execution of local or derived processing, distinct from external ingestion."},
        {term:"Provenance",definition:"Traceability from intelligence back to evidence, observations, source records, methods, and runs."},
        {term:"Query target",definition:"A search query selected for possible repeated observation."},
        {term:"Recommendation",definition:"A governed suggestion for human consideration, not autonomous execution."},
        {term:"Rights policy",definition:"Machine-readable permitted-use and licensing context associated with a source or connection."},
        {term:"Schedule",definition:"A pipeline's preferred execution cadence and timezone; it creates durable obligations rather than guaranteeing a process ran at one instant."},
        {term:"Data obligation",definition:"A versioned requirement to satisfy one source or processing window, with an original due time, expiry, attempts, completion outcome, and provenance."},
        {term:"Recovered late",definition:"An obligation satisfied after its preferred due time through bounded catch-up or retry."},
        {term:"Provider data pending",definition:"The request succeeded technically, but the reporting period is not yet complete or finalized enough to satisfy the obligation."},
        {term:"Executor offline",definition:"A schedule is enabled but no current scheduler or worker lease proves that GIS can execute it."},
        {term:"Signal",definition:"A deterministic analytical pattern or change derived from observations."},
        {term:"Source",definition:"The first-party or external origin of information registered in GIS."},
        {term:"URL target",definition:"A specific web address selected for possible repeated observation."}
      ]}
    ]
  }
];

export const docsBySlug = new Map(docs.map((page) => [page.slug, page]));
export const docGroups = [...new Set(docs.map((page) => page.group))];
