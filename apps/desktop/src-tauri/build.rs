fn main() {
    tauri_build::try_build(tauri_build::Attributes::new().app_manifest(
        tauri_build::AppManifest::new().commands(&[
            "runtime_status",
            "runtime_restart",
            "runtime_stop",
            "runtime_diagnostics",
            "simulator_scenario",
            "telemetry_history",
            "registry_read",
            "registry_save",
            "intelligence_read",
            "optimization_request",
            "dispatch_request",
            "finance_request",
            "sync_read",
            "ai_request",
            "security_request",
        ]),
    ))
    .expect("Unable to build desktop capability manifest");
}
