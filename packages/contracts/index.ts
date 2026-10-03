export type HealthState = 'healthy' | 'warning' | 'critical' | 'offline';
export interface DashboardMetrics {
  currentLoadKw: number;
  predictedPeakKw: number;
  thresholdKw: number;
  peakRiskPct: number;
  todaySavingsInr: number;
  activeAlerts: number;
  telemetryPerSecond: number;
}
export interface Asset {
  id: string;
  name: string;
  type: string;
  line: string;
  currentLoadKw: number;
  ratedLoadKw: number;
  flexibilityKw: number;
  criticality: 'low' | 'medium' | 'high';
  status: HealthState;
}
export interface TelemetryPoint {
  timestamp: string;
  assetId: string;
  voltage: number;
  current: number;
  activePowerKw: number;
  vibration: number;
  quality: 'valid' | 'suspect';
}
export interface OptimizationProposal {
  id: string;
  assetId: string;
  action: string;
  reductionKw: number;
  durationMinutes: number;
  expectedSavingsInr: number;
  productionImpactPct: number;
  status: 'proposed' | 'approved' | 'rejected' | 'completed';
}
