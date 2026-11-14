import {
  createContext,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import { AppState } from 'react-native';
import * as SecureStore from 'expo-secure-store';
import type { MobileSession, Portfolio } from '@gridforge/api-client';
import { ApiError, client, storageOwner } from './api';
import { cachePortfolio, readPortfolio } from './reports/storage';

const SessionContext = createContext<ReturnType<typeof useSessionState> | null>(
  null,
);
const key = 'gridforge.mobile.session.v1';
function useSessionState() {
  const [session, setSession] = useState<MobileSession | null>(null);
  const [ready, setReady] = useState(false),
    [busy, setBusy] = useState(false),
    [notice, setNotice] = useState('');
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null),
    [edge, setEdge] = useState('');
  const epoch = useRef(0);
  const pending = useRef(0);
  async function clear() {
    epoch.current++;
    setSession(null);
    setPortfolio(null);
    setEdge('');
    await SecureStore.deleteItemAsync(key);
  }
  async function run(action: () => Promise<void>) {
    pending.current++;
    setBusy(true);
    setNotice('');
    try {
      await action();
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        await clear().catch(() => undefined);
        setNotice(
          'Session ended. Sign in again. Your pending reports remain on this device.',
        );
      } else
        setNotice(
          error instanceof ApiError
            ? `Request rejected (${error.status}). Check your facility access.`
            : 'Service or device storage unavailable. Check configuration/connectivity and retry.',
        );
    } finally {
      pending.current--;
      setBusy(pending.current > 0);
    }
  }
  async function refresh(current = session) {
    if (!current) return;
    const version = epoch.current;
    const data = await client(current.token).portfolio();
    if (version !== epoch.current) return;
    await cachePortfolio(storageOwner(current.identity.id), data);
    if (version !== epoch.current) return;
    setPortfolio(data);
    setEdge((old) =>
      data.facilities.some((f) => f.edge_id === old)
        ? old
        : (data.facilities[0]?.edge_id ?? ''),
    );
  }
  useEffect(() => {
    void run(async () => {
      const stored = await SecureStore.getItemAsync(key);
      if (!stored) return;
      const saved = JSON.parse(stored) as {
        owner: string;
        session: MobileSession;
      };
      if (
        saved.owner !== storageOwner(saved.session.identity.id) ||
        Date.parse(saved.session.identity.expires_at) <= Date.now()
      )
        return clear();
      setSession(saved.session);
      const cached = await readPortfolio(saved.owner);
      setPortfolio(cached);
      setEdge(cached?.facilities[0]?.edge_id ?? '');
      await refresh(saved.session);
    }).finally(() => setReady(true));
    // Restore once; later requests use the current session.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  useEffect(() => {
    function expire() {
      if (session && Date.parse(session.identity.expires_at) <= Date.now())
        void clear()
          .catch(() => undefined)
          .then(() => setNotice('Session expired. Sign in again.'));
    }
    const timer = setInterval(expire, 1000);
    const subscription = AppState.addEventListener('change', expire);
    return () => {
      clearInterval(timer);
      subscription.remove();
    };
  }, [session]);
  async function login(username: string, password: string) {
    const next = await client().login(username, password);
    await SecureStore.setItemAsync(
      key,
      JSON.stringify({ owner: storageOwner(next.identity.id), session: next }),
      { keychainAccessible: SecureStore.WHEN_UNLOCKED_THIS_DEVICE_ONLY },
    );
    epoch.current++;
    setSession(next);
    await refresh(next);
  }
  async function logout() {
    if (session) await client(session.token).logout();
    await clear();
    setNotice('Signed out. Pending reports remain isolated to your account.');
  }
  return {
    session,
    ready,
    busy,
    notice,
    portfolio,
    edge,
    setEdge,
    run,
    refresh,
    login,
    logout,
  };
}
export function SessionProvider({ children }: { children: ReactNode }) {
  return (
    <SessionContext.Provider value={useSessionState()}>
      {children}
    </SessionContext.Provider>
  );
}
export function useSession() {
  const value = useContext(SessionContext);
  if (!value) throw new Error('Session provider required');
  return value;
}
