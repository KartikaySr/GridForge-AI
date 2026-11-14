import { useState } from 'react';
import { Text, TextInput } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useSession } from '../session';
import { Button, Page, styles } from './ui';
export default function SignIn() {
  const { ready, busy, run, login } = useSession();
  const [username, setUsername] = useState(''),
    [password, setPassword] = useState('');
  return (
    <SafeAreaView style={{ flex: 1 }}>
      <Page title="Field companion">
        <Text style={styles.text}>
          Review received facility evidence and record field observations. No
          equipment control or dispatch approvals.
        </Text>
        <Text style={styles.text}>Sign in with your provisioned account.</Text>
        <TextInput
          style={styles.input}
          accessibilityLabel="Username"
          placeholder="Username"
          autoCapitalize="none"
          autoComplete="username"
          maxLength={64}
          value={username}
          onChangeText={setUsername}
        />
        <TextInput
          style={styles.input}
          accessibilityLabel="Password"
          placeholder="Password"
          secureTextEntry
          autoComplete="current-password"
          maxLength={128}
          value={password}
          onChangeText={setPassword}
        />
        <Button
          title={ready ? 'Sign in' : 'Restoring session…'}
          disabled={
            !ready || busy || username.length < 3 || password.length < 12
          }
          onPress={() =>
            void run(async () => {
              await login(username, password);
              setPassword('');
            })
          }
        />
      </Page>
    </SafeAreaView>
  );
}
