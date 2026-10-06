import { Reports } from './pages/Reports';
import { IdentityGate } from './components/IdentityGate';
import { Demonstration } from './pages/Demonstration';
import { Security } from './pages/Security';
import { useEffect, useState } from 'react';
import { Activity, ChevronRight, Command, Search, Zap } from 'lucide-react';
import { StatusBadge } from './components/StatusBadge';
import { CommandCenter } from './pages/CommandCenter';
import { SystemHealth } from './pages/SystemHealth';
import { Settings } from './pages/Settings';
import { Registry } from './pages/Registry';
import { Dispatch } from './pages/Dispatch';
import { Finance } from './pages/Finance';
import { Copilot } from './pages/Copilot';
import { SyncCenter } from './pages/SyncCenter';
import { Optimization } from './pages/Optimization';
import { Forecasting } from './pages/Forecasting';
import { Telemetry } from './pages/Telemetry';
import { Diagnostics } from './pages/Diagnostics';
import { useRuntime } from './lib/useRuntime';
import { hasFreshHealth } from './lib/runtime';
import {
  readPreferences,
  savePreferences,
  type Preferences,
} from './lib/preferences';

const groups = [
  {
    name: 'WORKSPACE',
    items: [
      ['Command Center', 1],
      ['Facilities', 3],
      ['Assets', 3],
      ['Telemetry', 2],
      ['OT Devices', 3],
    ],
  },
  {
    name: 'INTELLIGENCE',
    items: [
      ['Energy & Tariffs', 7],
      ['Forecasting & Risk', 4],
      ['Constraints & Optimization', 5],
      ['Dispatch', 6],
      ['Verification & Savings', 7],
      ['AI Copilot', 9],
      ['Production & Reports', 12],
    ],
  },
  {
    name: 'PLATFORM',
    items: [
      ['Integrated Demonstration', 11],
      ['Security & Operations', 10],
      ['Sync Center', 8],
      ['System Health', 1],
      ['Diagnostics', 1],
      ['Settings', 1],
    ],
  },
] as const;
const phaseFor = (name: string) =>
  groups
    .flatMap((group) => [...group.items])
    .find((item) => item[0] === name)?.[1];

