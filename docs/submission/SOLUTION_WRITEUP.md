# GridForge AI: Smart Manufacturing solution proposal

Prepared for the Yuva Yodha Energy Tech Hackathon 2026 by Schneider Electric, Challenge 4: Smart Manufacturing — Industrial Energy & Process Efficiency, as an idea-stage submission. The existing simulation supports feasibility; the proposed industrial solution remains to be piloted. The submission includes a 12-slide editable PowerPoint, a 300–500-word application description and this supporting write-up. No physical hardware build or application submission is included.

## 1. Problem and target segment

Small manufacturers need to distinguish productive energy use from avoidable auxiliary demand. Bills show aggregate cost but cannot by themselves attribute consumption to an asset, operating state or good-output quantity. An attractive demand reduction can still be unacceptable if it disrupts throughput, raises rejects or relies on poor measurements.

The proposed first customer is a small foundry with accessible electrical panels, a responsible plant operator and a measurable auxiliary opportunity. The initial boundary is purchased electricity. Melting and other critical process adjustments are excluded. Compressed-air auxiliary consumption is a candidate for investigation, not an assumption that every compressor can be curtailed safely. Pressure, air quality, process demand and compressor operating rules must remain authoritative.

BEE operates SME energy-efficiency programmes, and the SAMEEEKSHA knowledge platform documents foundry compressed-air interventions. These support investigating this segment. They do not establish GridForge's effectiveness. The cited Rajkot case concerns equipment replacement, which our proposed monitoring budget does not include. The broad national percentages in the challenge brief are contextual inputs, not independently validated project evidence.

## 2. Mechanism and implementation status

The working prototype follows telemetry, validation, state, forecast, risk, constraints, optimization, proposal, authorization, simulated dispatch, acknowledgement, verification, savings and audit.

The local runtime ingests nominal 1 Hz synthetic asset measurements. It normalizes units, checks quality/freshness and mapping revisions, and persists history with event outboxes. Forecasting requires sufficient valid minute coverage and uses a five-minute rolling mean to project thirty minutes. A degraded input state suppresses a usable prediction and produces UNKNOWN risk. It does not fill missing consumption with zero.

The optimizer selects continuous bounded reductions from eligible simulated loads. It minimizes configured penalty-weighted allocation for the restricted problem. Criticality, flexibility, maintenance, telemetry freshness, mapping evidence and load bounds govern eligibility. Unsupported minimum-run/off conditions block eligibility. This is not a general production scheduler.

An operator separately approves an eligible proposal. The dispatch state machine revalidates conditions, records acknowledgement and tracks simulated execution. Financial verification compares complete measured simulation output with the declared pre-dispatch baseline and accounts for rebound. Cited local evidence retrieval supports explanation. No generative LLM, trained XGBoost/LightGBM predictor or predictive-maintenance model runs today.

### Proposed pilot extension

Read-only physical meter adapters and production-record ingestion must be implemented. The operator and auditor would investigate idle consumption, leakage and unnecessary auxiliary operation. Any maintenance or operating change remains a plant-managed activity under existing procedures. GridForge must not imply that a software load allocation alone repairs leaks or preserves product quality.

No direct equipment writes are proposed for the first pilot. Future physical actuation requires separately commissioned interlocks, point allowlists, bounds, failsafes and site authorization.

## 3. Architecture and Indian SME fit

The existing client uses React 19, TypeScript and Tauri 2. Rust supervises the local Python 3.12/FastAPI/asyncio modular monolith. React accesses fixed native operations and has no direct database or OT connection. SQLite WAL provides local persistence, while versioned outboxes synchronize to a FastAPI/PostgreSQL receiver. Optional pgvector supports knowledge retrieval.

The editable architecture diagram in slide 4 marks physical meter and ERP integration as proposed. Existing components appear in solid green. Proposed integrations appear with dashed amber borders. Cloud acknowledgements confirm committed events; they are not remote dispatch instructions.

SME deployment assumptions include local operation during connectivity loss, reuse of compatible meters or PCs, simple operator workflows, phased commissioning and a local installation/support partner. CSV production capture can precede ERP integration. Local-language labels and low-bandwidth reporting require operator research and implementation.

