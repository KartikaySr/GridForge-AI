// @vitest-environment happy-dom
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { describe, expect, it, vi } from 'vitest';
import type { CopilotAnswer, CopilotSnapshot } from '@gridforge/api-client';
import { runtimeBridge } from '../lib/runtime';
import { Copilot } from './Copilot';

vi.mock('../lib/runtime', () => ({
  runtimeBridge: { ai: vi.fn(), aiQuery: vi.fn(), aiFeedback: vi.fn() },
}));

async function mount(desktop: boolean) {
  Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
  const container = document.createElement('div');
  document.body.append(container);
  const root = createRoot(container);
  await act(async () => root.render(<Copilot desktop={desktop} />));
  return {
    container,
    close: async () => {
      await act(async () => root.unmount());
      container.remove();
    },
  };
}

const answer: CopilotAnswer = {
  id: 'answer',
  request_id: 'request',
  conversation_id: 'conversation',
  question: 'Compressor SOP?',
  answer:
    'Retrieved source excerpts (untrusted document content; advisory only): <script>evil()</script>',
  status: 'ANSWERED',
  provider: 'local-extractive-v1',
  created_at: new Date().toISOString(),
  evidence: [
    {
      citation: 'D1',
      document_id: 'document',
      revision: 2,
      title: 'SOP',
      source: 'Manual',
      chunk_id: 'chunk',
      start: 0,
      end: 24,
      digest: 'digest',
      excerpt: '<script>evil()</script>',
      score: 0.5,
    },
  ],
  query_id: 'query',
  mode: 'SIMULATION',
  advisory_only: true,
};

const snapshot = (): CopilotSnapshot => ({
  provider: 'local-extractive-v1',
  embedding_model: 'token-hash-256-v1',
  provider_state: 'READY',
  retrieval_backend: 'LOCAL',
  query_backend: 'LOCAL_READ_ONLY',
  advisory_only: true,
  mode: 'SIMULATION',
  can_ingest: false,
  can_inspect: false,
  documents: [],
  answers: [answer],
  semantic_views: {},
});

describe('AI Copilot', () => {
  it('requires the authenticated native runtime', async () => {
    vi.mocked(runtimeBridge.ai).mockClear();
    const view = await mount(false);
    expect(view.container.textContent).toContain('Native desktop required');
    expect(runtimeBridge.ai).not.toHaveBeenCalled();
    await view.close();
  });
  it('renders source text safely and hides privileged actions', async () => {
    vi.mocked(runtimeBridge.ai).mockResolvedValue(snapshot());
    const view = await mount(true);
    const button = [...view.container.querySelectorAll('button')].find((node) =>
      node.textContent?.includes('Compressor SOP?'),
    )!;
    await act(async () => button.click());
    expect(view.container.textContent).toContain('revision 2');
    expect(view.container.textContent).toContain('<script>evil()</script>');
    expect(view.container.querySelector('script')).toBeNull();
    expect(view.container.textContent).not.toContain('Inspect query');
    expect(view.container.textContent).not.toContain('Ingest document');
    await view.close();
  });
  it('shows provider failure without claiming an answer', async () => {
    vi.mocked(runtimeBridge.ai).mockResolvedValue({
      ...snapshot(),
      provider_state: 'UNAVAILABLE',
      answers: [],
    });
    const view = await mount(true);
    expect(view.container.textContent).toContain('UNAVAILABLE');
    expect(view.container.textContent).toContain('No conversations yet.');
    expect(view.container.textContent).toContain('ADVISORY ONLY');
    await view.close();
  });
  it('opens the server query inspector only for an authorized user', async () => {
    vi.mocked(runtimeBridge.ai).mockResolvedValue({
      ...snapshot(),
      can_inspect: true,
    });
    vi.mocked(runtimeBridge.aiQuery).mockResolvedValue({
      id: 'query',
      status: 'REJECTED',
      proposed_sql: 'DROP TABLE telemetry',
      executed_sql: null,
      parameters: [],
      columns: [],
      rows: [],
      row_limit: 100,
      source_row_limit: 1000,
      timeout_ms: 200,
      source_view: null,
      observed_at: new Date().toISOString(),
      error: 'SELECT_ONLY',
      result_digest: null,
    });
    const view = await mount(true);
    await act(async () =>
      [...view.container.querySelectorAll('button')]
        .find((node) => node.textContent?.includes('Compressor SOP?'))!
        .click(),
    );
    await act(async () =>
      [...view.container.querySelectorAll('button')]
        .find((node) => node.textContent === 'Inspect query')!
        .click(),
    );
    expect(runtimeBridge.aiQuery).toHaveBeenCalledWith('query');
    expect(view.container.textContent).toContain('SELECT_ONLY');
    await view.close();
  });
});
