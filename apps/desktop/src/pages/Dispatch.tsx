import { useEffect, useRef, useState } from 'react';
import type {
  ApprovalRequest,
  DecisionRequest,
  DispatchDetail,
  DispatchSnapshot,
  OptimizationSnapshot,
} from '@gridforge/api-client';
import { runtimeBridge } from '../lib/runtime';

export function Dispatch({ desktop }: { desktop: boolean }) {
  const [data, setData] = useState<DispatchSnapshot | null>(null);
  const [optimization, setOptimization] = useState<OptimizationSnapshot | null>(
    null,
  );
  const [detail, setDetail] = useState<DispatchDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [received, setReceived] = useState(0);
  const [clock, setClock] = useState(Date.now());
  const [busy, setBusy] = useState(false);
  const [behavior, setBehavior] =
    useState<ApprovalRequest['behavior']>('normal');
  const [reason, setReason] = useState(
    'I reviewed the simulated proposal and current constraints.',
  );
  const pending = useRef<ApprovalRequest | DecisionRequest | null>(null);
  const currentId = useRef<string | null>(null);
  async function refresh() {
    const [dispatch, opt] = await Promise.all([
      runtimeBridge.dispatch(),
      runtimeBridge.optimization(),
    ]);
    setData(dispatch);
    setOptimization(opt);
    const id = currentId.current ?? dispatch.commands[0]?.id;
    if (id) setDetail(await runtimeBridge.dispatchDetail(id));
    setReceived(Date.now());
    setClock(Date.now());
    setError(null);
  }
  useEffect(() => {
    if (!desktop) return;
    let active = true;
    let loading = false;
    const poll = async () => {
      setClock(Date.now());
      if (loading) return;
      loading = true;
      try {
        const dispatch = await runtimeBridge.dispatch();
        if (active) setData(dispatch);
        const opt = await runtimeBridge.optimization();
        if (active) setOptimization(opt);
        const id = currentId.current ?? dispatch.commands[0]?.id;
        const info = id ? await runtimeBridge.dispatchDetail(id) : null;
        if (active) {
          setDetail(info);
          setReceived(Date.now());
          setClock(Date.now());
          setError(null);
        }
      } catch (cause) {
        if (active)
          setError(
            `Dispatch runtime unavailable: ${cause instanceof Error ? cause.message : String(cause)}`,
          );
      } finally {
        loading = false;
      }
    };
    void poll();
    const timer = setInterval(() => void poll(), 1000);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [desktop]);
  async function submit(write: ApprovalRequest | DecisionRequest) {
    pending.current = write;
    setBusy(true);
    try {
      const command =
        'run_id' in write
          ? await runtimeBridge.requestApproval(write)
          : await runtimeBridge.decideDispatch(write);
      currentId.current = command.id;
      pending.current = null;
      setNotice(`Command ${command.state}.`);
      await refresh();
    } catch {
      setError(
        'Request rejected or response lost. Refresh and retry the same request ID; check the timeline before creating another.',
      );
    } finally {
      setBusy(false);
    }
  }
  if (!desktop)
    return (
      <section className="surface">
        <h2>Native desktop required</h2>
        <p>
          Simulated dispatch is available only through the authenticated local
          runtime.
        </p>
      </section>
    );
  const fresh = !error && clock >= received && clock - received <= 5000;
  const command = detail?.command;
  const latest = optimization?.latest;
  const canRequest =
    !!latest?.proposal &&
    latest.status === 'PROPOSED' &&
    !data?.commands.some((c) => c.run_id === latest.id) &&
    !data?.commands.some(
      (c) =>
        !['COMPLETED', 'FAILED', 'CANCELLED', 'REJECTED'].includes(c.state),
    );
  const canDecide =
    !!command &&
    !['COMPLETED', 'FAILED', 'CANCELLED', 'REJECTED'].includes(command.state);
  const date = (value: string) =>
    new Date(value).toLocaleString(undefined, {
      timeZone: data?.timezone ?? 'UTC',
    });
  return (
    <div className="dispatchPage">
      <section className="surface">
        <span className="simulationPill">
          SIMULATION ONLY · HUMAN DECISION REQUIRED
        </span>
        <h2>Approval and dispatch</h2>
        <p>{data?.identity_notice ?? 'Loading local session…'}</p>
        <p>
          Actor: {data?.actor ?? 'Unknown'} · Session expires:{' '}
          {data?.session_expires_at ? date(data.session_expires_at) : 'Unknown'}{' '}
          · Worker: {data?.worker_error ?? 'Ready'}
        </p>
        <p>
          No physical OT connection. Approval does not imply measured load
          response or verified savings. Constraints are checked again before the
          simulator starts.
        </p>
        {error && <p role="alert">{error}</p>}
        {notice && <p role="status">{notice}</p>}
        {pending.current && (
          <div>
            <button
              disabled={busy}
              onClick={() => pending.current && void submit(pending.current)}
            >
              Retry same request ID
            </button>
            <button
              disabled={busy}
              onClick={() => {
                pending.current = null;
                setError(null);
                setNotice(
                  'Pending request cleared. Inspect the timeline before another action.',
                );
              }}
            >
              Clear pending request
            </button>
          </div>
        )}
        <p>
          {data
            ? `${data.command_count} / ${data.capacity} commands · ${data.pending_events} audit events pending sync`
            : 'Loading command state…'}
        </p>
      </section>
      <section className="surface">
        <h2>Request human approval</h2>
        {latest?.proposal ? (
          <>
            <p>
              Proposal {latest.proposal.id} ·{' '}
              {latest.proposal.expected_reduction_kw.toFixed(2)} kW ·{' '}
              {latest.request.duration_seconds} seconds ·{' '}
              {latest.candidates.filter((c) => c.selected_kw > 0).length}{' '}
              selected assets.
            </p>
            <p>{latest.proposal.explanation}</p>
          </>
        ) : (
          <p>No proposal exists. Generate one in Constraints & Optimization.</p>
        )}
        <label>
          Simulator behavior{' '}
          <select
            value={behavior}
            onChange={(e) =>
              setBehavior(e.target.value as ApprovalRequest['behavior'])
            }
          >
            <option value="normal">Normal ACK and response</option>
            <option value="delayed_ack">Delayed ACK (tests retry)</option>
            <option value="missing_ack">Missing ACK (fails closed)</option>
            <option value="failed_command">Simulator rejects command</option>
          </select>
        </label>
        <button
          className="primary"
          disabled={
            !fresh ||
            !canRequest ||
            busy ||
            !!pending.current ||
            !data?.permissions.includes('dispatch.request')
          }
          onClick={() =>
            latest &&
            void submit({
              request_id: crypto.randomUUID(),
              run_id: latest.id,
              behavior,
            })
          }
        >
          Request approval for simulation
        </button>
        {!canRequest && latest?.proposal && (
          <p>
            This proposal already has a command, or another command is active.
            Generate a fresh optimization run after the current command ends.
          </p>
        )}
      </section>
      <section className="surface">
        <h2>Command queue</h2>
        {data?.commands.length ? (
          <div className="tableScroll">
            <table>
              <thead>
                <tr>
                  <th>Command</th>
                  <th>State</th>
                  <th>Created</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {data.commands.map((c) => (
                  <tr key={c.id}>
                    <td>
                      {c.id.slice(0, 8)} · {c.behavior}
                    </td>
                    <td>{c.state}</td>
                    <td>{date(c.created_at)}</td>
                    <td>
                      <button
                        onClick={() => {
                          currentId.current = c.id;
                          void refresh();
                        }}
                      >
                        View timeline
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p>No dispatch commands yet.</p>
        )}
        {command && (
          <>
            <h3>Command {command.id}</h3>
            <p>
              {command.state} · revision {command.revision} · {command.reason}
            </p>
            <p>
              Attempts {command.attempts}/{command.max_attempts} · ACK{' '}
              {command.acknowledged_at
                ? date(command.acknowledged_at)
                : 'Not received'}{' '}
              · Started{' '}
              {command.execution_started_at
                ? date(command.execution_started_at)
                : 'Not started'}
            </p>
            <ul>
              {command.actions.map((a) => (
                <li key={a.asset_id}>
                  {a.asset_id}: {a.reduction_kw.toFixed(2)} kW simulated
                  reduction
                </li>
              ))}
            </ul>
            <label>
              Decision reason
              <input
                value={reason}
                maxLength={300}
                onChange={(e) => setReason(e.target.value)}
              />
            </label>
            <div className="dispatchDecisions">
              <button
                className="primary"
                disabled={
                  !fresh ||
                  busy ||
                  !!pending.current ||
                  command.state !== 'PENDING_APPROVAL' ||
                  !reason.trim() ||
                  !data?.permissions.includes('dispatch.approve')
                }
                onClick={() =>
                  void submit({
                    request_id: crypto.randomUUID(),
                    command_id: command.id,
                    expected_revision: command.revision,
                    action: 'approve',
                    reason,
                  })
                }
              >
                Approve simulated dispatch
              </button>
              <button
                disabled={
                  !fresh ||
                  busy ||
                  !!pending.current ||
                  command.state !== 'PENDING_APPROVAL' ||
                  !reason.trim() ||
                  !data?.permissions.includes('dispatch.approve')
                }
                onClick={() =>
                  void submit({
                    request_id: crypto.randomUUID(),
                    command_id: command.id,
                    expected_revision: command.revision,
                    action: 'reject',
                    reason,
                  })
                }
              >
                Reject
              </button>
              <button
                disabled={
                  !fresh ||
                  busy ||
                  !!pending.current ||
                  !canDecide ||
                  !reason.trim() ||
                  !data?.permissions.includes('dispatch.cancel')
                }
                onClick={() =>
                  void submit({
                    request_id: crypto.randomUUID(),
                    command_id: command.id,
                    expected_revision: command.revision,
                    action: 'cancel',
                    reason,
                  })
                }
              >
                Cancel
              </button>
            </div>
            <h3>Durable timeline</h3>
            <ol>
              {detail?.timeline.map((e) => (
                <li key={e.event_id}>
                  {date(e.occurred_at)} · {e.event_type} ·{' '}
                  {e.from_state ?? 'NEW'} → {e.to_state} · {e.actor} ·{' '}
                  {e.reason}
                </li>
              ))}
            </ol>
            <details>
              <summary>Approval and validation evidence</summary>
              <pre>
                {JSON.stringify(
                  {
                    run_id: command.run_id,
                    proposal_id: command.proposal_id,
                    validations: command.validations,
                  },
                  null,
                  2,
                )}
              </pre>
            </details>
          </>
        )}
      </section>
    </div>
  );
}
