// @vitest-environment happy-dom
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { describe, expect, it, vi } from 'vitest';
import type { RegistrySnapshot } from '@gridforge/api-client';
import { Registry } from './Registry';
import { runtimeBridge } from '../lib/runtime';

vi.mock('../lib/runtime', () => ({
  runtimeBridge: { registry: vi.fn(), saveRegistry: vi.fn() },
}));
const data: RegistrySnapshot = {
  schema_version: '1',
  mode: 'SIMULATION',
  org_id: 'org',
  facility_id: 'facility',
  records: [
    {
      revision: 3,
      entity: {
        kind: 'line',
        id: 'line-a',
        name: 'Line A',
        org_id: 'org',
        facility_id: 'facility',
        enabled: true,
      },
    },
  ],
  connectors: [],
  flexibility_available: [],
  pending_configuration_events: 3,
};

describe('Registry editing', () => {
  it('sends the selected revision and shows a conflict without discarding the draft', async () => {
    Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
    vi.mocked(runtimeBridge.registry).mockResolvedValue(data);
    vi.mocked(runtimeBridge.saveRegistry).mockRejectedValue(new Error('409'));
    const host = document.createElement('div');
    const root = createRoot(host);
    try {
      await act(async () =>
        root.render(<Registry desktop page="Facilities" />),
      );
      const select = Array.from(host.querySelectorAll('button')).find((b) =>
        b.textContent?.includes('Line A'),
      )!;
      await act(async () => select.click());
      expect(
        host
          .querySelector('input[aria-label="Record ID"]')
          ?.hasAttribute('disabled'),
      ).toBe(true);
      await act(async () =>
        host
          .querySelector('form')!
          .dispatchEvent(
            new Event('submit', { bubbles: true, cancelable: true }),
          ),
      );
      expect(runtimeBridge.saveRegistry).toHaveBeenCalledWith(
        expect.objectContaining({
          expected_revision: 3,
          entity: data.records[0].entity,
        }),
      );
      expect(host.textContent).toContain('Save not confirmed');
      expect(
        host.querySelector<HTMLInputElement>('input[aria-label="Name"]')!.value,
      ).toBe('Line A');
    } finally {
      await act(async () => root.unmount());
    }
  });
  it('keeps browser preview offline without invoking native configuration', async () => {
    Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
    vi.clearAllMocks();
    const host = document.createElement('div');
    const root = createRoot(host);
    try {
      await act(async () =>
        root.render(<Registry desktop={false} page="OT Devices" />),
      );
      expect(host.textContent).toContain('Open the native desktop');
      expect(runtimeBridge.registry).not.toHaveBeenCalled();
      expect(host.querySelector('form')).toBeNull();
    } finally {
      await act(async () => root.unmount());
    }
  });
  it('adds maintenance windows with explicit UTC times and preserves them in the save', async () => {
    Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
    const assetData: RegistrySnapshot = {
      ...data,
      records: [
        {
          revision: 1,
          entity: {
            kind: 'asset',
            id: 'asset-a',
            name: 'Asset A',
            org_id: 'org',
            facility_id: 'facility',
            enabled: true,
            line_id: 'line-a',
            rated_kw: 100,
            min_load_kw: 0,
            max_load_kw: 200,
            capabilities: ['telemetry'],
            criticality: 'NORMAL',
            flexible: false,
            max_reduction_kw: 0,
            min_run_seconds: 0,
            min_off_seconds: 0,
            maintenance: [],
          },
        },
      ],
    };
    vi.mocked(runtimeBridge.registry).mockResolvedValue(assetData);
    vi.mocked(runtimeBridge.saveRegistry).mockResolvedValue({
      ...assetData.records[0],
      revision: 2,
    });
    const host = document.createElement('div');
    const root = createRoot(host);
    try {
      await act(async () => root.render(<Registry desktop page="Assets" />));
      const click = async (label: string) => {
        const button = Array.from(host.querySelectorAll('button')).find((b) =>
          b.textContent?.includes(label),
        )!;
        await act(async () => button.click());
      };
      await click('Asset A');
      await click('Add maintenance window');
      expect(host.querySelector('textarea')).toBeNull();
      expect(
        host.querySelector<HTMLInputElement>(
          'input[aria-label="Maintenance start 1"]',
        )!.type,
      ).toBe('datetime-local');
      expect(host.textContent).toContain('Start (UTC)');
      await act(async () =>
        host
          .querySelector('form')!
          .dispatchEvent(
            new Event('submit', { bubbles: true, cancelable: true }),
          ),
      );
      const sent = vi.mocked(runtimeBridge.saveRegistry).mock.calls.at(-1)![0];
      expect(sent.entity.kind).toBe('asset');
      if (sent.entity.kind === 'asset') {
        expect(sent.entity.maintenance).toHaveLength(1);
        expect(sent.entity.maintenance[0].starts_at).toMatch(/Z$/);
        expect(Date.parse(sent.entity.maintenance[0].ends_at)).toBeGreaterThan(
          Date.parse(sent.entity.maintenance[0].starts_at),
        );
      }
    } finally {
      await act(async () => root.unmount());
    }
  });
});
