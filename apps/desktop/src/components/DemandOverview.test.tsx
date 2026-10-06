// @vitest-environment happy-dom
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { expect, it, vi } from 'vitest';
import type { TelemetrySnapshot } from '@gridforge/api-client';
import { DemandOverview } from './DemandOverview';
vi.mock('../lib/runtime', () => ({
  runtimeBridge: {
    intelligence: vi.fn().mockRejectedValue(new Error('offline')),
  },
}));
it('withholds current load when the latest asset observation is stale', async () => {
  Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
  const host = document.createElement('div'),
    root = createRoot(host);
  const telemetry = {
    observed_at: new Date().toISOString(),
    assets: [
      {
        status: 'LIVE',
        point: {
          value: 999,
          quality: 'GOOD',
          flags: [],
          event_time: new Date(Date.now() - 20000).toISOString(),
        },
      },
    ],
  } as unknown as TelemetrySnapshot;
  await act(async () =>
    root.render(<DemandOverview desktop fresh telemetry={telemetry} />),
  );
  expect(host.textContent).not.toContain('999.0 kW');
  expect(host.textContent).toContain('UNKNOWN');
  expect(host.querySelector('svg')).toBeNull();
  await act(async () => root.unmount());
});
