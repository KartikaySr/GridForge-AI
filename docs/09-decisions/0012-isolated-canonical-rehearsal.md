# ADR 0012: isolated canonical demonstration and three-client handoff

Status: accepted for Phase 11 simulation scope.

The desktop exposes a guided rehearsal backed by DemoService, sharing the existing registry, simulator, forecast/risk, optimization, dispatch, finance, audit, AI and synchronization services. A separate ephemeral SQLite repository and explicit accelerated clock avoid contaminating the operating facility or requiring minutes of real-time waiting. Each step is ordered and successful request UUIDs replay without repeating effects. Approval is an explicit permission-checked action.

All samples pass through the simulator and Repository.ingest. Financial verification reads the retained execution/rebound observations. No post-hoc measurement replacement or direct fixture SQL is permitted in this scenario. AI returns cited local extractive evidence and has no operational authority. Cloud fault injection wraps a real transport and never fabricates acknowledgements; a real disposable PostgreSQL/HTTP receiver verifies the full acceptance run.

The sandbox is visibly ephemeral; restarting the runtime ends it. Main-facility persistence, transport credentials and permissions are unchanged. No schema migration is necessary. External demo receiver enrollment is separate from the operating edge. Unconfigured cloud stages remain incomplete.

Desktop, web and mobile are clients of shared contracts. The corporate operating model assigns local execution to edge, portfolio/governance to web, and field evidence/alerts to mobile. Enterprise identity/read projections, unattended edge hosting and a revalidated remote action protocol are prerequisites for the respective future capabilities. The current milestone does not authorize physical OT or automatically create future applications.
