import type { Preferences } from '../lib/preferences';
export function Settings({
  preferences,
  change,
  notice,
}: {
  preferences: Preferences;
  change: (next: Preferences) => void;
  notice: string | null;
}) {
  return (
    <section className="surface settings">
      <span className="eyebrow">THIS DESKTOP</span>
      <h2>Display preferences</h2>
      <p className="muted">
        Preferences affect presentation only. Facility identity, permissions and
        operational policies are not configured here.
      </p>
      <label htmlFor="theme">Appearance</label>
      <select
        id="theme"
        value={preferences.theme}
        onChange={(event) =>
          change({
            ...preferences,
            theme: event.target.value as Preferences['theme'],
          })
        }
      >
        <option value="dark">Dark</option>
        <option value="light">Light</option>
      </select>
      <label className="checkLabel">
        <input
          type="checkbox"
          checked={preferences.compact}
          onChange={(event) =>
            change({ ...preferences, compact: event.target.checked })
          }
        />
        Compact information density
      </label>
      {notice && <p role="status">{notice}</p>}
      <div className="settingsNote">
        <strong>Simulation is enforced by the runtime.</strong>
        <p>
          No live-control mode or writable OT configuration is available.
          Account sign-in, facility setup, secure persistent credentials and
          update distribution will arrive in later phases.
        </p>
      </div>
    </section>
  );
}
