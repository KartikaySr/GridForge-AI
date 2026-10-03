# Development and validation

## Phase 4 forecast/risk workflow

Open the native desktop and let the normal simulator collect five sufficiently complete UTC
minute bins (about five to six minutes from an empty/gapped store). In Forecasting & Risk,
inspect the baseline curve, five input means, coverage, model version and evidence digests.
No configured simulation demand threshold means risk UNKNOWN even when the forecast is ready.
Set an illustrative threshold in Facilities → facility record; no real safety/utility meaning
is attached. For example, a threshold below the displayed forecast opens a simulated breach.

To exercise lifecycle at a fixed threshold, use Telemetry's spike scenario until the rolling
mean crosses it, then normal until a complete fresh forecast falls below it. Bad/stale/disconnected
scenarios suppress current forecasting and cannot resolve an existing risk. Recovery may require
five clean minute bins. Changing the facility revision supersedes the earlier risk.

Leave the simulator running for a forecast's full 30-minute future window plus five seconds to
see prospective evaluation. UNKNOWN actual windows remain recorded. Stop/restart the runtime to
verify retained predictions/events and fresh warm-up semantics. Tests use bounded chronological
fixtures to validate this window without sleeping for 35 minutes. The regular facility uses real
time; the separate Phase 11 rehearsal explicitly uses an accelerated simulation clock.

Inspect /api/v1/forecasts with an exclusive sequence cursor and /api/v1/intelligence/events with
an ascending sequence cursor only through an authorized native/local session. Credentials are
native-owned and must not be copied into browser storage or command logs.

## Install

Use Node 22.23.2 (.nvmrc), npm 10.9.8, uv 0.12.15, Python 3.12.14 (.python-version), and the
Rust toolchain pinned in rust-toolchain.toml. macOS requires Xcode Command Line Tools.

```sh
uv python install
npm ci
uv sync --locked
rustup show
```

The native npm scripts use a normal Rust installation or automatically select an isolated
.tooling/cargo + .tooling/rustup installation when present. This checkout contains that isolated
toolchain after local validation; .tooling is ignored and is not a distributed dependency.
Other checkouts should install the pinned toolchain through rustup.

The project Python environment must live at root .venv. Do not treat apps/api/requirements.txt
as an independent dependency authority. PostgreSQL and Docker are not required in Phase 2.

## Native desktop

```sh
npm run desktop:native
```

This starts Vite, builds Tauri, opens the desktop window and supervises its authenticated local
Python runtime. Do not separately start the old API or simulator for this workflow.

A debug build with embedded frontend assets is available through:

```sh
npm run desktop:build
```

On macOS its executable is apps/desktop/src-tauri/target/debug/gridforge-desktop. This build
still needs this source checkout and its .venv; it is not a distributable installer. Use `npm run desktop:package` for a standalone macOS release containing the embedded Python
runtime. Developer ID signing and notarization remain production release work.

The implementation was compiled and launched on macOS ARM64. Other platforms need native
prerequisites and validation before support is claimed. The CI native job targets macOS.

## Browser preview

```sh
npm run desktop
```

Open http://127.0.0.1:5173. Browser preview does not start or authenticate to the runtime.
It visibly reports UNAVAILABLE and disables native lifecycle/diagnostic actions. Settings
and navigation can be inspected; no live operational data is fabricated.

## Quality gates

```sh
npm run format
npm run check
npm run native:check
npm run desktop:build
```

The platform check runs Prettier, ESLint/Ruff, strict TS/mypy, generated-contract consistency,
Vitest, pytest (including real loopback process tests), and the frontend build. Native checks
run rustfmt, Clippy with warnings denied, and Rust tests against the real Python runtime.
Python tests and native tests require permission to bind ephemeral loopback ports.

After changing runtime Pydantic contracts:

```sh
npm run contracts:generate
npm run contracts:check
```

Python tests compare executable OpenAPI shapes with the committed schema; the TypeScript
check regenerates in memory and compares types without modifying source. The generator's
TypeScript 5 dependency is isolated from the app's TypeScript 6 tooling.

