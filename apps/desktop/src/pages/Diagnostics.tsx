import { useState } from 'react';
import { runtimeBridge } from '../lib/runtime';
export function Diagnostics({ desktop }: { desktop: boolean }) {
  const [report, setReport] = useState('');
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function generate() {
    setPending(true);
    setError(null);
    setReport('');
    try {
      setReport(JSON.stringify(await runtimeBridge.diagnostics(), null, 2));
    } catch {
      setError(
        'Diagnostics could not be read. The desktop supervisor may be unavailable.',
      );
    } finally {
      setPending(false);
    }
  }
  return (
    <section className="surface">
      <span className="eyebrow">LOCAL TROUBLESHOOTING</span>
      <h2>Diagnostic snapshot</h2>
      <p className="muted">
        Includes current lifecycle, component health and bounded request logs.
        Credentials, request payloads, file paths and environment variables are
        excluded. This snapshot is not a durable audit trail.
      </p>
      <button disabled={!desktop || pending} onClick={() => void generate()}>
        {pending ? 'Reading diagnostics…' : 'Generate diagnostic report'}
      </button>
      {!desktop && (
        <p className="muted">Diagnostics require the native desktop.</p>
      )}
      {error && (
        <p role="alert" className="errorText">
          {error}
        </p>
      )}
      {report && (
        <>
          <label htmlFor="diagnostic-report">
            Redacted JSON · select text to copy
          </label>
          <textarea
            id="diagnostic-report"
            className="diagnosticReport"
            readOnly
            value={report}
            spellCheck={false}
          />
          <p className="muted">
            This report captures one moment. Generate it again for current
            state.
          </p>
        </>
      )}
    </section>
  );
}
