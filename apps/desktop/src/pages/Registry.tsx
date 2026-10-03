import { useEffect, useState } from 'react';
import type {
  RegistryEntity,
  RegistryRecord,
  RegistrySnapshot,
} from '@gridforge/api-client';
import { runtimeBridge } from '../lib/runtime';
import { StatusBadge } from '../components/StatusBadge';

type Kind = RegistryEntity['kind'];
type MaintenanceWindow = Extract<
  RegistryEntity,
  { kind: 'asset' }
>['maintenance'][number];
const kinds: Record<string, Kind[]> = {
  Facilities: ['organization', 'facility', 'line'],
  Assets: ['asset'],
  'OT Devices': ['device', 'mapping', 'metric'],
};

function blank(kind: Kind, data: RegistrySnapshot): RegistryEntity {
  const base = {
    id: `${kind}-${crypto.randomUUID().slice(0, 8)}`,
    name: '',
    org_id: data.org_id,
    facility_id: data.facility_id,
    enabled: true,
  };
  const first = (type: Kind) =>
    data.records.find((r) => r.entity.kind === type && r.entity.enabled)?.entity
      .id ?? '';
  switch (kind) {
    case 'organization':
      return { ...base, kind, id: data.org_id };
    case 'facility':
      return { ...base, kind, id: data.facility_id, timezone: 'UTC' };
    case 'line':
      return { ...base, kind };
    case 'asset':
      return {
        ...base,
        kind,
        line_id: first('line'),
        rated_kw: 0,
        max_load_kw: 0,
        min_load_kw: 0,
        criticality: 'NORMAL',
        capabilities: ['telemetry'],
        flexible: false,
        max_reduction_kw: 0,
        min_run_seconds: 0,
        min_off_seconds: 0,
        maintenance: [],
      };
    case 'device':
      return { ...base, kind, protocol: 'SIMULATOR', writable: false };
    case 'metric':
      return {
        ...base,
        kind,
        id: 'active_power',
        metric: 'active_power',
        canonical_unit: 'kW',
      };
    case 'mapping':
      return {
        ...base,
        kind,
        asset_id: first('asset'),
        device_id: first('device'),
        signal_id: 'active-power',
        metric_id: 'active_power',
        input_unit: 'W',
        scale: 0.001,
        offset: 0,
        writable: false,
      };
  }
}

