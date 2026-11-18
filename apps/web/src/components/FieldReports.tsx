import { useEffect, useState } from 'react';
import type { FieldReportHistory } from '@gridforge/api-client';
import { api } from '../api';
export function FieldReports({
  edge,
  revision,
  onError,
}: {
  edge: string;
  revision: number;
  onError: (error: unknown) => void;
}) {
  const [failed, setFailed] = useState(false);
  const [data, setData] = useState<FieldReportHistory | null>(null);
  useEffect(() => {
    let active = true;
    setData(null);
    setFailed(false);
    if (edge)
      void api
        .reports(edge)
        .then((value) => {
          if (active) setData(value);
        })
        .catch((error) => {
          if (active) {
            setFailed(true);
            onError(error);
          }
        });
    return () => {
      active = false;
    };
  }, [edge, revision, onError]);
  if (!edge)
    return <p>Select a facility to see your synchronized field reports.</p>;
  return (
    <div>
      <p>
        Your latest 100 field observations across mobile sessions. These are
        operator notes.
      </p>
      {!data && !failed && <p role="status">Loading reports…</p>}
      {data?.reports.length === 0 && <p>No synchronized field reports yet.</p>}
      {data?.reports.map((report) => (
        <article className="eventCard" key={report.request_id}>
          <h2>Field observation</h2>
          <p>{report.text}</p>
          <p className="timestamps">
            Received {report.received_at} · Request {report.request_id}
          </p>
        </article>
      ))}
    </div>
  );
}