CI is configured to perform these checks with locked dependencies, plus a macOS native build.
Local validation does not establish hosted CI success; inspect the GitHub Actions run for the
published commit.

## Operator verification

- Open Telemetry: five synthetic assets should update near 1 Hz. Select bad, stale, disconnected,
  spike and normal scenarios. Bad/stale/disconnected samples must suppress the aggregate load.
- Filter the explorer by asset, request older measurements, then return to live.
- Restart the runtime: facility identity, sequence, history, counters and outbox survive.
  The scenario intentionally resets to normal. Cloud stays unconfigured.
- Open System Health: stop, start and restart the runtime. Each restart gets a new instance.
- Terminate the owned runtime PID shown in System Health: FAILED must appear, followed by
  recovery when Restart is selected. Do not terminate unrelated processes.
- Open Diagnostics: generate a bounded redacted report. It must contain no bearer credential,
  request payload, environment variable or filesystem path.
- Change theme/density in Settings and reopen the app to verify device-local persistence.
- Close/quit the desktop: its runtime must exit. The private-pipe watchdog also handles parent
  termination. Quit/reopen during failures must not leave an orphan runtime.

## Legacy Phase 0 reference

apps/api remains a separate, unauthenticated simulation scaffold. Its old routes are not
mounted in the native runtime. The original dashboard is preserved as the unmounted
LegacyScaffold component. It is not part of the native production asset graph.
For explicit legacy experiments only: npm run api and npm run simulator. Root .env.example
variables apply to that legacy path and optional PostgreSQL, not native credential bootstrap.
Never expose the legacy API to shared networks.

Optional PostgreSQL, after Docker installation and local password configuration:

```sh
docker compose --env-file .env -f infra/docker-compose.yml up -d postgres
```

The SQL remains disconnected bootstrap SQL, not a migration runner. Do not delete data
volumes to apply schema upgrades. SQLite telemetry persistence uses edge/storage/migrations independently of that central SQL.

## Environment maintenance

Commit dependency manifests and their lockfiles together. Preserve peer compatibility; never
use force/legacy-peer-deps to hide conflicts. Python uses pyproject.toml and uv.lock. Native
crates use Cargo.lock with --locked checks. Registry security findings are point-in-time;
full ongoing supply-chain scanning is Phase 10 work.

Restricted automation may set UV_CACHE_DIR, UV_PYTHON_INSTALL_DIR, CARGO_HOME, RUSTUP_HOME,
and npm --cache to allowed directories. These are tooling environment choices, not runtime
configuration or committed machine-specific paths. No changes to the user's shell are required.

## Phase 2 store and stream

The development host stores SQLite at .local/edge.db, with WAL sidecars. Do not delete it to
restart the application. Back up a stopped store before migration work. Unknown schema versions
fail startup. Run one native runtime per store; multiprocess ownership is not commissioned.

Five points per approximately one-second tick use seed 57 and a durable next sequence. Event
values are deterministic for seed/tick; wall-clock timestamps reflect actual execution. The
scenario is session-local and resets to normal on restart. Identity UUIDs are generated once;
SIM-1 through SIM-5 are synthetic fixture labels, not the Phase 3 asset registry.

Limits: 64 KiB request body, 100 points/batch, eight queued batches, 100 recent points/snapshot,
50 history points/native page, 100 maximum/API page, 256 KiB/native SSE line. Slow consumers get
current snapshots; historical points and event cursors remain in SQLite. Native SSE transport
reconnects after its three-second connection deadline; each reconnect receives complete state.
The UI invalidates the stream after five seconds without receipt and retains last known values.

The prototype caps storage at 250,000 points (about 13.9 hours of uninterrupted five-point/sec
ingestion from empty). Full storage returns explicit rejection and preserves telemetry/outbox;
it does not silently prune pending records. Cloud ACK/compaction policy is Phase 8. Provisioned
retention, disk quotas, long-duration soak tests and installer data paths remain hardening work.
An authenticated batch is acknowledged only after commit; interrupted/unacknowledged submissions
must be replayed with the same idempotency key and content. Conflicting replays reject atomically.