The current runtime stops when the desktop closes. Unattended hosting is a prerequisite for continuous site monitoring. Only macOS ARM64 has verified native packaging. A site's Windows/Linux environment needs separate packaging and validation. Hardware installation should occur during an approved outage or safe access window through a qualified partner. No hardware fabrication is required for this submission.

## 4. Supporting design artefacts

Slide 5 contains an editable dashboard wireframe. It is a design artefact, not an actual screenshot. Demand, quality, proposal reasons, approval and verification reflect existing interface concepts. Production output and SEC widgets are explicitly proposed.

Slide 6 contains an editable conceptual data model. Existing records connect telemetry, prediction/proposal, approval/command, verification/ledger and audit/sync evidence. Every record remains organization/facility scoped. The planned production record adds shift, SKU/product mix, good tonnes, rejects and operating hours, with versioning and reconciliation to the energy interval.

The write-up and slides preserve differences between acknowledgement and verification, and between estimates and measured synthetic attribution. Local audit hash chaining is tamper-evident within its threat model; it does not protect against a privileged owner rewriting the complete local database.

## 5. Prototype evidence

The recorded 3 October 2026 local acceptance contains 174 passing Python tests, 39 frontend tests and 3 native tests. The full scenario ingested 3,995 telemetry points, acknowledged 4,041 domain events, reached zero pending events and retained valid audit integrity. It exercised quality degradation, constrained proposals, explicit approval, simulated response, verification and real local PostgreSQL/HTTP reconciliation after an outage.

The recorded USD 1.84 net synthetic event value uses a declared USD 0.15/kWh simulation rate and complete 60-second execution/rebound windows. It is a software finance test, not an Indian tariff result. We do not extrapolate it into a monthly factory saving. It contains no production quality/throughput evidence.

