import { useState } from 'react';
import { Text } from 'react-native';
import type { PortalEvent } from '@gridforge/api-client';
import { Button, Card, styles } from './ui';
function object(value: unknown): Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}
export default function EventCard({ event }: { event: PortalEvent }) {
  const [expanded, setExpanded] = useState(false);
  const payload = object(event.body.payload);
  const data = { ...event.body, ...payload, ...object(payload.entity) };
  const fields = [
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
    'threshold_kw',
    'predicted_peak_kw',
    'model_version',
    'reason',
  ];
  return (
    <Card>
      <Text accessibilityRole="header" style={styles.text}>
        {event.event_type} · #{event.sequence}
      </Text>
      {fields
        .filter((key) =>
          ['string', 'number', 'boolean'].includes(typeof data[key]),
        )
        .map((key) => (
          <Text key={key} style={styles.text}>
            {key.replaceAll('_', ' ')} · {String(data[key])}
          </Text>
        ))}
      <Text style={styles.text}>
        Source {String(event.body.occurred_at ?? 'Unavailable')}
      </Text>
      <Text style={styles.text}>Received {event.received_at}</Text>
      <Button
        title={expanded ? 'Hide evidence' : 'Inspect evidence'}
        onPress={() => setExpanded(!expanded)}
      />
      {expanded && (
        <Text selectable style={styles.text}>
          {JSON.stringify(event.body, null, 2)}
        </Text>
      )}
    </Card>
  );
}
