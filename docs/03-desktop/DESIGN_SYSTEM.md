# Design System

Industrial mission-control: calm, high-density, legible. Avoid gratuitous neon/glass/animation.
Semantic tokens: canvas/surface/text/border and status info/success/warning/critical/offline; chart
actual/forecast/threshold/tariff. Dark/light. Status never color-only.
Use tabular numerals for telemetry/finance, 4/8px spacing, target >=1280x800 and optimize for larger control-room screens.
Core components: AppShell, NavGroup, CommandPalette, FacilitySelector, ConnectionBadge, MetricCard, StatusBadge,
QualityBadge, DataTable, FilterBar, TimeRangePicker, TimeSeriesChart, TariffBand, ForecastBand, EventMarker,
ConstraintMatrix, DecisionExplanation, DispatchTimeline, AuditTimeline, EvidenceDrawer, OfflineBanner, StaleDataBadge.
Charts always show units/timezone and preserve raw data for calculations; visual downsampling cannot change finance.
