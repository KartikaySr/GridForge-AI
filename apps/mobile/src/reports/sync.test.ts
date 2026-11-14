import { expect, it, vi } from 'vitest';
import { ApiError } from '../api';
import { synchronizeReports } from './sync';
import type { PendingReport } from './outbox';
const report: PendingReport = {
  requestId: 'request',
  userId: 'owner',
  facilityId: 'edge',
  text: 'Observation',
  state: 'PENDING',
};
it('retries a lost response with the same immutable payload and only then marks synced', async () => {
  const send = vi
    .fn()
    .mockRejectedValueOnce(new Error('offline'))
    .mockResolvedValue({
      request_id: report.requestId,
      status: 'accepted',
      received_at: '2026-11-14T00:00:00Z',
    });
  const save = vi.fn();
  await expect(
    synchronizeReports([report], 'owner', send, save),
  ).rejects.toThrow('offline');
  expect(save).not.toHaveBeenCalled();
  await synchronizeReports(
    [report, { ...report, userId: 'someone-else' }],
    'owner',
    send,
    save,
  );
  expect(send.mock.calls[0]).toEqual(send.mock.calls[1]);
  expect(send).toHaveBeenCalledTimes(2);
  expect(save).toHaveBeenCalledWith({ ...report, state: 'SYNCED' });
});
it('retains conflicting replays and rejects mismatched acknowledgements', async () => {
  const save = vi.fn();
  await synchronizeReports(
    [report],
    'owner',
    vi.fn().mockRejectedValue(new ApiError(409)),
    save,
  );
  expect(save).toHaveBeenCalledWith({ ...report, state: 'CONFLICT' });
  save.mockClear();
  await expect(
    synchronizeReports(
      [report],
      'owner',
      vi.fn().mockResolvedValue({ request_id: 'wrong' }),
      save,
    ),
  ).rejects.toThrow('REPORT_ACK_MISMATCH');
  expect(save).not.toHaveBeenCalled();
});
