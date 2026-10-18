import type { PortalHistory } from '@gridforge/api-client';
type Event = PortalHistory['events'][number];
function object(value: unknown): Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}
export function Evidence({ event }: { event: Event }) {
  const payload = object(event.body.payload);
  const entity = object(payload.entity);
  const data = {
    ...event.body,
    ...payload,
    ...entity,
    ...object(payload.proposal),
  };
  const fields = [
    'amount',
    'currency',
    'net_energy_value',
    'net_energy_kwh',
    'rebound_kwh',
    'measured_reduction_kw',
    'expected_reduction_kw',
    'forecast_peak_kw',
    'required_reduction_kw',
    'name',
    'kind',
    'asset_id',
    'enabled',
    'criticality',
    'flexible',
    'min_load_kw',
    'max_load_kw',
    'max_reduction_kw',
    'status',
    'quality',
    'value',
    'unit',
    'model_version',
    'threshold_kw',
    'predicted_peak_kw',
    'from_state',
    'to_state',
    'revision',
    'command_id',
    'resource_id',
    'correlation_id',
    'actor',
  ];
  const values = Array.isArray(payload.values)
    ? payload.values.map(object)
    : [];
  return (
    <>
      <div className="facts">
        {fields
          .filter((key) =>
            ['string', 'number', 'boolean'].includes(typeof data[key]),
          )
          .map((key) => (
            <div key={key}>
              <span>{key.replaceAll('_', ' ')}</span>
              <b>{String(data[key])}</b>
            </div>
          ))}
      </div>
      {typeof data.reason === 'string' && <p>{data.reason}</p>}
      {values.length > 0 && (
        <details>
          <summary>Forecast intervals ({values.length})</summary>
          <ul>
            {values.map((value, index) => (
              <li key={index}>
                {String(value.starts_at ?? 'Unknown time')} —{' '}
                {String(value.value_kw ?? 'Unavailable')} kW
              </li>
            ))}
          </ul>
        </details>
      )}
      {['finance', 'optimization'].includes(event.stream) &&
        Object.keys(payload).length === 0 && (
          <p role="note">
            This synchronized event contains references only. Detailed{' '}
            {event.stream === 'finance'
              ? 'verification measurements and monetary values'
              : 'constraints and proposed adjustments'}{' '}
            are not available in this record. Inspect the linked resource in the
            desktop; no value is inferred here.
          </p>
        )}
    </>
  );
}
