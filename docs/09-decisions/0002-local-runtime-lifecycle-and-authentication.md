# ADR 0002: Native supervision and private local sessions

Status: implemented in Phase 1; operational domain capabilities remain deferred.

## Decision

The Tauri host owns the Python child process and its lifetime. The child runs the independent
edge.runtime composition root; it does not import or mount apps/api's legacy scaffold.
React invokes four scoped native commands: runtime_status, runtime_restart, runtime_stop,
and runtime_diagnostics. It cannot invoke a generic shell command, select an executable,
choose an HTTP destination, read arbitrary files or receive the session credential.

The native host generates a random 256-bit session credential and UUID per launch. A private
stdin pipe carries this bootstrap envelope to Python. Credentials are never command-line
arguments, inherited environment variables, WebView state, localStorage or diagnostic output.
Python binds 127.0.0.1 on an OS-selected port and announces its instance ID and port only after
Uvicorn startup. Native health requests authenticate with the private credential and validate
instance identity. HTTP redirects and proxy discovery are disabled. A browser Origin is denied
even if it presents a credential; this interface is native-to-runtime, not browser-to-runtime.

The runtime exits when its private pipe closes (including native parent death). Normal stop
requests use the pipe and allow three seconds before native forced termination and reaping.
Startup handshake timeout is ten seconds; native HTTP timeout is 800ms; health checks occur
approximately once a second without overlap. Three successive health failures stop the child
and expose FAILED. Unexpected process exit is immediately visible on the supervision loop.
Restart is explicit, rotates identity/credentials, and serializes lifecycle requests. There is
no unlimited automatic restart loop.

Tauri AppManifest and a main-window capability allow only those four commands. No filesystem,
shell, SQL, updater, HTTP or remote-origin plugin capabilities are granted. CSP blocks external
content; development CSP additionally permits the local Vite HMR WebSocket. A native frontend
connection and lifecycle changes emit fixed structured diagnostic events without credentials.

The local API contract is exported from FastAPI/Pydantic and generated into TypeScript.
Desktop lifecycle DTOs remain desktop-specific. The generated API package has no native
implementation imports. Runtime request logs are a bounded 100-record in-memory ring; native
lifecycle history is bounded to 64 entries. These are diagnostic records, not durable audit.

## Readiness and identity

READY means the authenticated shell API is responding. operational_ready is always false;
readiness_scope is shell-only. Facility identity is absent, cloud is not configured, and storage,
telemetry and synchronization are not implemented. A local process session is not an OIDC user
or an authorization grant for operational actions. OS credential storage is unnecessary for
this ephemeral token; persistent user credentials must use the later secure identity design.

## Development and distribution boundary

Phase 1 debug builds execute the workspace's .venv Python using the compiled workspace path.
They require the source checkout and its environment. Release builds fail closed with an
explicit unavailable-runtime status until a bundled runtime is designed in Phase 10. They do
not fall back to a shell or arbitrary system Python. Installer creation, signing, updates,
portable Python bundling, and Windows/Linux runtime validation remain deferred.

The initial macOS toolchain was installed under an isolated temporary path during development.
After temporary-directory cleanup during a session pause, it was restored under ignored
.tooling/cargo and .tooling/rustup. Native npm scripts detect that optional local installation;
other checkouts use normal rustup. No user shell configuration was changed by this phase.

## Consequences

Native Rust owns lifecycle and transport only. Python owns health and future domain composition.
The UI has no direct OT or database access. A same-user privileged process is outside this
local session's protection boundary; the design does not claim protection from OS compromise.
Port-level denial of service remains possible; timeouts, concurrency limits and visible failure
bound it but do not replace enterprise hardening. Operational authorization remains future work.

References: [Tauri capabilities](https://v2.tauri.app/security/capabilities/) and
[Tauri Rust commands](https://v2.tauri.app/develop/calling-rust/).
