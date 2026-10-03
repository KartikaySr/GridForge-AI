import { Component, type ReactNode } from 'react';
export class ErrorBoundary extends Component<
  { children: ReactNode },
  { failed: boolean }
> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    if (this.state.failed)
      return (
        <main className="fatal" role="alert">
          <span className="eyebrow">GRIDFORGE · SIMULATION</span>
          <h1>The desktop view could not render</h1>
          <p>
            The runtime is managed independently. Reload the view to reconnect,
            or close the desktop to stop its runtime.
          </p>
          <button onClick={() => window.location.reload()}>Reload view</button>
        </main>
      );
    return this.props.children;
  }
}
