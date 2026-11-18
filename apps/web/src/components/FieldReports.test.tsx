// @vitest-environment happy-dom
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { expect, it, vi } from 'vitest';
import { api } from '../api';
import { FieldReports } from './FieldReports';
vi.mock('../api', () => ({ api: { reports: vi.fn() } }));
it('shows received field observations and clears them when the facility is deselected', async () => {
  Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
  vi.mocked(api.reports).mockResolvedValue({
    edge_id: 'edge',
    mode: 'SIMULATION',
    limit: 100,
    reports: [
      {
        request_id: 'report',
        edge_id: 'edge',
        text: 'Synthetic inspection',
        received_at: '2026-11-18T00:00:00Z',
        status: 'accepted',
      },
    ],
  });
  const host = document.createElement('div'),
    root = createRoot(host),
    onError = vi.fn();
  await act(async () =>
    root.render(<FieldReports edge="edge" revision={0} onError={onError} />),
  );
  expect(host.textContent).toContain('Synthetic inspection');
  await act(async () =>
    root.render(<FieldReports edge="" revision={0} onError={onError} />),
  );
  expect(host.textContent).not.toContain('Synthetic inspection');
  await act(async () => root.unmount());
});
it('ends the loading state and reports failed reads', async () => {
  vi.mocked(api.reports).mockRejectedValue(new Error('offline'));
  const host = document.createElement('div'),
    root = createRoot(host),
    onError = vi.fn();
  await act(async () =>
    root.render(<FieldReports edge="edge" revision={0} onError={onError} />),
  );
  expect(onError).toHaveBeenCalledOnce();
  expect(host.textContent).not.toContain('Loading reports');
  await act(async () => root.unmount());
});
