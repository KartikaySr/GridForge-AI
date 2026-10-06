import type {
  Incident,
  IncidentAction,
  IncidentSnapshot,
} from '@gridforge/api-client';
import { invoke, isTauri } from '@tauri-apps/api/core';
import type {
  ProductionWrite,
  ProductionReport,
  ReportComparisonRequest,
  ReportComparison,
  ReportingSnapshot,
  IdentityStatus,
  LocalUser,
  UserWrite,
  UserChange,
  AuditSnapshot,
  OperationsSnapshot,
  DemoSnapshot,
  DemoStep,
  RuntimeDiagnostics,
  RuntimeHealth,
  TelemetrySnapshot,
  HistoryPage,
  RegistrySnapshot,
  RegistryRecord,
  RegistryWrite,
  IntelligenceSnapshot,
  OptimizationSnapshot,
  OptimizationRun,
  OptimizationPolicy,
  PolicyWrite,
  RunRequest,
  DispatchSnapshot,
  DispatchCommand,
  DispatchDetail,
  ApprovalRequest,
  DecisionRequest,
  FinanceSnapshot,
  TariffWrite,
  TariffVersion,
  VerificationRequest,
  Verification,
  SyncSnapshot,
  AskRequest,
  CopilotAnswer,
  CopilotSnapshot,
  DocumentWrite,
  KnowledgeDocument,
  FeedbackWrite,
  FeedbackReceipt,
  QueryRun,
} from '@gridforge/api-client';

// Native lifecycle DTOs are desktop-only. Domain/API contracts come from OpenAPI.
export type RuntimeState =
  | 'STARTING'
  | 'READY'
  | 'DEGRADED'
  | 'FAILED'
  | 'STOPPED'
  | 'STOPPING'
  | 'RESTARTING'
  | 'UNAVAILABLE';
