import { useEffect, useState } from 'react';
import { Text } from 'react-native';
import type { PortalHistory } from '@gridforge/api-client';
import { client } from '../api';
import { useSession } from '../session';
import { Button, Page, styles } from './ui';
import EventCard from './EventCard';
export default function History({
  stream,
  title,
}: {
  stream: 'registry' | 'intelligence';
  title: string;
}) {
  const { session, edge, run, busy } = useSession();
  const [history, setHistory] = useState<PortalHistory | null>(null);
  const [before, setBefore] = useState<number | undefined>(),
    [revision, setRevision] = useState(0);
  useEffect(() => {
    setBefore(undefined);
    setHistory(null);
  }, [edge]);
  useEffect(() => {
    let active = true;
    setHistory(null);
    if (edge && session)
      void run(async () => {
        const result = await client(session.token).history(
          edge,
          stream,
          before,
        );
        if (active) setHistory(result);
      });
    return () => {
      active = false;
    };
    // run only wraps errors/loading; it is intentionally not a request dependency.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [edge, session, stream, before, revision]);
  return (
    <Page title={title}>
      <Text style={styles.text}>
        {stream === 'intelligence'
          ? 'Received forecast and risk evidence. No background push delivery or incident acknowledgement.'
          : 'Received asset/configuration history. Values may be stale.'}
      </Text>
      <Button
        title="Refresh newest"
        disabled={busy || !edge}
        onPress={() => {
          setBefore(undefined);
          setRevision((v) => v + 1);
        }}
      />
      {!edge && <Text style={styles.text}>Select a facility first.</Text>}
      {busy && <Text style={styles.text}>Loading evidence…</Text>}
      {history?.events.length === 0 && (
        <Text style={styles.text}>No synchronized records yet.</Text>
      )}
      {history?.edge_id === edge &&
        history.events.map((event) => (
          <EventCard key={event.event_id} event={event} />
        ))}
      {history?.next_before && (
        <Button
          title="Older records"
          disabled={busy}
          onPress={() => setBefore(history.next_before ?? undefined)}
        />
      )}
    </Page>
  );
}
