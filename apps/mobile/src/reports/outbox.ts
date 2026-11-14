/** Pure transition policy; persistence and transport adapters must preserve these identifiers. */
export type PendingReport = {
  requestId: string;
  userId: string;
  facilityId: string;
  text: string;
  state: 'PENDING' | 'SYNCED' | 'CONFLICT';
};
export function pendingForUser(
  reports: PendingReport[],
  userId: string,
): PendingReport[] {
  return reports.filter(
    (report) => report.userId === userId && report.state === 'PENDING',
  );
}
export function acknowledge(
  report: PendingReport,
  requestId: string,
  outcome: 'accepted' | 'conflict',
): PendingReport {
  if (report.requestId !== requestId) throw new Error('REPORT_ACK_MISMATCH');
  if (report.state !== 'PENDING') return report;
  return { ...report, state: outcome === 'accepted' ? 'SYNCED' : 'CONFLICT' };
}