export function Registry({
  page,
  desktop,
}: {
  page: string;
  desktop: boolean;
}) {
  const [data, setData] = useState<RegistrySnapshot | null>(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [selected, setSelected] = useState<RegistryRecord | null>(null);
  const [maintenance, setMaintenance] = useState<MaintenanceWindow[]>([]);
  const [saving, setSaving] = useState(false);
  const [fresh, setFresh] = useState(false);
  const allowed = kinds[page] ?? [];
  useEffect(() => {
    if (!desktop) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try {
        const next = await runtimeBridge.registry();
        if (!cancelled) {
          setData(next);
          setFresh(true);
        }
      } catch {
        if (!cancelled) setFresh(false);
      }
      if (!cancelled) timer = setTimeout(poll, 2000);
    };
    void poll();
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [desktop]);
  function choose(record: RegistryRecord) {
    setSelected(record);
    setError('');
    setNotice('');
    setMaintenance(
      record.entity.kind === 'asset' ? record.entity.maintenance : [],
    );
  }
  function patch(values: Partial<RegistryEntity>) {
    if (selected)
      setSelected({
        ...selected,
        entity: { ...selected.entity, ...values } as RegistryEntity,
      });
  }
  async function save() {
    if (!selected || !fresh) return;
    setSaving(true);
    setError('');
    setNotice('');
    try {
      const entity =
        selected.entity.kind === 'asset'
          ? {
              ...selected.entity,
              maintenance,
            }
          : selected.entity;
      const saved = await runtimeBridge.saveRegistry({
        entity,
        expected_revision: selected.revision,
        request_id: crypto.randomUUID(),
      });
      choose(saved);
      setData(await runtimeBridge.registry());
      setNotice(
        `Saved revision ${saved.revision}. Configuration and audit event are durable.`,
      );
    } catch {
      setError(
        'Save not confirmed. Check values and parent references. Refresh the record before retrying: another edit or a lost response may have advanced its revision.',
      );
    } finally {
      setSaving(false);
    }
  }
  if (!desktop)
    return (
      <section className="surface">
        <h2>{page} registry</h2>
        <p>
          Open the native desktop to inspect and configure the simulation
          registry.
        </p>
      </section>
    );
  if (!data)
    return (
      <section className="surface">
        <h2>Registry unavailable</h2>
        <p>
          Waiting for the local runtime. Use System Health to start or recover
          it.
        </p>
      </section>
    );
  const entity = selected?.entity;
  function text(label: string, key: string, value: string, disabled = false) {
    return (
      <label>
        {label}
        <input
          aria-label={label}
          value={value}
          disabled={disabled || saving}
          onChange={(e) => patch({ [key]: e.target.value })}
        />
      </label>
    );
  }
  function number(label: string, key: string, value: number) {
    return (
      <label>
        {label}
        <input
          aria-label={label}
          type="number"
          step="any"
          value={value}
          disabled={saving}
          onChange={(e) => patch({ [key]: Number(e.target.value) })}
        />
      </label>
    );
  }
  function reference(label: string, key: string, value: string, kind: Kind) {
    return (
      <label>
        {label}
        <select
          aria-label={label}
          value={value}
          disabled={saving}
          onChange={(e) => patch({ [key]: e.target.value })}
        >
          <option value="">Select {kind}</option>
          {data!.records
            .filter((r) => r.entity.kind === kind)
            .map((r) => (
              <option key={r.entity.id} value={r.entity.id}>
                {r.entity.name}
                {r.entity.enabled ? '' : ' (disabled)'}
              </option>
            ))}
        </select>
      </label>
    );
  }
  return (
    <>
      {!fresh && (
        <p className="runtimeBanner" role="alert">
          Registry connection lost. Last known configuration is shown; saving is
          disabled.
        </p>
      )}
      <section className="surface">
        <div className="sectionHeader">
          <div>
            <span className="eyebrow">
              SIMULATION CONFIGURATION · SERVER-SCOPED
            </span>
            <h2>{page}</h2>
          </div>
          <StatusBadge state={fresh ? 'READY' : 'DISCONNECTED'} />
        </div>
        <p className="muted">
          One local organization and facility. Registry edits do not grant
          control authority. Disable dependents before disabling their parent.
        </p>
        <div className="registryActions">
          {allowed
            .filter(
              (kind) => !['organization', 'facility', 'metric'].includes(kind),
            )
            .map((kind) => (
              <button
                key={kind}
                className="secondary"
                disabled={!fresh || saving}
                onClick={() =>
                  choose({ revision: 0, entity: blank(kind, data) })
                }
              >
                Add {kind}
              </button>
            ))}
        </div>
        <div className="registryLayout">
          <div className="registryList">
            {data.records
              .filter((r) => allowed.includes(r.entity.kind))
              .map((record) => (
                <button
                  className="secondary"
                  key={record.entity.kind + record.entity.id}
                  disabled={saving}
                  onClick={() => choose(record)}
                >
                  <strong>{record.entity.name}</strong>
                  <span>
                    {record.entity.kind} · {record.entity.id} · v
                    {record.revision} ·{' '}
                    {record.entity.enabled ? 'enabled' : 'disabled'}
                  </span>
                </button>
              ))}
          </div>
          {entity ? (
            <form
              className="registryForm"
              onSubmit={(e) => {
                e.preventDefault();
                void save();
              }}
            >
              <h3>
                {selected!.revision ? 'Edit' : 'Create'} {entity.kind}
              </h3>
              {text('Record ID', 'id', entity.id, selected!.revision > 0)}
              {text('Name', 'name', entity.name)}
              {!['organization', 'facility', 'metric'].includes(
                entity.kind,
              ) && (
                <label className="checkLabel">
                  <input
                    type="checkbox"
                    checked={entity.enabled}
                    disabled={saving}
                    onChange={(e) => patch({ enabled: e.target.checked })}
                  />
                  Enabled
                </label>
              )}
              {entity.kind === 'facility' && (
                <>
                  {text(
                    'Facility timezone (IANA)',
                    'timezone',
                    entity.timezone,
                  )}
                  <label>
                    Simulation demand threshold (kW, optional)
                    <input
                      type="number"
                      min="0.001"
                      max="100000000"
                      step="any"
                      aria-label="Simulation demand threshold"
                      value={entity.simulation_demand_threshold_kw ?? ''}
                      disabled={saving}
                      onChange={(e) =>
                        patch({
                          simulation_demand_threshold_kw:
                            e.target.value === ''
                              ? null
                              : Number(e.target.value),
                        })
                      }
                    />
                    <small>
                      Advisory simulation threshold, not a safety limit or
                      utility contract. Empty means risk UNKNOWN.
                    </small>
                  </label>
                </>
              )}
              {entity.kind === 'asset' && (
                <>
                  {reference(
                    'Production line',
                    'line_id',
                    entity.line_id,
                    'line',
                  )}
                  {number('Rated load (kW)', 'rated_kw', entity.rated_kw)}
                  {number(
                    'Minimum load (kW)',
                    'min_load_kw',
                    entity.min_load_kw,
                  )}
                  {number(
                    'Maximum load (kW)',
                    'max_load_kw',
                    entity.max_load_kw,
                  )}
                  <label>
                    Criticality
                    <select
                      value={entity.criticality}
                      disabled={saving}
                      onChange={(e) =>
                        patch({
                          criticality: e.target.value as 'NORMAL' | 'CRITICAL',
                        })
                      }
                    >
                      <option>NORMAL</option>
                      <option>CRITICAL</option>
                    </select>
                  </label>
                  <label className="checkLabel">
                    <input
                      type="checkbox"
                      checked={entity.capabilities.includes(
                        'simulated_load_adjustment',
                      )}
                      disabled={saving}
                      onChange={(e) =>
                        patch({
                          capabilities: e.target.checked
                            ? ['telemetry', 'simulated_load_adjustment']
                            : ['telemetry'],
                        })
                      }
                    />
                    Declare simulated load adjustment capability
                  </label>
                  <label className="checkLabel">
                    <input
                      type="checkbox"
                      checked={entity.flexible}
                      disabled={saving}
                      onChange={(e) => patch({ flexible: e.target.checked })}
                    />
                    Flexible metadata (not dispatch authorization)
                  </label>
                  {number(
                    'Maximum reduction (kW)',
                    'max_reduction_kw',
                    entity.max_reduction_kw,
                  )}
                  {number(
                    'Minimum run time (seconds)',
                    'min_run_seconds',
                    entity.min_run_seconds,
                  )}
                  {number(
                    'Minimum off time (seconds)',
                    'min_off_seconds',
                    entity.min_off_seconds,
                  )}
                  <fieldset className="maintenanceWindows">
                    <legend>Maintenance windows</legend>
                    {maintenance.map((window, index) => (
                      <div className="maintenanceWindow" key={index}>
                        <label>
                          Start (UTC)
                          <input
                            aria-label={`Maintenance start ${index + 1}`}
                            type="datetime-local"
                            required
                            disabled={saving}
                            value={window.starts_at.slice(0, 16)}
                            onChange={(e) =>
                              setMaintenance((previous) =>
                                previous.map((item, i) =>
                                  i === index
                                    ? {
                                        ...item,
                                        starts_at: e.target.value
                                          ? `${e.target.value}:00Z`
                                          : '',
                                      }
                                    : item,
                                ),
                              )
                            }
                          />
                        </label>
                        <label>
                          End (UTC)
                          <input
                            aria-label={`Maintenance end ${index + 1}`}
                            type="datetime-local"
                            required
                            disabled={saving}
                            value={window.ends_at.slice(0, 16)}
                            onChange={(e) =>
                              setMaintenance((previous) =>
                                previous.map((item, i) =>
                                  i === index
                                    ? {
                                        ...item,
                                        ends_at: e.target.value
                                          ? `${e.target.value}:00Z`
                                          : '',
                                      }
                                    : item,
                                ),
                              )
                            }
                          />
                        </label>
                        <label>
                          Reason
                          <input
                            aria-label={`Maintenance reason ${index + 1}`}
                            required
                            maxLength={200}
                            disabled={saving}
                            value={window.reason}
                            onChange={(e) =>
                              setMaintenance((previous) =>
                                previous.map((item, i) =>
                                  i === index
                                    ? { ...item, reason: e.target.value }
                                    : item,
                                ),
                              )
                            }
                          />
                        </label>
                        <button
                          type="button"
                          className="secondary"
                          disabled={saving}
                          onClick={() =>
                            setMaintenance((previous) =>
                              previous.filter((_, i) => i !== index),
                            )
                          }
                        >
                          Remove window {index + 1}
                        </button>
                      </div>
                    ))}
                    {maintenance.length === 0 && (
                      <p>No maintenance windows scheduled.</p>
                    )}
                    <button
                      type="button"
                      className="secondary"
                      disabled={saving || maintenance.length >= 20}
                      onClick={() =>
                        setMaintenance((previous) => [
                          ...previous,
                          {
                            starts_at: new Date().toISOString(),
                            ends_at: new Date(
                              Date.now() + 3600000,
                            ).toISOString(),
                            reason: '',
                          },
                        ])
                      }
                    >
                      Add maintenance window
                    </button>
                  </fieldset>
                  <small>
                    Schedule times use UTC explicitly. Maintenance excludes
                    flexibility metadata; telemetry continues. Changes apply
                    only when saved.
                  </small>
                  <p>
                    Metadata eligibility now:{' '}
                    {data.flexibility_available.includes(entity.id)
                      ? 'Eligible'
                      : 'Restricted / not declared'}
                    . This does not authorize optimization or dispatch.
                  </p>
                </>
              )}
              {entity.kind === 'device' && (
                <p>
                  Protocol: SIMULATOR · Physical writes: disabled. This
                  connector has no execution method.
                </p>
              )}
              {entity.kind === 'mapping' && (
                <>
                  {reference('Asset', 'asset_id', entity.asset_id, 'asset')}
                  {reference('Device', 'device_id', entity.device_id, 'device')}
                  {text('Signal ID', 'signal_id', entity.signal_id)}
                  <p>Canonical metric: active_power · output: kW · read-only</p>
                  <label>
                    Input unit
                    <select
                      value={entity.input_unit}
                      disabled={saving}
                      onChange={(e) =>
                        patch({ input_unit: e.target.value as 'W' | 'kW' })
                      }
                    >
                      <option>W</option>
                      <option>kW</option>
                    </select>
                  </label>
                  {number('Scale to canonical kW', 'scale', entity.scale)}
                  {number('Offset (kW)', 'offset', entity.offset)}
                  <small>
                    Canonical value = raw value × scale + offset. One enabled
                    active-power mapping per asset.
                  </small>
                </>
              )}
              {entity.kind === 'metric' && (
                <p>
                  active_power · canonical kW. Other metric families are not
                  commissioned.
                </p>
              )}
              {error && <p role="alert">{error}</p>}
              {notice && <p role="status">{notice}</p>}
              <div className="registryActions">
                <button disabled={!fresh || saving}>
                  {saving ? 'Saving…' : 'Save configuration'}
                </button>
                {selected!.revision > 0 && (
                  <button
                    type="button"
                    className="secondary"
                    disabled={saving}
                    onClick={() => {
                      const latest = data.records.find(
                        (r) =>
                          r.entity.kind === entity.kind &&
                          r.entity.id === entity.id,
                      );
                      if (latest) choose(latest);
                    }}
                  >
                    Refresh record
                  </button>
                )}
              </div>
            </form>
          ) : (
            <p className="muted">
              Select a record to inspect its configuration and revision.
            </p>
          )}
        </div>
      </section>
      {page === 'OT Devices' && (
        <section className="surface">
          <h2>Connector health and diagnostics</h2>
          <p>
            Configuration events awaiting cloud acknowledgement:{' '}
            {data.pending_configuration_events}
          </p>
          {data.connectors.map((connector) => (
            <article className="connectorRow" key={connector.device_id}>
              <strong>{connector.device_id}</strong>
              <StatusBadge state={fresh ? connector.state : 'DISCONNECTED'} />
              <p>
                {connector.mapping_count} active mappings · Last receipt:{' '}
                {connector.last_received_at ?? 'None'}
              </p>
              <p>{connector.detail}</p>
            </article>
          ))}
          <p className="muted">
            Use Telemetry scenario controls to simulate a disconnect, bad
            quality or stale data. Reconnect by returning to normal.
          </p>
        </section>
      )}
    </>
  );
}
