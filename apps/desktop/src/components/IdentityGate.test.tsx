// @vitest-environment happy-dom
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { afterEach, expect, it, vi } from 'vitest';
import axe from 'axe-core';
import { IdentityGate } from './IdentityGate';
import { runtimeBridge } from '../lib/runtime';
vi.mock('../lib/runtime', () => ({
  runtimeBridge: { identity: vi.fn(), signIn: vi.fn(), signOut: vi.fn() },
}));
Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
const container = document.createElement('div');
document.body.append(container);
const root = createRoot(container);
afterEach(async () => {
  await act(async () => root.render(null));
  vi.clearAllMocks();
});
it('keeps domain content hidden before sign-in and exposes labeled setup fields', async () => {
  vi.mocked(runtimeBridge.identity).mockResolvedValue({
    authenticated: false,
    setup_required: true,
    user: null,
    permissions: [],
    expires_at: null,
    mode: 'SIMULATION',
  });
  await act(async () =>
    root.render(
      <IdentityGate desktop>
        <div>Private telemetry</div>
      </IdentityGate>,
    ),
  );
  expect(container.textContent).not.toContain('Private telemetry');
  expect(
    container
      .querySelector('input[type="password"]')
      ?.getAttribute('minlength'),
  ).toBe('12');
  const report = await axe.run(container, {
    runOnly: {
      type: 'rule',
      values: [
        'label',
        'button-name',
        'select-name',
        'aria-valid-attr',
        'aria-valid-attr-value',
        'aria-allowed-attr',
      ],
    },
  });
  expect(report.violations.map((value) => value.id)).toEqual([]);
});
it('unmounts private content on successful sign-out', async () => {
  vi.mocked(runtimeBridge.identity).mockResolvedValue({
    authenticated: true,
    setup_required: false,
    user: null,
    permissions: [],
    expires_at: null,
    mode: 'SIMULATION',
  });
  vi.mocked(runtimeBridge.signOut).mockResolvedValue({
    authenticated: false,
    setup_required: false,
    user: null,
    permissions: [],
    expires_at: null,
    mode: 'SIMULATION',
  });
  await act(async () =>
    root.render(
      <IdentityGate desktop>
        <div>Private telemetry</div>
      </IdentityGate>,
    ),
  );
  expect(container.textContent).toContain('Private telemetry');
  await act(async () => container.querySelector('button')?.click());
  expect(container.textContent).not.toContain('Private telemetry');
  expect(container.textContent).toContain('Sign in to this facility');
});