Launch via npm run desktop:native or the development executable from the workspace terminal.
A temporary QA .app launched through macOS LaunchServices timed out starting its child; the same
binary launched from the verified terminal reached READY. This temporary wrapper is not a
supported installer and is not shipped. OS bundle permission/packaging work remains Phase 10.

## Phase 3 registry workflow

Open Facilities to edit the local organization/facility and add production lines. Scope identity
is fixed; names/timezone are editable. Open Assets to create/edit nominal load, line assignment,
capabilities, criticality, flexibility limits, run/off durations and maintenance windows. The
maintenance editor uses explicitly labeled UTC start/end and reason fields; the API requires
timezone-aware timestamps. Maintenance blocks flexibility metadata, not telemetry or actual equipment.

Open OT Devices for simulator devices, signal mappings, the canonical metric and connector
health. New assets require an enabled mapping to produce samples. Start a new mapping with
W/0.001 or kW/1, then adjust calibration only deliberately. Bad normalized values are rejected.
One active power mapping per asset is supported. Disable mappings before disabling an asset or
device; disable assets before their production line. Edits are revision-checked and recorded in
the local configuration outbox. Refresh a record after conflict or uncertain save before retrying.

The adapter reads registry settings on each poll. Inspect mapping ID/revision in API history for
provenance. Telemetry displays the facility timezone; stored timestamps remain UTC. Scenario
controls in Telemetry exercise connector diagnostics: bad/stale become DEGRADED, disconnected
becomes DISCONNECTED, normal recovers after fresh samples. No physical adapter is installed.

Migration 0002 upgrades a Phase 2 store in place without deleting history or changing scope IDs.
Back up a stopped database before manual maintenance. Registry bounds are 100 records/150,000
serialized bytes and 10,000 configuration events; full capacity rejects edits. Cloud ACK,
retention and multi-process ownership remain deferred. No destructive registry delete exists.

## Phase 5 constraints and optimization workflow

1. Start `npm run desktop:native`; keep the simulator normal until Forecasting & Risk is READY.
2. In Facilities set a simulation demand threshold below the observed forecast peak.
3. In Assets configure at least one noncritical asset with simulated adjustment capability,
   flexibility enabled, bounded maximum reduction and sensible min/max loads. Preserve one
   nonflexible asset to see hard rejection. Wait for a forecast using the revised registry.
4. Open Constraints & Optimization. Enter a named policy, UTC allowed window covering now and
   the intended duration, maximum duration and total reduction cap. Optional rate is synthetic;
   leave it empty to verify INCOMPLETE economic value. Relative penalties are an asset-ID JSON
   object (0–10000, lower preferred; omitted asset penalty is 1).
5. Save policy, select its version, choose duration and generate a simulation proposal. Inspect
   global gates, candidate rejections/selections, estimate exclusions and input snapshot IDs.
6. Use a short cap or overlapping maintenance to see INFEASIBLE. Use bad/disconnected telemetry
   to see INPUT_READY fail. With no excess and good inputs expect NO_ACTION.
7. Older run/Latest run navigate durable history. Restart preserves policies/runs/events. An
   uncertain response can be retried with the same request ID. Clear pending request permits
   editing a rejected request; inspect latest results before issuing a new request ID.

The five-second proposal evidence window is intentionally short and does not authorize action.
No approve/dispatch controls exist in Phase 5. Tests include real simulator ingestion through
forecast and proposal, hard-gate rejection, native API round trips and UI retry identity.

## Phase 6 approval and simulated dispatch workflow

1. Follow the Phase 5 workflow until a PROPOSED optimization run exists. A fresh forecast,
   configured threshold, at least one flexible asset and policy window are needed for approval.
2. Open Dispatch. Review the proposal and choose a simulator behavior. Click Request approval.
   The backend rechecks current constraints and shows PENDING_APPROVAL for at most 120 seconds.
