import type {
  FieldReportReceipt,
  FieldReportWrite,
} from '@gridforge/api-client';
import { ApiError } from '../api';
import { acknowledge, pendingForUser, type PendingReport } from './outbox';

export async function synchronizeReports(
  reports: PendingReport[],
  owner: string,
  send: (body: FieldReportWrite) => Promise<FieldReportReceipt>,
  save: (report: PendingReport) => Promise<void>,
): Promise<void> {
  for (const report of pendingForUser(reports, owner)) {
    try {
      const receipt = await send({
        request_id: report.requestId,
        edge_id: report.facilityId,
        text: report.text,
      });
      await save(acknowledge(report, receipt.request_id, 'accepted'));
    } catch (error) {
      if (error instanceof ApiError && error.status === 409)
        await save(acknowledge(report, report.requestId, 'conflict'));
      else throw error;
    }
  }
}
