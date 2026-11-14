import { Text } from 'react-native';
import { useSession } from '../session';
import { Button, Page, styles } from '../components/ui';
export default function Account() {
  const { session, run, logout, busy } = useSession();
  return (
    <Page title="Account">
      <Text style={styles.text}>{session?.identity.username}</Text>
      <Text style={styles.text}>
        Session expires {session?.identity.expires_at}
      </Text>
      <Text style={styles.text}>
        Sign-out requires connectivity to confirm revocation. Pending reports
        stay on this device, isolated to this account and server. Sessions
        expire after one hour. Use only synthetic, non-sensitive field notes in
        this prototype.
      </Text>
      <Button
        title="Sign out"
        disabled={busy}
        onPress={() => void run(logout)}
      />
    </Page>
  );
}
