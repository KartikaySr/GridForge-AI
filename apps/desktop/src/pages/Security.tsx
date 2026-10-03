import { useEffect, useState } from 'react';
import type {
  AuditSnapshot,
  IdentityStatus,
  LocalUser,
  OperationsSnapshot,
  UserWrite,
} from '@gridforge/api-client';
import { runtimeBridge } from '../lib/runtime';

const roles: UserWrite['role'][] = [
  'SUPER_ADMIN',
  'ORG_ADMIN',
  'FACILITY_MANAGER',
  'ENERGY_MANAGER',
  'OPERATOR',
  'OT_ENGINEER',
  'ANALYST',
  'VIEWER',
];
export function Security({ desktop }: { desktop: boolean }) {
  const [identity, setIdentity] = useState<IdentityStatus | null>(null);
  const [users, setUsers] = useState<LocalUser[]>([]);
  const [audit, setAudit] = useState<AuditSnapshot | null>(null);
  const [metrics, setMetrics] = useState<OperationsSnapshot | null>(null);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [role, setRole] = useState<UserWrite['role']>('VIEWER');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (!desktop) return;
    let active = true;
    void (async () => {
      try {
        const current = await runtimeBridge.identity();
        const [nextUsers, nextAudit, nextMetrics] = await Promise.all([
          current.permissions.includes('user.manage')
            ? runtimeBridge.users()
            : [],
          current.permissions.includes('audit.read')
            ? runtimeBridge.audit()
            : null,
          runtimeBridge.metrics(),
        ]);
        if (active) {
          setIdentity(current);
          setUsers(nextUsers);
          setAudit(nextAudit);
          setMetrics(nextMetrics);
        }
      } catch {
        if (active)
          setNotice('Security information is unavailable for this session.');
      }
    })();
    return () => {
      active = false;
    };
  }, [desktop]);
  if (!desktop)
    return (
      <section className="surface">
        <h2>Local identity and operations</h2>
        <p>Open the native desktop to manage this installation.</p>
      </section>
    );
  return (
    <div className="securityGrid">
      <section className="surface">
        <h2>Identity & access</h2>
        <p>
          Role changes revoke existing sessions immediately. Every role remains
          scoped to this installation’s organization and facility.
        </p>
        {identity?.permissions.includes('user.manage') && (
          <>
            <form
              onSubmit={async (event) => {
                event.preventDefault();
                setBusy(true);
                setNotice('');
                try {
                  await runtimeBridge.createUser({ username, password, role });
                  setPassword('');
                  setUsername('');
                  setUsers(await runtimeBridge.users());
                  setNotice('Account created.');
                } catch {
                  setNotice(
                    'Account creation rejected. Check username, password length and permissions.',
                  );
                } finally {
                  setBusy(false);
                }
              }}
            >
              <label>
                New username
                <input
                  required
                  minLength={3}
                  maxLength={50}
                  pattern="[a-zA-Z0-9_.-]+"
                  value={username}
                  onChange={(event) => setUsername(event.target.value)}
                />
              </label>
              <label>
                Initial password
                <input
                  required
                  type="password"
                  autoComplete="new-password"
                  minLength={12}
                  maxLength={128}
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                />
              </label>
              <label>
                Role
                <select
                  value={role}
                  onChange={(event) =>
                    setRole(event.target.value as UserWrite['role'])
                  }
                >
                  {roles.map((value) => (
                    <option key={value}>{value}</option>
                  ))}
                </select>
              </label>
              <button disabled={busy}>Create account</button>
            </form>
            <ul>
              {users.map((user) => (
                <li key={user.id}>
                  <strong>{user.username}</strong> · {user.role} ·{' '}
                  {user.enabled ? 'Enabled' : 'Disabled'}
                  <select
                    aria-label={`Role for ${user.username}`}
                    value={user.role}
                    disabled={busy}
                    onChange={async (event) => {
                      setBusy(true);
                      try {
                        await runtimeBridge.changeUser({
                          user_id: user.id,
                          role: event.target.value as UserWrite['role'],
                          enabled: user.enabled,
                          expected_revision: user.revision,
                        });
                        setUsers(await runtimeBridge.users());
                      } catch {
                        setNotice(
                          'Role change rejected. The final administrator must remain enabled.',
                        );
                      } finally {
                        setBusy(false);
                      }
                    }}
                  >
                    {roles.map((value) => (
                      <option key={value}>{value}</option>
                    ))}
                  </select>
                  <button
                    disabled={busy}
                    onClick={async () => {
                      setBusy(true);
                      try {
                        await runtimeBridge.changeUser({
                          user_id: user.id,
                          role: user.role,
                          enabled: !user.enabled,
                          expected_revision: user.revision,
                        });
                        setUsers(await runtimeBridge.users());
                      } catch {
                        setNotice(
                          'Account change rejected. Refresh and check administrator access.',
                        );
                      } finally {
                        setBusy(false);
                      }
                    }}
                  >
                    {user.enabled ? 'Disable' : 'Enable'}
                  </button>
                </li>
              ))}
            </ul>
          </>
        )}
        <p role="status">{notice}</p>
      </section>
      <section className="surface">
        <h2>Operations</h2>
        <p>
          Schema {metrics?.schema_version ?? '—'} · Audit integrity{' '}
          {metrics ? (metrics.audit_integrity_ok ? 'Valid' : 'FAILED') : '—'}
        </p>
        {metrics && (
          <dl>
            {Object.entries(metrics.counters).map(([key, value]) => (
              <div key={key}>
                <dt>{key.replaceAll('_', ' ')}</dt>
                <dd>{value}</dd>
              </div>
            ))}
          </dl>
        )}
        {identity?.permissions.includes('system.diagnostics') && (
          <button
            onClick={async () => {
              try {
                const bundle = await runtimeBridge.bundle();
                await navigator.clipboard.writeText(
                  JSON.stringify(bundle, null, 2),
                );
                setNotice('Redacted diagnostic bundle copied.');
              } catch {
                setNotice('Unable to copy diagnostics.');
              }
            }}
          >
            Copy diagnostics bundle
          </button>
        )}
      </section>
      {audit && (
        <section className="surface">
          <h2>Audit trail</h2>
          <p>
            {audit.count} records · Chain{' '}
            {audit.integrity_ok ? 'verified' : 'FAILED'}. First 100 records
            shown.
          </p>
          <ol>
            {audit.rows.map((row) => (
              <li key={row.event_id}>
                <time>{new Date(row.occurred_at).toLocaleString()}</time> ·{' '}
                {row.action} · {row.outcome}
                <small> Trace {row.correlation_id}</small>
              </li>
            ))}
          </ol>
        </section>
      )}
    </div>
  );
}
