import { Tabs } from 'expo-router';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { SessionProvider, useSession } from '../session';
import SignIn from '../components/SignIn';
function Navigation() {
  const { session } = useSession();
  if (!session) return <SignIn />;
  return (
    <Tabs
      screenOptions={{
        headerStyle: { backgroundColor: '#123d2e' },
        headerTintColor: '#fff',
        tabBarActiveTintColor: '#194e3e',
      }}
    >
      <Tabs.Screen name="index" options={{ title: 'Facilities' }} />
      <Tabs.Screen name="assets" options={{ title: 'Assets' }} />
      <Tabs.Screen name="alerts" options={{ title: 'Risk alerts' }} />
      <Tabs.Screen name="reports" options={{ title: 'Reports' }} />
      <Tabs.Screen name="account" options={{ title: 'Account' }} />
    </Tabs>
  );
}
export default function Layout() {
  return (
    <SafeAreaProvider>
      <SessionProvider>
        <Navigation />
      </SessionProvider>
    </SafeAreaProvider>
  );
}