3. Review the command actions and enter a reason. Explicitly Approve, Reject or Cancel. Approval
   rechecks constraints, persists the decision and queues the command. Automatic approval is off.
4. The timeline shows SENT, ACKNOWLEDGED, EXECUTING and COMPLETED for normal behavior. A delayed
   ACK retries the same command ID. Missing ACK and rejected simulator command end FAILED.
   Disconnected/bad telemetry and stale/changed configuration fail closed. Cancellation stops
   any active synthetic reduction. The Telemetry screen shows the simulator response only while
   EXECUTING; completion does not create verified savings.
5. Restarting while a command is active records FAILED and removes the effect. Generate a new
   optimization run and obtain fresh approval; the old proposal cannot silently resume.

Local session permissions are server-enforced capability checks but are not verified user
identity or production RBAC. No physical OT connection or real settlement is supported.

## Phase 7 simulation finance workflow

1. Complete a normal simulated dispatch from Phase 6; failed or cancelled commands cannot be
   verified. Keep normal telemetry running through the full 300-second execution window and its
   equal-length rebound window.
2. Open Energy & Tariffs and save a user-entered simulation currency and energy rate. This creates
   an immutable version; the form spans the previous and next 30 days so a recently completed
   command can be assessed. The optional demand rate is only recorded, never applied to a short
   dispatch window.
3. Open Verification & Savings, select the completed command and tariff version, then start
   verification. The ledger records an ESTIMATED entry from the expected commanded reduction if
   the energy band covers execution. It has no measured-data or rebound claim.
4. After rebound ends plus five seconds, the worker checks every whole UTC second in both
   windows. One good, on-time, mapping-consistent simulator point per baseline asset is required.
   Complete data yields VERIFIED simulated net energy value: baseline-minus-actual energy cost
   during execution, less positive rebound energy cost under the selected tariff bands. Missing,
   duplicate, bad, late or uncovered intervals yield INCOMPLETE with no verified ledger entry.
5. Inspect forecast/proposal/command/tariff IDs and row-range/digest evidence in the case. The
   demand-charge assessment remains INCOMPLETE until complete billing-period interval demand,
   ratchet and utility rule evidence exists. These calculations are synthetic comparisons, not
   utility settlement or a causal savings study.

The local schema upgrades v5→v6 in place; back up a stopped SQLite database before manual
maintenance. The runtime's source of truth is `edge/runtime/app.py`, not `apps/api/app/main.py`.

## Phase 8 edge/cloud sync development workflow

1. Keep the desktop stopped while backing up `.local/edge.db`. Starting the updated native
   runtime migrates it from SQLite v6 to v7 and assigns a persistent edge UUID. Prior telemetry,
   configuration, forecast, optimization, dispatch and finance outboxes remain unchanged.
2. Start PostgreSQL for local development, supplying `POSTGRES_PASSWORD` to the optional
   Compose setup, or use a separately managed PostgreSQL database. Set
   `GRIDFORGE_CLOUD_DATABASE_URL` in the cloud receiver's environment. The receiver applies
   `database/migrations/0002_sync.sql` on startup; this also upgrades existing databases.
3. With the desktop stopped, enroll the edge with
   `uv run python -m scripts.provision_edge --edge-db .local/edge.db --token-file .local/edge-token`.
   This generates a new 256-bit token and writes it with mode 0600. Enrollment stores only its
   SHA-256 digest in PostgreSQL and binds the edge UUID to the local org/facility UUIDs. Keep the
   token file private and inject its contents as `GRIDFORGE_EDGE_TOKEN` into the native process.
4. Start `npm run cloud:sync` on loopback (default port 8081), and start the desktop with
   `GRIDFORGE_CLOUD_URL=http://127.0.0.1:8081`. For a remote receiver, use HTTPS with a trusted
   certificate and set the corresponding endpoint in the native process environment.
5. Open Sync Center. The worker fetches cloud cursors, uploads at most 20 versioned events per
   batch and five batches per stream per cycle, then marks local outbox rows acknowledged only
   after the cloud commits. Disconnect the cloud: pending count/oldest age grow while telemetry
   and simulated dispatch continue. Reconnect: the worker replays safely and catches up. A lost
   acknowledgement leads to a matched replay, not a second dispatch or finance record.
