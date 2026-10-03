import { useEffect, useState, type ReactNode } from 'react';
import type { IdentityStatus } from '@gridforge/api-client';
import { runtimeBridge } from '../lib/runtime';

export function IdentityGate({
  desktop,
  children,
}: {
  desktop: boolean;
  children: ReactNode;
}) {
  const [identity, setIdentity] = useState<IdentityStatus | null>(null);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (!desktop) return;
    let active = true;
    const refresh = () =>
      runtimeBridge
        .identity()
        .then((value) => {
          if (active) setIdentity(value);
        })
        .catch(() => {
          if (active) setIdentity(null);
        });
    void refresh();
    const timer = setInterval(() => {
      void refresh();
    }, 2000);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [desktop]);
  if (!desktop) return children;
  if (!identity?.authenticated)
    return (
      <main className="identityGate">
        <section className="surface">
          <span className="eyebrow">GRIDFORGE AI · SIMULATION</span>
          <h1>
            {identity?.setup_required
              ? 'Create your local administrator'
              : 'Sign in to this facility'}
          </h1>
          <p>
            Accounts apply to this edge installation. No physical equipment can
            be controlled.
          </p>
          {!identity ? (
            <p role="status">Waiting for the local runtime…</p>
          ) : (
            <form
              onSubmit={async (event) => {
                event.preventDefault();
                setBusy(true);
                setError('');
                try {
                  setIdentity(
                    await runtimeBridge.signIn(
                      identity.setup_required,
                      username,
                      password,
                    ),
                  );
                  setPassword('');
                } catch {
                  setError(
                    'Sign-in failed. Check credentials or wait a minute after repeated attempts.',
                  );
                } finally {
                  setBusy(false);
                }
              }}
            >
              <label>
                Username
                <input
                  required
                  minLength={3}
                  maxLength={50}
                  pattern="[a-zA-Z0-9_.-]+"
                  autoComplete="username"
                  value={username}
                  onChange={(event) => setUsername(event.target.value)}
                />
              </label>
              <label>
                Password
                <input
                  required
                  type="password"
                  minLength={12}
                  maxLength={128}
                  autoComplete={
                    identity.setup_required
                      ? 'new-password'
                      : 'current-password'
                  }
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                />
              </label>
              <button disabled={busy}>
                {busy
                  ? 'Checking…'
                  : identity.setup_required
                    ? 'Create administrator'
                    : 'Sign in'}
              </button>
            </form>
          )}
          {error && <p role="alert">{error}</p>}
        </section>
      </main>
    );
  return (
    <>
      <div className="identityBar">
        <span>
          {identity.user?.username} · {identity.user?.role}
        </span>
        <button
          disabled={busy}
          onClick={async () => {
            setBusy(true);
            setError('');
            try {
              setIdentity(await runtimeBridge.signOut());
            } catch {
              setError('Sign-out failed. Retry or close the desktop.');
            } finally {
              setBusy(false);
            }
          }}
        >
          Sign out
        </button>
        {error && <span role="alert">{error}</span>}
      </div>
      {children}
    </>
  );
}
