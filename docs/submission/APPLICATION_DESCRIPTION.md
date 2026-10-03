# Application description

Project name: GridForge AI

Event: Yuva Yodha Energy Tech Hackathon 2026 by Schneider Electric

Challenge 4: Smart Manufacturing — Industrial Energy & Process Efficiency

## Paste-ready project description

GridForge AI is a proposed industrial energy-intelligence solution, supported by a working software simulation, designed to help Indian SME manufacturers understand electricity use and evaluate operational changes without compromising production. Its proposed first deployment targets a small foundry’s auxiliary loads, such as compressed-air systems, while excluding melting and other critical processes from adjustment.

The existing desktop simulation connects validated synthetic telemetry to demand forecasting, constrained recommendations, explicit operator approval, simulated dispatch and measured financial verification. It runs locally using React and Tauri, a Rust supervisor, Python/FastAPI services and SQLite. Durable event synchronization with PostgreSQL supports recovery after cloud disconnection. Invalid or stale inputs produce an explicit UNKNOWN risk state rather than an unsupported recommendation. Every decision retains its input evidence, constraint results, approval and audit history.

The current forecast uses a rolling-mean baseline, and the advisory interface retrieves cited evidence. Neither a trained predictive-maintenance model nor an autonomous equipment-control system is claimed. The implemented simulation passed 216 local tests and demonstrated complete reconciliation of 4,041 domain events. These results establish software behavior, not factory energy savings.

For an Indian SME pilot, we propose read-only integration with suitable meters and production records through CSV or ERP interfaces. Plant staff would review auxiliary-load opportunities and execute approved changes under existing operating procedures. Local processing addresses unreliable connectivity, while staged metering and reuse of suitable equipment reduce installation complexity.

An explicitly illustrative scenario assumes 100,000 kWh monthly electricity consumption, 100 tonnes of good output and 20,000 kWh of auxiliary consumption. A 10% reduction in auxiliary electricity would save 2,000 kWh and reduce electricity-specific energy consumption from 1,000 to 980 kWh per good tonne, a 2% improvement. The scenario holds product mix, working hours, throughput and reject rate constant. These assumptions require field validation through matched baseline and intervention periods, with no savings claim if quality, output or measurement confidence deteriorates.

The proposed installation budget is INR 1.2 lakh. At an assumed marginal electricity rate of INR 8/kWh, the base scenario yields INR 16,000 monthly gross value and INR 12,000 after proposed software/support and maintenance costs, giving a ten-month simple payback. These are planning estimates, not quotations or guaranteed returns.

During the hackathon, we propose an SME-focused SEC dashboard and production-record import. A subsequent pilot would seek a foundry, energy auditor and electrical integrator to validate production safeguards and economics. Successful pilots would support cluster-based rollout, followed by enterprise web visibility and mobile field workflows. GridForge’s intended contribution is an inspectable, locally resilient decision process linking energy opportunities to production evidence and accountable human action.