6. On sequence, scope or digest conflict, the affected stream is quarantined and its events stay
   local. Inspect both append-only histories and resolve the underlying divergence through an
   administrator-controlled data-repair procedure; the UI has no blind overwrite/skip action.
   Other streams continue. No cloud-to-edge command download exists in this phase.

`npm run check` includes real PostgreSQL integration tests when local `initdb`/`pg_ctl` are
available; otherwise those tests skip and unit tests still cover the local sync API/worker.
Cloud deployment, credential rotation, production TLS termination, OS credential storage and
central analytics projections need separate commissioning.

## Phase 9 Copilot and knowledge

Open AI Copilot in the native desktop. Ingest plain text or Markdown using a stable key, revision
1, title and source reference. Ask a Knowledge question containing relevant terms; inspect its
source revision, chunk offsets and digest. A new revision uses the same key and revision + 1.
Old revisions remain evidence for prior answers but no longer enter current retrieval.

Choose Analytics and ask for recent telemetry, dispatch commands, or the savings ledger. The
local provider selects a conservative query template. Users with `ai.inspect` can submit a
restricted SELECT and inspect the validated SQL, bound server scope, limits and result digest.
These are snapshots over the latest 1,000 source rows, not full-period reports. Feedback is
persisted and audited. The local provider is extractive/token-based, not a hosted language model.

`GRIDFORGE_AI_PROVIDER=disabled npm run desktop:native` exercises explicit AI unavailability.
Telemetry and the rest of the simulation remain available. Default `local` requires no API key.
The native launcher forwards only the documented sync/AI environment variables; `.env` is not
automatically sourced. Never put database credentials in `VITE_*` variables.

### Optional central AI backends

For an existing central database, an administrator applies `0003_ai_sync.sql`, then
`0004_ai_reporting.sql` and `0005_ai_vectors.sql` from `database/migrations`. The last migration
requires pgvector. Fresh Compose databases mount all migrations. Migration 0004 revokes PUBLIC
CREATE on the public schema; evaluate this change for a shared database before provisioning it.
Do not delete an existing volume to apply these changes.

Provision separate LOGIN accounts with membership in `gridforge_ai_reader` and, for the explicit
publication CLI only, `gridforge_knowledge_writer`. Use deployment-specific credentials. Do not
configure the desktop with an owner/superuser DSN. The adapters always SET LOCAL ROLE to the
corresponding restricted role, bind scope and enforce query timeouts.

Set `GRIDFORGE_KNOWLEDGE_WRITER_DSN` in the administrator's environment, then publish local
revisions explicitly:

```sh
uv run python -m scripts.publish_knowledge --edge-db .local/edge.db
```

Publication exports document content, preserves versions and can be replayed. It is separate
from the metadata-only AI audit sync stream. Set `GRIDFORGE_AI_KNOWLEDGE_DSN` to a reader DSN to
select central pgvector retrieval. The local document list is not a central catalog; publish
new local revisions before querying centrally. Set `GRIDFORGE_AI_QUERY_DSN` for central
telemetry analytics. Only telemetry has a central projection in this phase. The UI shows both
selected backends and reports errors without silently substituting local data.

### Phase 9 validation

`npm run check`, `npm run native:check`, and `npm run desktop:build` cover the implementation.
The PostgreSQL tests start and stop temporary loopback databases. They skip if PostgreSQL tools
are absent or initdb would run as root. pgvector tests use an installed extension when available.
On the verified macOS host, pgvector v0.8.0 was compiled in
`/private/tmp/gridforge-pgvector-phase9` without a system installation; run the full check with
`GRIDFORGE_TEST_PGVECTOR_DIR=/private/tmp/gridforge-pgvector-phase9` to load that temporary test
library. This test-only path registers the same vector types/functions directly in the temporary
DB; production uses CREATE EXTENSION. No production cloud was configured or contacted.
