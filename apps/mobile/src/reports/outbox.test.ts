import { expect, it } from 'vitest';
import { acknowledge, pendingForUser, type PendingReport } from './outbox';
const report: PendingReport = {
  requestId: 'r1',
  userId: 'user-a',
  facilityId: 'facility-a',
  text: 'Inspect compressor',
  state: 'PENDING',
};
it('never offers another user reports for upload', () => {
  expect(pendingForUser([report], 'user-b')).toEqual([]);
  expect(pendingForUser([report], 'user-a')).toEqual([report]);
});
it('requires the matching acknowledgement before marking a report synchronized', () => {
  expect(() => acknowledge(report, 'other', 'accepted')).toThrow(
    'REPORT_ACK_MISMATCH',
  );
  expect(acknowledge(report, 'r1', 'accepted')).toMatchObject({
    requestId: 'r1',
    state: 'SYNCED',
  });
  expect(report.state).toBe('PENDING');
});
it('holds conflicting reports rather than retrying them automatically', () => {
  const conflict = acknowledge(report, 'r1', 'conflict');
  expect(pendingForUser([conflict], 'user-a')).toEqual([]);
});
