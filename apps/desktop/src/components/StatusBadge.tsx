export function StatusBadge({ state }: { state: string }) {
  return (
    <span className={`statusBadge status-${state.toLowerCase()}`}>
      <span aria-hidden="true">●</span> {state.replaceAll('_', ' ')}
    </span>
  );
}
