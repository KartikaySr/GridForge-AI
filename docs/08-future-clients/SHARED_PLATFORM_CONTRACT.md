# Future Web & Mobile Contract

Shared: domain vocabulary/IDs, API/event schemas, validation concepts, auth/permissions, design tokens,
money/unit/time conventions and audit correlation.

Desktop owns UX/capability for OT connectivity, local continuity, edge health, simulator, device commissioning/
diagnostics and dispatch adapter.
Web later owns enterprise portfolio, multi-site analytics, central reporting/admin/model/financial governance;
it consumes cloud APIs and must not require the desktop UI process to be open.
Mobile later owns field reports/photos/notes, alerts, concise facility/asset state and explicitly permitted approvals;
it never receives unrestricted OT/database administration.

Share contracts and pure utilities, not Tauri-specific or page-specific implementation.

See [Corporate operating model](CORPORATE_OPERATING_MODEL.md) for the daily workflow, ownership boundaries, shared contracts and implementation order. Current cloud sync is edge-to-cloud only. Remote actions and unattended edge service hosting are prerequisites to implement, not existing capabilities.
