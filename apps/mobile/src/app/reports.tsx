import { useEffect, useState } from 'react';
import { Text, TextInput } from 'react-native';
import { randomUUID } from 'expo-crypto';
import { client, storageOwner } from '../api';
import { useSession } from '../session';
import type { PendingReport } from '../reports/outbox';
import { synchronizeReports } from '../reports/sync';
import {
  clearSynced,
  listReports,
  markReport,
  saveReport,
} from '../reports/storage';
import { Button, Card, Page, styles } from '../components/ui';
export default function Reports() {
  const { session, edge, run, busy } = useSession();
  const [reports, setReports] = useState<PendingReport[]>([]),
    [text, setText] = useState('');
  const owner = session ? storageOwner(session.identity.id) : '';
  async function reload() {
    setReports(await listReports(owner));
  }
  useEffect(() => {
    void run(reload);
  }, [owner]); // eslint-disable-line react-hooks/exhaustive-deps
  async function sync() {
    if (!session) return;
    try {
      await synchronizeReports(
        await listReports(owner),
        owner,
        client(session.token).report,
        markReport,
      );
    } finally {
      await reload();
    }
  }

  return (
    <Page title="Field reports">
      <Text style={styles.text}>
        Synthetic observations only; not verified production data. Pending notes
        persist offline. Synchronization is explicit and requires your current
        facility access.
      </Text>
      <Text style={styles.text}>
        Selected edge: {edge || 'Select a facility first'}
      </Text>
      <TextInput
        accessibilityLabel="Field observation"
        placeholder="Describe your observation"
        multiline
        maxLength={2000}
        style={[styles.input, { minHeight: 120 }]}
        value={text}
        onChangeText={setText}
      />
      <Button
        title="Save on this device"
        disabled={busy || !edge || !text.trim()}
        onPress={() =>
          void run(async () => {
            await saveReport({
              requestId: randomUUID(),
              userId: owner,
              facilityId: edge,
              text: text.trim(),
              state: 'PENDING',
            });
            setText('');
            await reload();
          })
        }
      />
      <Button
        title="Synchronize pending reports"
        disabled={busy || !reports.some((r) => r.state === 'PENDING')}
        onPress={() => void run(sync)}
      />
      <Button
        title="Remove synchronized local copies"
        disabled={busy || !reports.some((r) => r.state === 'SYNCED')}
        onPress={() =>
          void run(async () => {
            await clearSynced(owner);
            await reload();
          })
        }
      />
      {!reports.length && (
        <Text style={styles.text}>No local reports for this account.</Text>
      )}
      {reports.map((r) => (
        <Card key={r.requestId}>
          <Text style={styles.text}>
            {r.state} · {r.facilityId}
          </Text>
          <Text selectable style={styles.text}>
            {r.text}
          </Text>
          <Text selectable style={styles.text}>
            Request {r.requestId}
          </Text>
          {r.state === 'CONFLICT' && (
            <Text style={styles.text}>
              Conflicting replay: retained for administrator review; will not
              retry automatically.
            </Text>
          )}
        </Card>
      ))}
    </Page>
  );
}
