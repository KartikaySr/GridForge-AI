import { Text } from 'react-native';
import { useSession } from '../session';
import { Button, Card, Page, styles } from '../components/ui';
export default function Facilities() {
  const { portfolio, edge, setEdge, busy, run, refresh } = useSession();
  return (
    <Page title="Your facilities">
      <Text style={styles.text}>
        Cloud receipt is historical evidence, not live plant health. Select a
        facility for assets, risk and reports.
      </Text>
      <Button
        title="Refresh facilities"
        disabled={busy}
        onPress={() => void run(() => refresh())}
      />
      {portfolio && (
        <Text style={styles.text}>
          Portfolio snapshot {portfolio.observed_at}. Cached access may change
          at synchronization.
        </Text>
      )}
      {portfolio?.facilities.length === 0 && (
        <Text style={styles.text}>
          No facilities assigned. Ask your administrator for access.
        </Text>
      )}
      {!portfolio && (
        <Text style={styles.text}>
          No portfolio loaded. Connect and refresh.
        </Text>
      )}
      {portfolio?.facilities.map((f) => (
        <Card key={f.edge_id}>
          <Text style={styles.text}>Facility {f.facility_id}</Text>
          <Text style={styles.text}>Edge {f.edge_id}</Text>
          <Text style={styles.text}>
            Last receipt: {f.last_received_at ?? 'None'} ·{' '}
            {f.enabled ? 'Enabled' : 'Disabled'}
          </Text>
          <Button
            title={edge === f.edge_id ? 'Selected facility' : 'Select facility'}
            disabled={edge === f.edge_id}
            onPress={() => setEdge(f.edge_id)}
          />
        </Card>
      ))}
    </Page>
  );
}
