mod supervisor;

use supervisor::{DiagnosticSnapshot, LaunchConfig, Snapshot, Supervisor};
use tauri::{Manager, State};

#[tauri::command]
fn runtime_status(supervisor: State<'_, Supervisor>) -> Snapshot {
    supervisor.note_frontend();
    supervisor.snapshot()
}

#[tauri::command]
fn runtime_restart(supervisor: State<'_, Supervisor>) -> Result<(), String> {
    supervisor.restart()
}

#[tauri::command]
fn runtime_stop(supervisor: State<'_, Supervisor>) -> Result<(), String> {
    supervisor.stop()
}

#[tauri::command]
fn runtime_diagnostics(supervisor: State<'_, Supervisor>) -> DiagnosticSnapshot {
    supervisor.diagnostics()
}

#[tauri::command]
fn simulator_scenario(supervisor: State<'_, Supervisor>, scenario: String) -> Result<(), String> {
    supervisor.scenario(scenario)
}

#[tauri::command]
fn telemetry_history(
    supervisor: State<'_, Supervisor>,
    before: Option<u64>,
    asset: Option<String>,
) -> Result<serde_json::Value, String> {
    supervisor.history(before, asset)
}

#[tauri::command]
fn registry_read(supervisor: State<'_, Supervisor>) -> Result<serde_json::Value, String> {
    supervisor.registry(None)
}

#[tauri::command]
fn registry_save(
    supervisor: State<'_, Supervisor>,
    write: serde_json::Value,
) -> Result<serde_json::Value, String> {
    supervisor.registry(Some(write))
}

#[tauri::command]
fn intelligence_read(supervisor: State<'_, Supervisor>) -> Result<serde_json::Value, String> {
    supervisor.intelligence()
}

#[tauri::command]
fn optimization_request(
    supervisor: State<'_, Supervisor>,
    operation: String,
    write: Option<serde_json::Value>,
) -> Result<serde_json::Value, String> {
    supervisor.optimization(operation, write)
}

#[tauri::command]
fn dispatch_request(
    supervisor: State<'_, Supervisor>,
    operation: String,
    write: Option<serde_json::Value>,
) -> Result<serde_json::Value, String> {
    supervisor.dispatch(operation, write)
}

#[tauri::command]
fn finance_request(
    supervisor: State<'_, Supervisor>,
    operation: String,
    write: Option<serde_json::Value>,
) -> Result<serde_json::Value, String> {
    supervisor.finance(operation, write)
}

#[tauri::command]
fn sync_read(supervisor: State<'_, Supervisor>) -> Result<serde_json::Value, String> {
    supervisor.sync()
}

#[tauri::command]
fn ai_request(
    supervisor: State<'_, Supervisor>,
    operation: String,
    write: Option<serde_json::Value>,
) -> Result<serde_json::Value, String> {
    supervisor.ai(operation, write)
}

#[tauri::command]
fn security_request(
    supervisor: State<'_, Supervisor>,
    operation: String,
    write: Option<serde_json::Value>,
) -> Result<serde_json::Value, String> {
    supervisor.security(operation, write)
}

pub fn run() {
    tauri::Builder::default()
        .setup(|app| {
            let config = if cfg!(debug_assertions) {
                LaunchConfig::development()
            } else {
                match (app.path().resource_dir(), app.path().app_local_data_dir()) {
                    (Ok(resources), Ok(data)) => LaunchConfig::packaged(resources, data),
                    _ => Err("Application paths unavailable".into()),
                }
            };
            app.manage(Supervisor::start(config));
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            runtime_status,
            runtime_restart,
            runtime_stop,
            runtime_diagnostics,
            simulator_scenario,
            telemetry_history,
            registry_read,
            registry_save,
            intelligence_read,
            optimization_request,
            dispatch_request,
            finance_request,
            sync_read,
            ai_request,
            security_request
        ])
        .build(tauri::generate_context!())
        .expect("Desktop initialization failed")
        .run(|app, event| {
            if matches!(
                event,
                tauri::RunEvent::ExitRequested { .. } | tauri::RunEvent::Exit
            ) {
                app.state::<Supervisor>().shutdown();
            }
        });
}
