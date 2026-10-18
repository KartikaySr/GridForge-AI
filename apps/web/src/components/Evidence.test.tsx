// @vitest-environment happy-dom
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { expect, it } from 'vitest';
import type { PortalHistory } from '@gridforge/api-client';
import { Evidence } from './Evidence';
async function render(
  stream: PortalHistory['events'][number]['stream'],
  body: Record<string, unknown>,
) {
  Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
  const host = document.createElement('div');
  const root = createRoot(host);
  await act(async () =>
    root.render(
      <Evidence
        event={{
          event_id: 'event',
          sequence: 1,
          stream,
          event_type: 'Test',
          received_at: '2026-10-11T00:00:00Z',
          body,
        }}
      />,
    ),
  );
  const text = host.textContent;
  await act(async () => root.unmount());
  return text;
}
it('renders dispatch transitions from the event envelope', async () => {
  expect(
    await render('dispatch', {
      from_state: 'SENT',
      to_state: 'FAILED',
      reason: 'ACK_TIMEOUT',
    }),
  ).toContain('ACK_TIMEOUT');
});
it('does not invent amounts for reference-only savings events', async () => {
  const text = await render('finance', {
    resource_id: 'verification-reference',
  });
  expect(text).toContain('monetary values');
  expect(text).toContain('no value is inferred');
  expect(text).not.toContain('0 USD');
});
it('renders registry entities nested inside the payload', async () => {
  expect(
    await render('registry', {
      payload: {
        entity: { name: 'Critical furnace', criticality: 'CRITICAL' },
      },
    }),
  ).toContain('Critical furnace');
});