export function App() {
  const runtime = useRuntime();
  const [page, setPage] = useState('Command Center');
  const [search, setSearch] = useState('');
  const [preferences, setPreferences] = useState(readPreferences);
  const [notice, setNotice] = useState<string | null>(null);
  useEffect(() => {
    document.documentElement.dataset.theme = preferences.theme;
  }, [preferences.theme]);
  function change(next: Preferences) {
    setPreferences(next);
    setNotice(
      savePreferences(next)
        ? 'Display preferences saved on this device.'
        : 'Storage unavailable. Preferences apply for this session only.',
    );
  }
  const fresh = hasFreshHealth(runtime.snapshot);
  const state =
    runtime.snapshot.state === 'READY' && !fresh
      ? 'STALE'
      : runtime.snapshot.state;
  return (
    <IdentityGate desktop={runtime.desktop}>
      <div className={`desktopShell ${preferences.compact ? 'compact' : ''}`}>
        <a className="skipLink" href="#main-content">
          Skip navigation
        </a>
        <aside className="sidebar">
          <div className="brand">
            <Zap size={25} />
            <div>
              GRIDFORGE <b>AI</b>
              <small>DESKTOP / EDGE</small>
            </div>
          </div>
          <label className="navSearch">
            <Search size={15} />
            <input
              aria-label="Find a module"
              placeholder="Find a module"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          </label>
          <nav aria-label="Main navigation">
            {groups.map((group) => (
              <div className="navGroup" key={group.name}>
                <h2>{group.name}</h2>
                {group.items
                  .filter(([name]) =>
                    name.toLowerCase().includes(search.toLowerCase()),
                  )
                  .map(([name, phase]) => (
                    <button
                      key={name}
                      aria-current={page === name ? 'page' : undefined}
                      onClick={() => {
                        setPage(name);
                        setSearch('');
                      }}
                    >
                      <span>{name}</span>
                      {phase > 12 && <span className="phaseTag">P{phase}</span>}
                      {page === name && <ChevronRight size={14} />}
                    </button>
                  ))}
              </div>
            ))}
          </nav>
          <div className="sidebarFooter">
            <ShieldLabel />
            <small>No operational authority provisioned</small>
          </div>
        </aside>
        <div className="workspace">
          <header className="commandBar">
            <div className="facilityContext">
              <span className="contextLabel">FACILITY</span>
              <strong>
                {runtime.snapshot.telemetry
                  ? `${runtime.snapshot.telemetry.facility_name} · ${runtime.snapshot.telemetry.timezone}`
                  : 'No facility configured'}
              </strong>
            </div>
            <div className="topStatuses">
              <span className="simulationPill">SIMULATION</span>
              <span>
                Cloud{' '}
                <b>
                  {runtime.snapshot.health?.cloud_state ?? 'Not configured'}
                </b>
              </span>
              <span>
                Sync{' '}
                <b>{runtime.snapshot.health?.sync_state ?? 'Not configured'}</b>
              </span>
            </div>
          </header>
          <main id="main-content" tabIndex={-1}>
            <div className="pageHeading">
              <div>
                <div className="breadcrumb">Workspace / {page}</div>
                <h1>{page}</h1>
                <p>
                  {page === 'Command Center'
                    ? 'Local execution, connection state and platform readiness.'
                    : 'GridForge facility-local control plane · Simulation'}
                </p>
              </div>
              <StatusBadge state={state} />
            </div>
            <div
              className={`runtimeBanner ${fresh ? 'connected' : ''}`}
              role="status"
            >
              <Activity size={17} />
              <span>
                <strong>
                  {fresh
                    ? 'Local runtime connected.'
                    : runtime.desktop
                      ? 'Local runtime needs attention.'
                      : 'Browser preview.'}
                </strong>{' '}
                {fresh
                  ? 'Local services are ready. Simulated actions require valid data, constraints and operator authorization.'
                  : runtime.snapshot.message}
              </span>
              {page !== 'System Health' && (
                <button
                  className="textButton"
                  onClick={() => setPage('System Health')}
                >
                  View health
                </button>
              )}
            </div>
            {page === 'Command Center' ? (
              <CommandCenter
                snapshot={runtime.snapshot}
                openHealth={() => setPage('System Health')}
              />
            ) : ['Facilities', 'Assets', 'OT Devices'].includes(page) ? (
              <Registry key={page} page={page} desktop={runtime.desktop} />
            ) : page === 'Telemetry' ? (
              <Telemetry
                snapshot={runtime.snapshot}
                desktop={runtime.desktop}
              />
            ) : page === 'Forecasting & Risk' ? (
              <Forecasting desktop={runtime.desktop} />
            ) : page === 'Constraints & Optimization' ? (
              <Optimization desktop={runtime.desktop} />
            ) : page === 'Dispatch' ? (
              <Dispatch desktop={runtime.desktop} />
            ) : page === 'Energy & Tariffs' ||
              page === 'Verification & Savings' ? (
              <Finance desktop={runtime.desktop} page={page} />
            ) : page === 'Production & Reports' ? (
              <Reports desktop={runtime.desktop} />
            ) : page === 'AI Copilot' ? (
              <Copilot desktop={runtime.desktop} />
            ) : page === 'Integrated Demonstration' ? (
              <Demonstration desktop={runtime.desktop} />
            ) : page === 'Security & Operations' ? (
              <Security desktop={runtime.desktop} />
            ) : page === 'Sync Center' ? (
              <SyncCenter desktop={runtime.desktop} />
            ) : page === 'System Health' ? (
              <SystemHealth {...runtime} />
            ) : page === 'Settings' ? (
              <Settings
                preferences={preferences}
                change={change}
                notice={notice}
              />
            ) : page === 'Diagnostics' ? (
              <Diagnostics desktop={runtime.desktop} />
            ) : (
              <section className="surface deferred">
                <Command size={30} />
                <span className="eyebrow">
                  SCHEDULED FOR PHASE {phaseFor(page)}
                </span>
                <h2>{page} is not implemented yet</h2>
                <p>
                  This shell reserves the platform navigation. No data, control
                  capability or completion is implied.
                </p>
                <button
                  className="secondary"
                  onClick={() => setPage('Command Center')}
                >
                  Return to Command Center
                </button>
              </section>
            )}
            <footer className="workspaceFooter">
              <span>SIMULATION ONLY · No physical actuation</span>
              <span>GridForge Desktop / Phase 11</span>
            </footer>
          </main>
        </div>
      </div>
    </IdentityGate>
  );
}
function ShieldLabel() {
  return <strong>Local desktop session</strong>;
}
