# Phase 11 demonstration and desktop handoff

## Desktop walkthrough

Run the native desktop, create/sign in to a local administrator, and open **Integrated Demonstration**. It uses a separate temporary SQLite database and an explicitly accelerated simulation clock. The actual facility's configuration, telemetry, money and command history are not changed. Its evidence lasts until runtime shutdown; use Copy evidence to retain the JSON report.

Advance the steps in order: normal factory, bad quality, recovered demand peak, constraint proposal, explicit approval, verification, advisory explanation, cloud disconnect and reconnect. Generating one sample per simulated second is not the same as waiting a real second. Proposal deadlines in this sandbox use its paused/advanced simulation clock; this is not a demonstration of real operator response-time guarantees.

The proposal screen shows the reduction and excluded critical asset. Approval is a separate button requiring dispatch approval permission. No read, refresh or model result can approve it automatically. Verification measures actual simulator output and rebound; it does not overwrite measurements or manufacture a ledger result.

Cloud actions are disabled until a separate demo edge is enrolled in a real receiver. The normal facility's enrollment credential is not reused for the temporary demo identity. The UI never labels unconfigured cloud synchronization complete. `GRIDFORGE_DEMO_CLOUD_URL` and `GRIDFORGE_DEMO_EDGE_TOKEN` are separate native-forwarded configuration; enroll the edge/org/facility IDs shown under Demo enrollment identity. Restart creates a new ephemeral identity and requires reenrollment.

## Repeatable complete acceptance run

With PostgreSQL `initdb` and `pg_ctl` on PATH:

```sh
uv sync --locked
npm run demo:verify
```

The script's explicit `--approve-simulation` flag authorizes automated approval only for this disposable acceptance run. It launches temporary PostgreSQL and an actual loopback FastAPI receiver, enrolls a fresh demo edge, and executes all nine stages through the same DemoService used by the desktop. It saves `.local/phase11-demo.json`, then stops and removes the temporary receiver/database. The application dataset is untouched.

Fault injection blocks real HTTP transport during disconnect; it does not invent cloud responses. Reconnect drains bounded event batches and checks acknowledgement state. The integration test also reconciles received event count and cursor totals. Both local and central databases are mutated through their domain APIs; no manual telemetry/history editing is used.

The first verified run generated 1.84 USD of net **SIMULATED** energy value using an explicitly declared 0.15 USD/kWh synthetic tariff, a 60-second execution window and 60-second rebound window. This is a reproducible synthetic scenario, not a utility tariff claim, measured industrial saving or demand-charge saving. The predictor remains `rolling-mean-v1`; the explanation provider remains `local-extractive-v1`.

## Packaging and use

```sh
npm run desktop:package
uv run python -m scripts.smoke_packaged_runtime "apps/desktop/src-tauri/target/release/bundle/macos/GridForge AI.app/Contents/Resources/runtime/gridforge-edge/gridforge-edge"
```

The smoke test boots the bundled runtime outside the checkout, exercises local authentication and all seven local demo stages, verifies the finance and cited explanation results, signs out, and shuts down. The `.app` uses OS application data, separately from the development `.local/edge.db`. First run requires local administrator creation; no default password is provided.

The package is an ad-hoc signed macOS simulation prototype. Developer ID/notarization, unattended edge service hosting, other OS packages, production credential handling, remote authorization and physical OT commissioning remain independent release gates. See Operations and Release and the Corporate Operating Model.

## Client handoff

Continue with enterprise cloud read APIs and scoped identity before building web screens. Build the mobile field/alert companion after those shared contracts are stable. Do not expose edge IPC, internal SQLite or physical protocols to either client. Phase 11 adds no web/mobile application and no cloud-to-edge command transport.