export interface RuntimeSnapshot {
  state: RuntimeState;
  message: string;
  generation: number;
  pid: number | null;
  instance_id: string | null;
  last_checked_ms: number | null;
  health: RuntimeHealth | null;
  telemetry: TelemetrySnapshot | null;
  telemetry_checked_ms: number | null;
  busy: boolean;
  events: { timestamp_ms: number; event: string; generation: number }[];
}
export interface DiagnosticSnapshot {
  supervisor: RuntimeSnapshot;
  runtime: RuntimeDiagnostics | null;
}
export const unavailable: RuntimeSnapshot = {
  state: 'UNAVAILABLE',
  message: 'Open the native desktop to start the local runtime.',
  generation: 0,
  pid: null,
  instance_id: null,
  last_checked_ms: null,
  health: null,
  telemetry: null,
  telemetry_checked_ms: null,
  busy: false,
  events: [],
};
export const initialRuntime: RuntimeSnapshot = {
  ...unavailable,
  state: 'STARTING',
  message: 'Connecting to desktop supervisor…',
  busy: true,
};
export const isDesktop = () => typeof window !== 'undefined' && isTauri();
export const runtimeBridge = {
  incidents: (before: number | null = null) =>
    withTimeout(
      invoke<IncidentSnapshot>('security_request', {
        operation: before ? 'incident-history' : 'incidents',
        write: before ? { before } : null,
      }),
    ),
  incidentAction: (write: IncidentAction) =>
    withTimeout(
      invoke<Incident>('security_request', {
        operation: 'incident-action',
        write,
      }),
    ),
  reports: (before: number | null = null) =>
    withTimeout(
      invoke<ReportingSnapshot>('security_request', {
        operation: before ? 'report-history' : 'reports',
        write: before ? { before } : null,
      }),
    ),
  createReport: (write: ProductionWrite) =>
    withTimeout(
      invoke<ProductionReport>('security_request', {
        operation: 'report-create',
        write,
      }),
    ),
  compareReports: (write: ReportComparisonRequest) =>
    withTimeout(
      invoke<ReportComparison>('security_request', {
        operation: 'report-compare',
        write,
      }),
    ),
  demo: () =>
    withTimeout(
      invoke<DemoSnapshot>('security_request', {
        operation: 'demo',
        write: null,
      }),
    ),
  demoStep: (write: DemoStep) =>
    invoke<DemoSnapshot>('security_request', { operation: 'demo-step', write }),
  identity: () =>
    withTimeout(
      invoke<IdentityStatus>('security_request', {
        operation: 'identity',
        write: null,
      }),
    ),
  signIn: (setup: boolean, username: string, password: string) =>
    withTimeout(
      invoke<IdentityStatus>('security_request', {
        operation: setup ? 'bootstrap' : 'login',
        write: { username, password },
      }),
    ),
  signOut: () =>
    withTimeout(
      invoke<IdentityStatus>('security_request', {
        operation: 'logout',
        write: null,
      }),
    ),
  users: () =>
    withTimeout(
      invoke<LocalUser[]>('security_request', {
        operation: 'users',
        write: null,
      }),
    ),
  createUser: (write: UserWrite) =>
    withTimeout(
      invoke<LocalUser>('security_request', { operation: 'create', write }),
    ),
  changeUser: (write: UserChange) =>
    withTimeout(
      invoke<LocalUser>('security_request', { operation: 'change', write }),
    ),
  audit: () =>
    withTimeout(
      invoke<AuditSnapshot>('security_request', {
        operation: 'audit',
        write: null,
      }),
    ),
  metrics: () =>
    withTimeout(
      invoke<OperationsSnapshot>('security_request', {
        operation: 'metrics',
        write: null,
      }),
    ),
  bundle: () =>
    withTimeout(
      invoke<Record<string, unknown>>('security_request', {
        operation: 'bundle',
        write: null,
      }),
    ),
  ai: () =>
    withTimeout(
      invoke<CopilotSnapshot>('ai_request', { operation: 'read', write: null }),
    ),
  aiAsk: (write: AskRequest) =>
    withTimeout(
      invoke<CopilotAnswer>('ai_request', { operation: 'ask', write }),
    ),
  aiIngest: (write: DocumentWrite) =>
    withTimeout(
      invoke<KnowledgeDocument>('ai_request', { operation: 'document', write }),
    ),
  aiFeedback: (write: FeedbackWrite) =>
    withTimeout(
      invoke<FeedbackReceipt>('ai_request', { operation: 'feedback', write }),
    ),
  aiQuery: (query_id: string) =>
    withTimeout(
      invoke<QueryRun>('ai_request', {
        operation: 'query',
        write: { query_id },
      }),
    ),
  sync: () => withTimeout(invoke<SyncSnapshot>('sync_read')),
  finance: () =>
    withTimeout(
      invoke<FinanceSnapshot>('finance_request', {
        operation: 'read',
        write: null,
      }),
    ),
  saveTariff: (write: TariffWrite) =>
    withTimeout(
      invoke<TariffVersion>('finance_request', { operation: 'tariff', write }),
    ),
  verifySavings: (write: VerificationRequest) =>
    withTimeout(
      invoke<Verification>('finance_request', { operation: 'verify', write }),
    ),
  dispatch: () =>
    withTimeout(
      invoke<DispatchSnapshot>('dispatch_request', {
        operation: 'read',
        write: null,
      }),
    ),
  dispatchDetail: (command_id: string) =>
    withTimeout(
      invoke<DispatchDetail>('dispatch_request', {
        operation: 'detail',
        write: { command_id },
      }),
    ),
  requestApproval: (write: ApprovalRequest) =>
    withTimeout(
      invoke<DispatchCommand>('dispatch_request', {
        operation: 'request',
        write,
      }),
    ),
  decideDispatch: (write: DecisionRequest) =>
    withTimeout(
      invoke<DispatchCommand>('dispatch_request', {
        operation: 'decision',
        write,
      }),
    ),
  optimization: () =>
    withTimeout(
      invoke<OptimizationSnapshot>('optimization_request', {
        operation: 'read',
        write: null,
      }),
    ),
  optimizationHistory: (before: number) =>
    withTimeout(
      invoke<OptimizationRun[]>('optimization_request', {
        operation: 'history',
        write: { before },
      }),
    ),
  savePolicy: (write: PolicyWrite) =>
    withTimeout(
      invoke<OptimizationPolicy>('optimization_request', {
        operation: 'policy',
        write,
      }),
    ),
  optimize: (write: RunRequest) =>
    withTimeout(
      invoke<OptimizationRun>('optimization_request', {
        operation: 'run',
        write,
      }),
    ),
  intelligence: () =>
    withTimeout(invoke<IntelligenceSnapshot>('intelligence_read')),
  registry: () => withTimeout(invoke<RegistrySnapshot>('registry_read')),
  saveRegistry: (write: RegistryWrite) =>
    withTimeout(invoke<RegistryRecord>('registry_save', { write })),
  history: (before: number | null, asset: string | null) =>
    withTimeout(invoke<HistoryPage>('telemetry_history', { before, asset })),
  scenario: (scenario: string) =>
    withTimeout(invoke<void>('simulator_scenario', { scenario })),
  status: () => withTimeout(invoke<RuntimeSnapshot>('runtime_status')),
  restart: () => withTimeout(invoke<void>('runtime_restart')),
  stop: () => withTimeout(invoke<void>('runtime_stop')),
  diagnostics: () =>
    withTimeout(invoke<DiagnosticSnapshot>('runtime_diagnostics')),
};

export function hasFreshHealth(
  snapshot: RuntimeSnapshot,
  now = Date.now(),
): boolean {
  return (
    snapshot.state === 'READY' &&
    snapshot.health !== null &&
    snapshot.last_checked_ms !== null &&
    now >= snapshot.last_checked_ms &&
    now - snapshot.last_checked_ms <= 5000
  );
}

export async function withTimeout<T>(request: Promise<T>): Promise<T> {
  let timer: ReturnType<typeof setTimeout> | undefined;
  try {
    return await Promise.race([
      request,
      new Promise<never>((_, reject) => {
        timer = setTimeout(
          () => reject(new Error('Desktop bridge timed out')),
          2500,
        );
      }),
    ]);
  } finally {
    clearTimeout(timer);
  }
}
