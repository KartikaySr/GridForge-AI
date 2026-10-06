import type { components } from './runtime.generated';
import type { components as cloudComponents } from './cloud.generated';
export type RuntimeHealth = components['schemas']['RuntimeHealth'];
export type RuntimeDiagnostics = components['schemas']['Diagnostics'];
export type RuntimeLog = components['schemas']['LogRecord'];
export type RuntimeApiError = components['schemas']['RuntimeErrorResponse'];

export type TelemetrySnapshot = components['schemas']['TelemetrySnapshot'];
export type StoredPoint = components['schemas']['StoredPoint'];
export type TelemetryEvent = components['schemas']['TelemetryEvent'];
export type HistoryPage = components['schemas']['HistoryPage'];

export type RegistrySnapshot = components['schemas']['RegistrySnapshot'];
export type RegistryRecord = components['schemas']['RegistryRecord'];
export type RegistryWrite = components['schemas']['RegistryWrite'];
export type RegistryEntity = RegistryRecord['entity'];
export type IntelligenceSnapshot =
  components['schemas']['IntelligenceSnapshot'];
export type OptimizationSnapshot =
  components['schemas']['OptimizationSnapshot'];
export type OptimizationRun = components['schemas']['OptimizationRun'];
export type OptimizationPolicy = components['schemas']['OptimizationPolicy'];
export type PolicyWrite = components['schemas']['PolicyWrite'];
export type RunRequest = components['schemas']['RunRequest'];
export type DispatchSnapshot = components['schemas']['DispatchSnapshot'];
export type DispatchCommand = components['schemas']['DispatchCommand'];
export type DispatchDetail = components['schemas']['DispatchDetail'];
export type DispatchEvent = components['schemas']['DispatchEvent'];
export type ApprovalRequest = components['schemas']['ApprovalRequest'];
export type DecisionRequest = components['schemas']['DecisionRequest'];
export type FinanceSnapshot = components['schemas']['FinanceSnapshot'];
export type TariffWrite = components['schemas']['TariffWrite'];
export type TariffVersion = components['schemas']['TariffVersion'];
export type VerificationRequest = components['schemas']['VerificationRequest'];
export type Verification = components['schemas']['Verification'];
export type SyncSnapshot = components['schemas']['SyncSnapshot'];
export type CloudSyncBatch = cloudComponents['schemas']['SyncBatch'];
export type CloudSyncAck = cloudComponents['schemas']['SyncAck'];
export type CloudSyncState = cloudComponents['schemas']['CloudSyncState'];

export type AskRequest = components['schemas']['AskRequest'];
export type CopilotAnswer = components['schemas']['CopilotAnswer'];
export type CopilotSnapshot = components['schemas']['CopilotSnapshot'];
export type DocumentWrite = components['schemas']['DocumentWrite'];
export type KnowledgeDocument = components['schemas']['KnowledgeDocument'];
export type Evidence = components['schemas']['Evidence'];
export type FeedbackWrite = components['schemas']['FeedbackWrite'];
export type FeedbackReceipt = components['schemas']['FeedbackReceipt'];
export type QueryRun = components['schemas']['QueryRun'];

export type IdentityStatus = components['schemas']['IdentityStatus'];
export type LocalUser = components['schemas']['LocalUser'];
export type UserWrite = components['schemas']['UserWrite'];
export type UserChange = components['schemas']['UserChange'];
export type AuditSnapshot = components['schemas']['AuditSnapshot'];
export type OperationsSnapshot = components['schemas']['OperationsSnapshot'];

export type DemoSnapshot = components['schemas']['DemoSnapshot'];
export type DemoStep = components['schemas']['DemoStep'];
export type ProductionWrite = components['schemas']['ProductionWrite-Input'];
export type ProductionReport = components['schemas']['ProductionReport'];
export type ReportComparisonRequest =
  components['schemas']['ReportComparisonRequest'];
export type ReportComparison = components['schemas']['ReportComparison'];
export type ReportingSnapshot = components['schemas']['ReportingSnapshot'];
export type Incident = components['schemas']['Incident'];
export type IncidentAction = components['schemas']['IncidentAction'];
export type IncidentSnapshot = components['schemas']['IncidentSnapshot'];