Source code and portable acceptance evidence are public at [GridForge-AI](https://github.com/KartikaySr/GridForge-AI). The walkthrough explains `npm run demo:verify` and its temporary PostgreSQL prerequisites. The package is an ad-hoc signed desktop prototype, not a certified industrial release.

## 6. Quantified SEC scenario and assumptions

The following is a reproducible analytical scenario, not output from an industrial trial or from a production model in the application:

- Baseline purchased electricity: 100,000 kWh/month.
- Good output: 100 tonnes/month in both cases.
- Auxiliary electricity: 20,000 kWh/month, within the total above.
- Target auxiliary reduction: 10%, or 2,000 kWh/month.
- Intervention electricity: 98,000 kWh/month.
- Baseline electricity SEC: 100,000 / 100 = 1,000 kWh/good tonne.
- Intervention electricity SEC: 98,000 / 100 = 980 kWh/good tonne.
- Modeled improvement: (1,000 − 980) / 1,000 = 2%.

The scenario holds product mix, working hours, good output and reject rate constant. It assumes a 3% reject rate in both cases and no additional energy outside the stated measurement boundary. These are assumptions, not proof of quality or throughput preservation. Loss of output, shifted consumption or rebound can eliminate the modeled benefit.

The submission therefore provides a quantified target with a defined baseline and preserved production assumptions. It does **not** satisfy a demand for already field-measured SEC improvement. If the organizer requires that stronger evidence, a metered pilot remains necessary.

For an unchanged valid grid emissions factor, the modeled electricity-related emissions intensity would also fall 2%. We do not claim a percentage for total factory emissions or use an unverified numerical factor. Actual reporting must identify the reporting year, purchased-electricity boundary and appropriate CEA factor. Fuel combustion requires a separate inventory.

## 7. Field validation and safeguards

Collect four representative baseline weeks and four matched intervention weeks. Reconcile meter readings with bills and production records. Capture product mix, good tonnes, reject rate, operating hours, maintenance and abnormal shutdowns by shift. Meter selected auxiliaries separately to distinguish changed consumption from unrelated plant variation.

Before intervention, the auditor and plant manager should register the baseline normalization method, eligible loads, exclusions, uncertainty, minimum data coverage and operating limits. The proposed coverage target is at least 95% per assessed shift. Low coverage or suspect calibration produces no claim rather than zero-filled consumption. Use matched shifts or regression where operating variation requires it.

Accept the outcome only when electricity SEC improves beyond measurement uncertainty, matched good-output throughput does not fall, and rejection does not increase. Monitor site-approved pressure and process conditions. Existing plant protection and operator stop authority remain in force. Stop or reverse a change on pressure, production quality or process alarms. Account for execution and rebound over the complete affected boundary. Schedule shifting alone cannot count as energy savings.

The plan is proposed engineering methodology, not a claim of accredited M&V certification.

## 8. Deployment budget and economics

One-time planning budget:

- Meters and current transformers: INR 45,000.
- Gateway/local compute: INR 20,000.
- Wiring and installation: INR 20,000.
- Commissioning and mapping: INR 25,000.
- Training and contingency: INR 10,000.
- Total: INR 1,20,000.

These are explicit budget assumptions, not supplier quotations. Exclusions include GST, finance charges, major panel work, machinery replacement and exceptional travel. Site survey findings and reuse of suitable assets may change the amount.

The proposed business model combines partner-led installation with INR 3,000/month software and support. The financial scenario also allows INR 1,000/month for incremental maintenance, for a total recurring expense of INR 4,000/month. The assumed marginal electricity price is INR 8/kWh, not a cited DISCOM tariff. Demand-charge reductions, carbon credits and subsidies are excluded.

At 10% auxiliary improvement, 2,000 kWh/month saves INR 16,000 gross and INR 12,000 after recurring expense. Simple payback is INR 1,20,000 / INR 12,000 = 10 months. The same method yields 30 months at 5% auxiliary improvement and 6 months at 15%. Zero energy savings produces no positive payback and leaves recurring cost. Twelve identical base-case months imply INR 1,44,000 annual net value, but seasonality and production changes must be assessed before using that annual estimate commercially.

No guaranteed savings, signed customer, validated willingness-to-pay or vendor margin is claimed. Site-specific economics must use actual bills, quotes and operating costs.

## 9. Roadmap and scale-up

During the hackathon, build an SME-focused demonstration around the existing simulation: prototype production-record import, a production-normalized SEC view and a constrained auxiliary decision workflow. Label modeled production assumptions explicitly. These extensions are proposed deliverables, not features claimed complete today.

The next proposed 8–12 weeks cover recruiting a partner site and auditor, implementing read-only integration and production records, resolving unattended hosting and the site operating system, then collecting baseline/intervention evidence. The duration depends on site access and representative operating cycles.

After successful validation, repeat the method in a small foundry cluster with local integrators and energy auditors. Standardize meter mapping, operator training, outcome reporting and support costs. Expand only when energy results and customer economics repeat. Shared enterprise identity and cloud read APIs precede a web client, followed by mobile field inputs and alerts. Remote actions and physical OT remain separate safety work.

## 10. Team and request

Kartikay Srivastava is a B.Tech Computer Science and Engineering student specializing in AI & ML at JECRC University. GridForge is an AI-assisted student engineering project. The proposal seeks a foundry pilot site, an energy auditor and an electrical integration partner. It does not claim a secured partnership, institutional endorsement or additional team members.

## Sources and evidence

1. User-supplied challenge brief and application screenshot: Smart Manufacturing requirements, 300–500-word description and 8–12-slide presentation.
2. [BEE SME programme](https://www.beeindia.gov.in/small-medium-scale-enterprises-sme.php): context for SME efficiency interventions.
3. [SAMEEEKSHA Rajkot foundry compressed-air case](https://www.sameeeksha.org/pdf/compressed-air-system.pdf): independent evidence that this subsystem is relevant, not a benchmark for GridForge's effect.
4. [CEA CO2 database](https://cea.nic.in/cdm-co2-baseline-database/): source to select a suitable reporting-year factor during a real inventory. No numerical emissions factor is assumed here.
5. [Project acceptance summary](../evidence/phase-11-acceptance.json): actual recorded software acceptance evidence.
6. [Phase 11 report](../00-master/PHASE_11_COMPLETION_REPORT.md) and [demonstration guide](../06-engineering/PHASE_11_DEMONSTRATION.md).

## Submission checklist

- Solution mechanism, assumptions and SME fit: slides 2–3 and this write-up.
- Sensors, edge/cloud, equipment and ERP architecture: slide 4, with proposed elements labeled.
- UX and data-model artefacts: slides 5–6.
- Functional prototype evidence: slide 7 and public source.
- Quantified SEC scenario and production safeguards: slides 8–9; analytical target, not a measured factory result.
- Deployment, costs, payback and scale-up: slides 10–12.
- Team introduction: slides 1 and 12.
- Application description: separate paste-ready Markdown file.
