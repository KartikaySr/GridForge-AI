import { useCallback, useEffect, useState } from 'react';
import {
  initialRuntime,
  isDesktop,
  runtimeBridge,
  unavailable,
  type RuntimeSnapshot,
} from './runtime';

export function useRuntime() {
  const [desktop] = useState(isDesktop);
  const [snapshot, setSnapshot] = useState<RuntimeSnapshot>(
    desktop ? initialRuntime : unavailable,
  );
  const [pending, setPending] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  useEffect(() => {
    if (!desktop) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try {
        const next = await runtimeBridge.status();
        if (!cancelled) setSnapshot(next);
      } catch {
        if (!cancelled)
          setSnapshot((previous) => ({
            ...previous,
            state: 'FAILED',
            health: null,
            busy: false,
            message:
              'Desktop supervisor unavailable. Close and reopen the application.',
          }));
      }
      if (!cancelled) timer = setTimeout(poll, 1000);
    };
    void poll();
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [desktop]);
  const act = useCallback(
    async (action: 'restart' | 'stop') => {
      if (!desktop || pending || snapshot.busy) return;
      setPending(true);
      setActionError(null);
      try {
        await runtimeBridge[action]();
        setSnapshot(await runtimeBridge.status());
      } catch {
        setActionError(
          'The lifecycle request was not accepted. Wait for the current operation or retry.',
        );
      } finally {
        setPending(false);
      }
    },
    [desktop, pending, snapshot.busy],
  );
  return {
    desktop,
    snapshot,
    pending: pending || snapshot.busy,
    actionError,
    act,
  };
}
