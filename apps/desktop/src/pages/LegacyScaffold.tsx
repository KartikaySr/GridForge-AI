import React, { useEffect, useState } from 'react';
import {
  Activity,
  BrainCircuit,
  Factory,
  Gauge,
  IndianRupee,
  Radio,
  TriangleAlert,
  Zap,
} from 'lucide-react';
import { api } from '../lib/api';
import type {
  DashboardMetrics as Metrics,
  Asset,
  OptimizationProposal as Proposal,
} from '@gridforge/contracts';
const fallback: Metrics = {
  currentLoadKw: 8420,
  predictedPeakKw: 9180,
  thresholdKw: 9000,
  peakRiskPct: 78,
  todaySavingsInr: 12840,
  activeAlerts: 3,
  telemetryPerSecond: 5,
};
function Card({
  label,
  value,
  sub,
  icon,
}: {
  label: string;
  value: string;
  sub: string;
  icon: React.ReactNode;
}) {
  return (
    <div className="card">
      <div className="cardTop">
        <span>{label}</span>
        {icon}
      </div>
      <strong>{value}</strong>
      <small>{sub}</small>
    </div>
  );
}
export function LegacyScaffold() {
  const [m, setM] = useState(fallback);
  const [assets, setAssets] = useState<Asset[]>([]);
  const [p, setP] = useState<Proposal | null>(null);
  const [online, setOnline] = useState(false);
  useEffect(() => {
    const load = async () => {
      try {
        setM(await api<Metrics>('/api/v1/dashboard/metrics'));
        setAssets(await api<Asset[]>('/api/v1/assets'));
        setP(await api<Proposal>('/api/v1/optimization/current'));
        setOnline(true);
      } catch {
        setOnline(false);
      }
    };
    load();
    const id = setInterval(load, 3000);
    return () => clearInterval(id);
  }, []);
  return (
    <div className="app">
      <aside>
        <div className="brand">
          <Zap />
          GRIDFORGE <b>AI</b>
        </div>
        <div className="section">CONTROL</div>
        {[
          'Command Center',
          'Facilities',
          'Assets',
          'Telemetry',
          'OT Devices',
        ].map((x) => (
          <div
            key={x}
            className={'nav ' + (x === 'Command Center' ? 'active' : '')}
          >
            {x}
          </div>
        ))}
        <div className="section">INTELLIGENCE</div>
        {[
          'Energy & Tariffs',
          'Forecasting',
          'Optimization',
          'Dispatch',
          'Arbitrage',
          'AI Copilot',
        ].map((x) => (
          <div key={x} className="nav">
            {x}
          </div>
        ))}
        <div className="section">PLATFORM</div>
        {['Alerts', 'Integrations', 'Audit', 'Settings'].map((x) => (
          <div key={x} className="nav">
            {x}
          </div>
        ))}
      </aside>
      <main>
        <header>
          <div>
            <h1>Operational Command Center</h1>
            <p>Example Facility · Simulation Scaffold</p>
          </div>
          <div className={'pill ' + (online ? 'ok' : 'warn')}>
            <Radio size={15} />
            {online
              ? 'SIMULATED API CONNECTED'
              : 'OFFLINE / ILLUSTRATIVE VALUES'}
          </div>
        </header>
        <p className="simulationNotice" role="status">
          SIMULATION ONLY — Values may be stale. Forecast, risk, alerts,
          savings, asset data and proposal are illustrative. No verified savings
          or machine control.
        </p>
        <div className="pipeline">
          <span>TELEMETRY</span>→<span>FORECAST</span>→<span>RISK</span>→
          <span>CONSTRAINTS</span>→<span>OPTIMIZE</span>→<span>APPROVE</span>→
          <span>DISPATCH</span>→<span>VERIFY</span>
        </div>
        <section className="grid">
          <Card
            label="SIMULATED LOAD · MAY BE STALE"
            value={`${(m.currentLoadKw / 1000).toFixed(2)} MW`}
            sub={`Example threshold ${(m.thresholdKw / 1000).toFixed(2)} MW`}
            icon={<Gauge />}
          />
          <Card
            label="ILLUSTRATIVE FORECAST"
            value={`${(m.predictedPeakKw / 1000).toFixed(2)} MW`}
            sub={`${m.peakRiskPct}% illustrative risk score`}
            icon={<BrainCircuit />}
          />
          <Card
            label="ILLUSTRATIVE SAVINGS"
            value={`₹${m.todaySavingsInr.toLocaleString('en-IN')}`}
            sub="Synthetic amount · unverified"
            icon={<IndianRupee />}
          />
          <Card
            label="ILLUSTRATIVE ALERTS"
            value={`${m.activeAlerts}`}
            sub={`${m.telemetryPerSecond} asset slots · not throughput`}
            icon={<TriangleAlert />}
          />
        </section>
        <section className="columns">
          <div className="panel">
            <div className="panelTitle">
              <Activity />
              Illustrative Energy Profile · static chart
            </div>
            <div className="chart">
              <div className="threshold">EXAMPLE THRESHOLD</div>
              <svg viewBox="0 0 700 220" preserveAspectRatio="none">
                <polyline
                  points="0,165 80,155 150,160 220,135 290,145 360,100 430,115 500,70 570,90 640,55 700,78"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="4"
                />
              </svg>
            </div>
            <div className="legend">
              <span>Current {m.currentLoadKw} kW</span>
              <span>Forecast {m.predictedPeakKw} kW</span>
            </div>
          </div>
          <div className="panel">
            <div className="panelTitle">
              <Zap />
              Example Proposal · not constraint-evaluated
            </div>
            {p ? (
              <>
                <h2>{p.action}</h2>
                <p className="muted">
                  Asset {p.assetId} · {p.durationMinutes} min
                </p>
                <div className="decision">
                  <b>{p.reductionKw} kW</b>
                  <span>expected reduction</span>
                </div>
                <div className="decision">
                  <b>₹{p.expectedSavingsInr.toLocaleString('en-IN')}</b>
                  <span>illustrative savings</span>
                </div>
                <button disabled>Proposal review unavailable</button>
              </>
            ) : (
              <p className="muted">No active proposal.</p>
            )}
          </div>
        </section>
        <section className="panel">
          <div className="panelTitle">
            <Factory />
            Example Asset Flexibility · static data
          </div>
          <table>
            <thead>
              <tr>
                <th>Asset</th>
                <th>Line</th>
                <th>Load</th>
                <th>Flexible</th>
                <th>Criticality</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {assets.map((a) => (
                <tr key={a.id}>
                  <td>
                    <b>{a.name}</b>
                    <small>{a.type}</small>
                  </td>
                  <td>{a.line}</td>
                  <td>{a.currentLoadKw} kW</td>
                  <td>{a.flexibilityKw} kW</td>
                  <td>{a.criticality}</td>
                  <td>
                    <span className="status">● {a.status}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {!assets.length && (
            <p className="muted">
              Start the FastAPI backend to load static example assets.
            </p>
          )}
        </section>
      </main>
    </div>
  );
}
