// @vitest-environment happy-dom
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { describe, expect, it, vi } from 'vitest';
import type { SyncSnapshot } from '@gridforge/api-client';
import { runtimeBridge } from '../lib/runtime';
import { SyncCenter } from './SyncCenter';

vi.mock('../lib/runtime', () => ({ runtimeBridge: { sync: vi.fn() } }));

async function mount(desktop: boolean) {
  Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
  const container = document.createElement('div');
  document.body.append(container);
  const root = createRoot(container);
  await act(async () => root.render(<SyncCenter desktop={desktop} />));
  return {
    container,
    close: async () => {
      await act(async () => root.unmount());
      container.remove();
    },
  };
}

function snapshot(): SyncSnapshot {
  return {
    schema_version: '1',
    mode: 'SIMULATION',
    edge_id: '00000000-0000-4000-8000-000000000001',
    org_id: '00000000-0000-4000-8000-000000000002',
    facility_id: '00000000-0000-4000-8000-000000000003',
    observed_at: new Date().toISOString(),
    state: 'OFFLINE',
    configured: true,
    pending_count: 4,
    oldest_pending_at: new Date(Date.now() - 60000).toISOString(),
    oldest_pending_age_seconds: 60,
    last_success_at: null,
    conflict_count: 0,
    conflicts: [],
    streams: [
      {
        stream: 'dispatch',
        local_last_sequence: 4,
        acknowledged_sequence: 0,
        pending_count: 4,
        oldest_pending_at: new Date(Date.now() - 60000).toISOString(),
        last_success_at: null,
        last_error: null,
        conflict_code: null,
      },
    ],
    message: 'Cloud unavailable; local operation continues',
  };
}

describe('Sync Center', () => {
  it('does not invent cloud status in browser preview', async () => {
    vi.mocked(runtimeBridge.sync).mockClear();
    const view = await mount(false);
    expect(view.container.textContent).toContain('Native desktop required');
    expect(runtimeBridge.sync).not.toHaveBeenCalled();
    await view.close();
  });
  it('shows offline backlog and acknowledged cursors honestly', async () => {
    vi.mocked(runtimeBridge.sync).mockResolvedValue(snapshot());
    const view = await mount(true);
    expect(view.container.textContent).toContain('OFFLINE');
    expect(view.container.textContent).toContain(
      '4 events pending acknowledgement',
    );
    expect(view.container.textContent).toContain('cloud acknowledged 0');
    expect(view.container.textContent).toContain(
      'continue while cloud sync is offline',
    );
    await view.close();
  });
});
